#!/usr/bin/env python3
"""
Generate Work-Based Learning Schedule Report

Analyzes student schedules to identify which students can work together
on long-lived group projects without being separated by class schedules.
"""

import csv
from collections import defaultdict
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
ROSTER_DIR = SCRIPT_DIR.parent / 'waco-teams-hosting' / 'rosters'
OUTPUT_DIR = SCRIPT_DIR.parent / 'waco-teams-hosting'
WBL_SCHEDULE_FILE = OUTPUT_DIR / 'wbl-schedule.csv'

# Schedule structure
# A-day: morning=1,2  afternoon=3,4
# B-day: morning=5,6  afternoon=7,8
# C-day: combines A+B with shorter periods - NOT used for group planning

SCHEDULE = {
    'A': {
        'morning': ['01', '02'],
        'afternoon': ['03', '04']
    },
    'B': {
        'morning': ['05', '06'],
        'afternoon': ['07', '08']
    }
}

# Period pairs (A-day period -> B-day equivalent)
PERIOD_PAIRS = {
    '01': '05', '02': '06', '03': '07', '04': '08',
    '05': '01', '06': '02', '07': '03', '08': '04'
}


def load_roster():
    """Load the most recent ab-frontline roster."""
    roster_files = list(ROSTER_DIR.glob('ab-frontline-roster-*.csv'))
    if not roster_files:
        raise FileNotFoundError("No ab-frontline roster found")

    latest = max(roster_files, key=lambda p: p.stat().st_mtime)
    print(f"Loading roster: {latest.name}")

    students = defaultdict(lambda: {'periods': set(), 'courses': {}, 'wbl': {}})

    with open(latest, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Student Name']
            period = row['Period']
            course = row['Course']
            day = row['Day']

            students[name]['periods'].add(period)
            students[name]['courses'][period] = course

    return dict(students)


def load_wbl_schedule():
    """Load the WBL schedule showing when students are out."""
    if not WBL_SCHEDULE_FILE.exists():
        print(f"Warning: WBL schedule not found at {WBL_SCHEDULE_FILE}")
        return {}

    print(f"Loading WBL schedule: {WBL_SCHEDULE_FILE.name}")
    wbl = defaultdict(lambda: {'Mon': [], 'Tue': [], 'Wed': [], 'Thu': [], 'Fri': []})

    with open(WBL_SCHEDULE_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            student = row['Student'].strip()
            teacher = row['Teacher'].strip()
            room = row.get('Room', '').strip()

            for day, col in [('Mon', 'Monday'), ('Tue', 'Tuesday'), ('Wed', 'Wednesday'),
                            ('Thu', 'Thursday'), ('Fri', 'Friday')]:
                time_slot = row.get(col, '').strip()
                if time_slot:
                    wbl[student][day].append({
                        'time': time_slot,
                        'teacher': teacher,
                        'room': room
                    })

    return dict(wbl)


def match_student_to_wbl(student_name, wbl_schedule):
    """
    Match a full student name to WBL schedule entries.
    Student names in roster: "Last, First Middle"
    Student names in WBL: "First L" or just "First"
    """
    # Parse roster name
    parts = student_name.split(', ')
    if len(parts) != 2:
        return None

    last = parts[0]
    first_parts = parts[1].split()
    first = first_parts[0]

    # Try exact matches first
    for wbl_name in wbl_schedule.keys():
        # "First L" format
        if wbl_name == f"{first} {last[0]}":
            return wbl_name
        # Just first name
        if wbl_name == first:
            return wbl_name
        # First name with initial
        if wbl_name.startswith(first) and len(wbl_name) > len(first):
            next_char = wbl_name[len(first)]
            if next_char == ' ' or next_char.isupper():
                return wbl_name

    return None


def get_wbl_summary(student_name, wbl_schedule):
    """Get a brief WBL summary for a student."""
    wbl_key = match_student_to_wbl(student_name, wbl_schedule)
    if not wbl_key:
        return None

    schedule = wbl_schedule[wbl_key]
    days_out = []
    for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']:
        if schedule[day]:
            times = [s['time'] for s in schedule[day]]
            days_out.append(f"{day}:{','.join(times)}")

    if days_out:
        return ' | '.join(days_out)
    return None


def get_period_group(periods):
    """
    Determine which class group a student belongs to based on periods.
    Returns a tuple of (morning_periods, afternoon_periods) for grouping.
    """
    morning = sorted([p for p in periods if p in ['01', '02', '05', '06']])
    afternoon = sorted([p for p in periods if p in ['03', '04', '07', '08']])
    return (tuple(morning), tuple(afternoon))


def get_time_slot(period):
    """Return 'morning' or 'afternoon' for a period."""
    if period in ['01', '02', '05', '06']:
        return 'morning'
    return 'afternoon'


def get_day_type(period):
    """Return 'A' or 'B' for a period."""
    if period in ['01', '02', '03', '04']:
        return 'A'
    return 'B'


def analyze_groupings(students):
    """
    Analyze which students can be grouped together.
    Returns groups organized by when students are together.
    """
    # Group students by their period pattern
    by_pattern = defaultdict(list)

    for name, data in students.items():
        pattern = get_period_group(data['periods'])
        by_pattern[pattern].append({
            'name': name,
            'periods': data['periods'],
            'courses': data['courses']
        })

    # Also organize by specific period for quick lookup
    by_period = defaultdict(list)
    for name, data in students.items():
        for period in data['periods']:
            by_period[period].append(name)

    return by_pattern, by_period


def format_student_name(name):
    """Convert 'Last, First Middle' to 'First L.' for brevity."""
    parts = name.split(', ')
    if len(parts) == 2:
        last = parts[0]
        first_parts = parts[1].split()
        first = first_parts[0]
        return f"{first} {last[0]}."
    return name


# Group size constraints
MIN_GROUP_SIZE = 3
MAX_GROUP_SIZE = 7
IDEAL_GROUP_SIZE = 5


def split_into_groups(names, min_size=MIN_GROUP_SIZE, max_size=MAX_GROUP_SIZE, ideal_size=IDEAL_GROUP_SIZE):
    """
    Split a list of names into groups of appropriate size.
    - Max 7, min 3, ideal 4-6
    - Avoids groups of 2 (merge with another)
    """
    n = len(names)

    if n <= max_size:
        return [names]

    # Calculate optimal number of groups
    # Try to get groups close to ideal_size
    num_groups = max(1, round(n / ideal_size))

    # Adjust to avoid tiny groups
    base_size = n // num_groups
    remainder = n % num_groups

    # If base_size would be too small, reduce number of groups
    while base_size < min_size and num_groups > 1:
        num_groups -= 1
        base_size = n // num_groups
        remainder = n % num_groups

    # If groups would be too large, increase number of groups
    while base_size > max_size:
        num_groups += 1
        base_size = n // num_groups
        remainder = n % num_groups

    # Distribute students into groups
    groups = []
    idx = 0
    for i in range(num_groups):
        # Add one extra to first 'remainder' groups
        size = base_size + (1 if i < remainder else 0)
        groups.append(names[idx:idx + size])
        idx += size

    return groups


def get_schedule_notes(pattern, time_slot):
    """
    Generate brief WBL schedule notes - periods and when they're together.
    """
    morning_p, afternoon_p = pattern
    all_periods = sorted(set(morning_p) | set(afternoon_p))

    # Simplify: strip leading zeros for readability
    periods = [p.lstrip('0') for p in all_periods]
    periods_str = f"Periods {', '.join(periods)}"

    # Determine when they're together (which day/time blocks)
    together = []
    if set(['01', '02']) & set(all_periods):
        together.append("A-AM")
    if set(['03', '04']) & set(all_periods):
        together.append("A-PM")
    if set(['05', '06']) & set(all_periods):
        together.append("B-AM")
    if set(['07', '08']) & set(all_periods):
        together.append("B-PM")

    together_str = " + ".join(together) if together else "None"

    return f"{periods_str} → Together {together_str}"


def compute_pattern_overlap(pattern1, pattern2):
    """Calculate how many periods two patterns share."""
    m1, a1 = pattern1
    m2, a2 = pattern2
    all1 = set(m1) | set(a1)
    all2 = set(m2) | set(a2)
    return len(all1 & all2)


# Fun group names for future educators (classroom/nature themed)
GROUP_NAMES = [
    "Fireflies", "Sunbeams", "Starlight", "Rainbows", "Butterflies",
    "Honeybees", "Bluebirds", "Ladybugs", "Daisies", "Sunflowers",
    "Moonbeams", "Dragonflies", "Hummingbirds", "Marigolds", "Bluebonnets",
    "Robins", "Sparrows", "Meadowlarks", "Wildflowers", "Snapdragons"
]


def generate_report(students, by_pattern, by_period, wbl_schedule):
    """Generate the markdown report v2.0 - organized by AM/PM with unique groups."""
    lines = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    name_idx = 0  # Track which group name to use

    lines.append("# WBL Group Planner")
    lines.append("")
    lines.append("**Version 2.0** | Mr. Edwards | Future Educators Academy")
    lines.append("")
    lines.append(f"*Generated: {now}*")
    lines.append("")
    lines.append("Each group appears once. More ★ = more time together.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Categorize all students by AM/PM and A-day vs B-only
    am_a_students = set()  # In periods 1 or 2 (A-day AM)
    am_b_only_students = set()  # In periods 5 or 6 but NOT 1 or 2
    pm_a_students = set()  # In periods 3 or 4 (A-day PM)
    pm_b_only_students = set()  # In periods 7 or 8 but NOT 3 or 4

    for name, data in students.items():
        periods = data['periods']
        in_a_am = bool(periods & {'01', '02'})
        in_b_am = bool(periods & {'05', '06'})
        in_a_pm = bool(periods & {'03', '04'})
        in_b_pm = bool(periods & {'07', '08'})

        if in_a_am:
            am_a_students.add(name)
        elif in_b_am:
            am_b_only_students.add(name)

        if in_a_pm:
            pm_a_students.add(name)
        elif in_b_pm:
            pm_b_only_students.add(name)

    def build_groups(student_set):
        """Build groups from a set of students, merging tiny ones."""
        sub_groups = defaultdict(list)
        for name in student_set:
            pattern = get_period_group(students[name]['periods'])
            sub_groups[pattern].append(name)

        sorted_groups = sorted(sub_groups.items(), key=lambda x: -len(x[1]))

        final_groups = []
        tiny_students = []

        for pattern, names in sorted_groups:
            if len(names) < MIN_GROUP_SIZE:
                for name in names:
                    tiny_students.append((name, pattern))
            else:
                final_groups.append((pattern, list(names)))

        for name, tiny_pattern in tiny_students:
            if not final_groups:
                final_groups.append((tiny_pattern, [name]))
            else:
                best_idx = 0
                best_overlap = -1
                for i, (grp_pattern, grp_names) in enumerate(final_groups):
                    overlap = compute_pattern_overlap(tiny_pattern, grp_pattern)
                    if overlap > best_overlap or (overlap == best_overlap and len(grp_names) < len(final_groups[best_idx][1])):
                        best_overlap = overlap
                        best_idx = i
                final_groups[best_idx][1].append(name)

        return final_groups

    def output_groups(final_groups, section_label):
        """Output groups with names and WBL schedules."""
        nonlocal name_idx
        for pattern, names in final_groups:
            names_sorted = sorted(names)
            morning_p, afternoon_p = pattern
            stability = "★★★" if len(morning_p) >= 2 and len(afternoon_p) >= 2 else "★★" if len(morning_p) + len(afternoon_p) >= 3 else "★"
            schedule_notes = get_schedule_notes(pattern, 'morning')

            subgroups = split_into_groups(names_sorted)

            for subgroup in subgroups:
                group_name = GROUP_NAMES[name_idx % len(GROUP_NAMES)]
                name_idx += 1

                lines.append(f"### {group_name} ({len(subgroup)}) {stability}")
                lines.append("")
                lines.append(f"{schedule_notes}")
                lines.append("")

                for full_name in subgroup:
                    short = format_student_name(full_name)
                    wbl_info = get_wbl_summary(full_name, wbl_schedule)
                    if wbl_info:
                        lines.append(f"- **{short}**: {wbl_info}")
                    else:
                        lines.append(f"- **{short}**")

                lines.append("")

    # === MORNING SECTION ===
    lines.append("## ☀️ Morning Students")
    lines.append("")

    # A-Day Morning (anchor)
    if am_a_students:
        lines.append("### A-Day Mornings (Periods 1-2)")
        lines.append("")
        lines.append("*These groups also meet B-Day mornings (Periods 5-6)*")
        lines.append("")
        am_a_groups = build_groups(am_a_students)
        output_groups(am_a_groups, "A-AM")
        lines.append("---")
        lines.append("")

    # B-Only Morning
    if am_b_only_students:
        lines.append("### B-Day Only Mornings (Periods 5-6)")
        lines.append("")
        lines.append("*These students are only here B-Day mornings*")
        lines.append("")
        am_b_groups = build_groups(am_b_only_students)
        output_groups(am_b_groups, "B-AM")
        lines.append("---")
        lines.append("")

    # === AFTERNOON SECTION ===
    lines.append("## 🌙 Afternoon Students")
    lines.append("")

    # A-Day Afternoon (anchor)
    if pm_a_students:
        lines.append("### A-Day Afternoons (Periods 3-4)")
        lines.append("")
        lines.append("*These groups also meet B-Day afternoons (Periods 7-8)*")
        lines.append("")
        pm_a_groups = build_groups(pm_a_students)
        output_groups(pm_a_groups, "A-PM")
        lines.append("---")
        lines.append("")

    # B-Only Afternoon
    if pm_b_only_students:
        lines.append("### B-Day Only Afternoons (Periods 7-8)")
        lines.append("")
        lines.append("*These students are only here B-Day afternoons*")
        lines.append("")
        pm_b_groups = build_groups(pm_b_only_students)
        output_groups(pm_b_groups, "B-PM")
        lines.append("---")
        lines.append("")

    # Legend
    lines.append("## Legend")
    lines.append("")
    lines.append("- ★★★ = Together all day types (best for long projects)")
    lines.append("- ★★ = Together most of the time")
    lines.append("- ★ = Together some of the time")
    lines.append("")

    # Detailed roster by period
    lines.append("---")
    lines.append("")
    lines.append("## Detailed Roster by Period")
    lines.append("")

    for period in ['01', '02', '03', '04', '05', '06', '07', '08']:
        day = 'A' if period in ['01', '02', '03', '04'] else 'B'
        time = 'Morning' if period in ['01', '02', '05', '06'] else 'Afternoon'

        lines.append(f"### Period {period} ({day}-Day {time})")
        lines.append("")

        period_students = sorted(by_period.get(period, []))
        if not period_students:
            lines.append("*No students*")
            lines.append("")
            continue

        # Group by course
        by_course = defaultdict(list)
        for name in period_students:
            course = students[name]['courses'].get(period, 'Unknown')
            by_course[course].append(name)

        for course in sorted(by_course.keys()):
            lines.append(f"**{course}** ({len(by_course[course])} students)")
            lines.append("")
            for name in sorted(by_course[course]):
                short = format_student_name(name)
                other_periods = sorted(students[name]['periods'] - {period})
                if other_periods:
                    lines.append(f"- {short} *(also: {', '.join(other_periods)})*")
                else:
                    lines.append(f"- {short}")
            lines.append("")

    # Summary stats
    lines.append("---")
    lines.append("")
    lines.append("## Summary Statistics")
    lines.append("")
    lines.append(f"- **Total unique students:** {len(students)}")
    lines.append(f"- **Unique schedule patterns:** {len(by_pattern)}")
    lines.append("")

    # Pattern breakdown
    lines.append("### Schedule Pattern Distribution")
    lines.append("")
    lines.append("| Pattern (Morning / Afternoon) | Count |")
    lines.append("|------------------------------|-------|")

    for pattern, names in sorted(by_pattern.items(), key=lambda x: -len(x[1])):
        morning, afternoon = pattern
        morning_str = ','.join(morning) if morning else '-'
        afternoon_str = ','.join(afternoon) if afternoon else '-'
        lines.append(f"| {morning_str} / {afternoon_str} | {len(names)} |")

    lines.append("")

    return '\n'.join(lines)


def main():
    print("Work-Based Learning Group Planner")
    print("=" * 40)

    # Load data
    students = load_roster()
    print(f"Loaded {len(students)} students")

    wbl_schedule = load_wbl_schedule()
    print(f"Loaded WBL schedule for {len(wbl_schedule)} students")

    # Analyze
    by_pattern, by_period = analyze_groupings(students)
    print(f"Found {len(by_pattern)} unique schedule patterns")

    # Generate report
    report = generate_report(students, by_pattern, by_period, wbl_schedule)

    # Write markdown
    md_path = OUTPUT_DIR / 'wbl-group-planner.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Wrote: {md_path}")

    return md_path


if __name__ == '__main__':
    main()
