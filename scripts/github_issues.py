#!/usr/bin/env python3
"""
github_issues.py - GitHub Issue Management with Rate Limiting

A robust CLI tool for managing GitHub issues using the `gh` CLI.
Respects GitHub API rate limits with automatic retry and backoff.

Operations:
  - create: Create a new issue
  - edit: Modify an existing issue (title, body)
  - close: Close an issue
  - reopen: Reopen a closed issue
  - delete: Delete an issue
  - label: Add/remove labels
  - assign: Assign/unassign users
  - list: List issues with filters
  - view: View issue details

Usage:
    python github_issues.py create --title "Bug" --body "Description"
    python github_issues.py edit 123 --title "New title"
    python github_issues.py close 123
    python github_issues.py label 123 --add bug --add urgent
    python github_issues.py assign 123 --add username
    python github_issues.py list --state open --label bug
    python github_issues.py view 123

Requirements:
    - gh CLI installed and authenticated
    - Repository context (run from repo directory or use --repo)
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional


# Rate limiting configuration
RATE_LIMIT_DELAY = 0.5  # seconds between API calls
MAX_RETRIES = 3
RETRY_DELAYS = [1, 5, 30]  # seconds to wait on each retry
RATE_LIMIT_THRESHOLD = 10  # warn when remaining calls below this


@dataclass
class RateLimitInfo:
    """GitHub API rate limit information."""
    limit: int
    remaining: int
    reset_at: str
    used: int


def run_gh_command(args: list[str], capture_output: bool = True,
                   check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a gh CLI command with rate limiting and retry logic.

    Args:
        args: Command arguments (without 'gh' prefix)
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise on non-zero exit

    Returns:
        CompletedProcess with result

    Raises:
        subprocess.CalledProcessError: If command fails after retries
    """
    cmd = ['gh'] + args

    for attempt in range(MAX_RETRIES):
        try:
            # Add delay between API calls
            time.sleep(RATE_LIMIT_DELAY)

            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                check=check
            )
            return result

        except subprocess.CalledProcessError as e:
            # Check if it's a rate limit error
            stderr = e.stderr or ''
            if 'rate limit' in stderr.lower() or 'secondary rate limit' in stderr.lower():
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAYS[attempt]
                    print(f"Rate limited. Waiting {wait_time}s before retry {attempt + 2}/{MAX_RETRIES}...",
                          file=sys.stderr)
                    time.sleep(wait_time)
                    continue
            raise

    # Should not reach here, but just in case
    raise RuntimeError("Max retries exceeded")


def check_rate_limit() -> Optional[RateLimitInfo]:
    """Check current GitHub API rate limit status."""
    try:
        result = run_gh_command(['api', 'rate_limit'], check=True)
        data = json.loads(result.stdout)

        # Get the core rate limit (used for most operations)
        core = data.get('resources', {}).get('core', {})
        graphql = data.get('resources', {}).get('graphql', {})

        # Use the more restrictive limit
        if graphql.get('remaining', 999) < core.get('remaining', 999):
            limit_data = graphql
        else:
            limit_data = core

        return RateLimitInfo(
            limit=limit_data.get('limit', 0),
            remaining=limit_data.get('remaining', 0),
            reset_at=limit_data.get('reset', ''),
            used=limit_data.get('used', 0)
        )
    except Exception as e:
        print(f"Warning: Could not check rate limit: {e}", file=sys.stderr)
        return None


def warn_if_rate_limited():
    """Print a warning if close to rate limit."""
    info = check_rate_limit()
    if info and info.remaining < RATE_LIMIT_THRESHOLD:
        print(f"Warning: Only {info.remaining} API calls remaining. "
              f"Resets at {info.reset_at}", file=sys.stderr)


def get_repo_arg(repo: Optional[str]) -> list[str]:
    """Get --repo argument if specified."""
    return ['--repo', repo] if repo else []


# ============================================================
# Issue Operations
# ============================================================

def create_issue(title: str, body: str = '', labels: list[str] = None,
                 assignees: list[str] = None, milestone: str = None,
                 project: str = None, repo: str = None) -> dict:
    """
    Create a new GitHub issue.

    Returns:
        dict with issue number and URL
    """
    warn_if_rate_limited()

    args = ['issue', 'create', '--title', title]
    args.extend(get_repo_arg(repo))

    if body:
        args.extend(['--body', body])

    if labels:
        for label in labels:
            args.extend(['--label', label])

    if assignees:
        for assignee in assignees:
            args.extend(['--assignee', assignee])

    if milestone:
        args.extend(['--milestone', milestone])

    if project:
        args.extend(['--project', project])

    result = run_gh_command(args)

    # Parse the URL from output to get issue number
    url = result.stdout.strip()
    issue_number = url.split('/')[-1] if url else None

    return {
        'url': url,
        'number': issue_number
    }


def edit_issue(issue_number: int, title: str = None, body: str = None,
               add_labels: list[str] = None, remove_labels: list[str] = None,
               add_assignees: list[str] = None, remove_assignees: list[str] = None,
               milestone: str = None, repo: str = None) -> bool:
    """
    Edit an existing issue.

    Returns:
        True if successful
    """
    warn_if_rate_limited()

    args = ['issue', 'edit', str(issue_number)]
    args.extend(get_repo_arg(repo))

    if title:
        args.extend(['--title', title])

    if body:
        args.extend(['--body', body])

    if add_labels:
        for label in add_labels:
            args.extend(['--add-label', label])

    if remove_labels:
        for label in remove_labels:
            args.extend(['--remove-label', label])

    if add_assignees:
        for assignee in add_assignees:
            args.extend(['--add-assignee', assignee])

    if remove_assignees:
        for assignee in remove_assignees:
            args.extend(['--remove-assignee', assignee])

    if milestone:
        args.extend(['--milestone', milestone])

    run_gh_command(args)
    return True


def close_issue(issue_number: int, reason: str = 'completed',
                comment: str = None, repo: str = None) -> bool:
    """
    Close an issue.

    Args:
        reason: 'completed' or 'not_planned'
    """
    warn_if_rate_limited()

    args = ['issue', 'close', str(issue_number)]
    args.extend(get_repo_arg(repo))
    args.extend(['--reason', reason])

    if comment:
        args.extend(['--comment', comment])

    run_gh_command(args)
    return True


def reopen_issue(issue_number: int, comment: str = None,
                 repo: str = None) -> bool:
    """Reopen a closed issue."""
    warn_if_rate_limited()

    args = ['issue', 'reopen', str(issue_number)]
    args.extend(get_repo_arg(repo))

    if comment:
        args.extend(['--comment', comment])

    run_gh_command(args)
    return True


def delete_issue(issue_number: int, confirm: bool = False,
                 repo: str = None) -> bool:
    """
    Delete an issue.

    Note: This uses the GraphQL API as REST doesn't support issue deletion.
    Only repo admins can delete issues.
    """
    if not confirm:
        print("Error: Must pass --confirm to delete issues", file=sys.stderr)
        return False

    warn_if_rate_limited()

    # Get the issue node ID first
    args = ['issue', 'view', str(issue_number), '--json', 'id']
    args.extend(get_repo_arg(repo))

    result = run_gh_command(args)
    data = json.loads(result.stdout)
    node_id = data.get('id')

    if not node_id:
        print(f"Error: Could not get node ID for issue #{issue_number}",
              file=sys.stderr)
        return False

    # Delete using GraphQL
    mutation = f'''
    mutation {{
      deleteIssue(input: {{issueId: "{node_id}"}}) {{
        clientMutationId
      }}
    }}
    '''

    args = ['api', 'graphql', '-f', f'query={mutation}']
    run_gh_command(args)
    return True


def add_labels(issue_number: int, labels: list[str],
               repo: str = None) -> bool:
    """Add labels to an issue."""
    return edit_issue(issue_number, add_labels=labels, repo=repo)


def remove_labels(issue_number: int, labels: list[str],
                  repo: str = None) -> bool:
    """Remove labels from an issue."""
    return edit_issue(issue_number, remove_labels=labels, repo=repo)


def assign_users(issue_number: int, users: list[str],
                 repo: str = None) -> bool:
    """Assign users to an issue."""
    return edit_issue(issue_number, add_assignees=users, repo=repo)


def unassign_users(issue_number: int, users: list[str],
                   repo: str = None) -> bool:
    """Unassign users from an issue."""
    return edit_issue(issue_number, remove_assignees=users, repo=repo)


def list_issues(state: str = 'open', labels: list[str] = None,
                assignee: str = None, author: str = None,
                milestone: str = None, search: str = None,
                limit: int = 30, repo: str = None) -> list[dict]:
    """
    List issues with filters.

    Returns:
        List of issue dictionaries
    """
    warn_if_rate_limited()

    args = ['issue', 'list', '--state', state, '--limit', str(limit)]
    args.extend(get_repo_arg(repo))
    args.extend(['--json', 'number,title,state,labels,assignees,createdAt,url'])

    if labels:
        for label in labels:
            args.extend(['--label', label])

    if assignee:
        args.extend(['--assignee', assignee])

    if author:
        args.extend(['--author', author])

    if milestone:
        args.extend(['--milestone', milestone])

    if search:
        args.extend(['--search', search])

    result = run_gh_command(args)
    return json.loads(result.stdout)


def view_issue(issue_number: int, repo: str = None) -> dict:
    """
    View detailed issue information.

    Returns:
        Issue details as dictionary
    """
    warn_if_rate_limited()

    args = ['issue', 'view', str(issue_number)]
    args.extend(get_repo_arg(repo))
    args.extend(['--json', 'number,title,body,state,labels,assignees,'
                 'milestone,createdAt,updatedAt,closedAt,author,url,comments'])

    result = run_gh_command(args)
    return json.loads(result.stdout)


def add_comment(issue_number: int, body: str, repo: str = None) -> bool:
    """Add a comment to an issue."""
    warn_if_rate_limited()

    args = ['issue', 'comment', str(issue_number), '--body', body]
    args.extend(get_repo_arg(repo))

    run_gh_command(args)
    return True


def create_label(name: str, color: str = None, description: str = None,
                 repo: str = None) -> bool:
    """Create a new label in the repository."""
    warn_if_rate_limited()

    args = ['label', 'create', name]
    args.extend(get_repo_arg(repo))

    if color:
        args.extend(['--color', color.lstrip('#')])

    if description:
        args.extend(['--description', description])

    run_gh_command(args)
    return True


def list_labels(repo: str = None) -> list[dict]:
    """List all labels in the repository."""
    warn_if_rate_limited()

    args = ['label', 'list', '--json', 'name,color,description']
    args.extend(get_repo_arg(repo))

    result = run_gh_command(args)
    return json.loads(result.stdout)


# ============================================================
# Batch Operations
# ============================================================

def batch_create(issues: list[dict], repo: str = None) -> list[dict]:
    """
    Create multiple issues with rate limiting.

    Args:
        issues: List of dicts with 'title', 'body', 'labels', 'assignees'

    Returns:
        List of created issue info
    """
    results = []
    total = len(issues)

    for i, issue in enumerate(issues, 1):
        print(f"Creating issue {i}/{total}: {issue.get('title', 'Untitled')}")

        try:
            result = create_issue(
                title=issue.get('title', 'Untitled'),
                body=issue.get('body', ''),
                labels=issue.get('labels'),
                assignees=issue.get('assignees'),
                repo=repo
            )
            results.append({'success': True, **result})
        except Exception as e:
            results.append({'success': False, 'error': str(e)})

        # Extra delay for batch operations
        time.sleep(RATE_LIMIT_DELAY)

    return results


def batch_close(issue_numbers: list[int], reason: str = 'completed',
                repo: str = None) -> list[dict]:
    """Close multiple issues."""
    results = []
    total = len(issue_numbers)

    for i, num in enumerate(issue_numbers, 1):
        print(f"Closing issue {i}/{total}: #{num}")

        try:
            close_issue(num, reason=reason, repo=repo)
            results.append({'number': num, 'success': True})
        except Exception as e:
            results.append({'number': num, 'success': False, 'error': str(e)})

        time.sleep(RATE_LIMIT_DELAY)

    return results


def batch_label(issue_numbers: list[int], add: list[str] = None,
                remove: list[str] = None, repo: str = None) -> list[dict]:
    """Add/remove labels from multiple issues."""
    results = []
    total = len(issue_numbers)

    for i, num in enumerate(issue_numbers, 1):
        print(f"Updating labels {i}/{total}: #{num}")

        try:
            edit_issue(num, add_labels=add, remove_labels=remove, repo=repo)
            results.append({'number': num, 'success': True})
        except Exception as e:
            results.append({'number': num, 'success': False, 'error': str(e)})

        time.sleep(RATE_LIMIT_DELAY)

    return results


# ============================================================
# CLI Interface
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='GitHub Issue Management with Rate Limiting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s create --title "Bug report" --body "Description" --label bug
  %(prog)s edit 123 --title "Updated title" --add-label urgent
  %(prog)s close 123 --reason completed --comment "Fixed in PR #456"
  %(prog)s label 123 --add bug --add urgent --remove wontfix
  %(prog)s assign 123 --add username1 --add username2
  %(prog)s list --state open --label bug --limit 50
  %(prog)s view 123
  %(prog)s rate-limit
        '''
    )

    parser.add_argument('--repo', '-R', help='Repository (owner/repo)')

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Create
    create_parser = subparsers.add_parser('create', help='Create a new issue')
    create_parser.add_argument('--title', '-t', required=True)
    create_parser.add_argument('--body', '-b', default='')
    create_parser.add_argument('--label', '-l', action='append', dest='labels')
    create_parser.add_argument('--assignee', '-a', action='append', dest='assignees')
    create_parser.add_argument('--milestone', '-m')
    create_parser.add_argument('--project', '-p')

    # Edit
    edit_parser = subparsers.add_parser('edit', help='Edit an issue')
    edit_parser.add_argument('number', type=int)
    edit_parser.add_argument('--title', '-t')
    edit_parser.add_argument('--body', '-b')
    edit_parser.add_argument('--add-label', action='append', dest='add_labels')
    edit_parser.add_argument('--remove-label', action='append', dest='remove_labels')
    edit_parser.add_argument('--add-assignee', action='append', dest='add_assignees')
    edit_parser.add_argument('--remove-assignee', action='append', dest='remove_assignees')
    edit_parser.add_argument('--milestone', '-m')

    # Close
    close_parser = subparsers.add_parser('close', help='Close an issue')
    close_parser.add_argument('number', type=int)
    close_parser.add_argument('--reason', choices=['completed', 'not_planned'],
                              default='completed')
    close_parser.add_argument('--comment', '-c')

    # Reopen
    reopen_parser = subparsers.add_parser('reopen', help='Reopen an issue')
    reopen_parser.add_argument('number', type=int)
    reopen_parser.add_argument('--comment', '-c')

    # Delete
    delete_parser = subparsers.add_parser('delete', help='Delete an issue')
    delete_parser.add_argument('number', type=int)
    delete_parser.add_argument('--confirm', action='store_true', required=True,
                               help='Confirm deletion')

    # Label
    label_parser = subparsers.add_parser('label', help='Manage issue labels')
    label_parser.add_argument('number', type=int)
    label_parser.add_argument('--add', action='append', dest='add_labels')
    label_parser.add_argument('--remove', action='append', dest='remove_labels')

    # Assign
    assign_parser = subparsers.add_parser('assign', help='Manage issue assignees')
    assign_parser.add_argument('number', type=int)
    assign_parser.add_argument('--add', action='append', dest='add_users')
    assign_parser.add_argument('--remove', action='append', dest='remove_users')

    # List
    list_parser = subparsers.add_parser('list', help='List issues')
    list_parser.add_argument('--state', '-s', choices=['open', 'closed', 'all'],
                             default='open')
    list_parser.add_argument('--label', '-l', action='append', dest='labels')
    list_parser.add_argument('--assignee', '-a')
    list_parser.add_argument('--author')
    list_parser.add_argument('--milestone', '-m')
    list_parser.add_argument('--search', '-S')
    list_parser.add_argument('--limit', '-L', type=int, default=30)
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # View
    view_parser = subparsers.add_parser('view', help='View issue details')
    view_parser.add_argument('number', type=int)
    view_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Comment
    comment_parser = subparsers.add_parser('comment', help='Add a comment')
    comment_parser.add_argument('number', type=int)
    comment_parser.add_argument('--body', '-b', required=True)

    # Rate limit
    rate_parser = subparsers.add_parser('rate-limit', help='Check API rate limit')

    # Create label
    create_label_parser = subparsers.add_parser('create-label', help='Create a label')
    create_label_parser.add_argument('name')
    create_label_parser.add_argument('--color', '-c')
    create_label_parser.add_argument('--description', '-d')

    # List labels
    list_labels_parser = subparsers.add_parser('list-labels', help='List labels')
    list_labels_parser.add_argument('--json', action='store_true')

    # Batch operations
    batch_close_parser = subparsers.add_parser('batch-close', help='Close multiple issues')
    batch_close_parser.add_argument('numbers', nargs='+', type=int)
    batch_close_parser.add_argument('--reason', choices=['completed', 'not_planned'],
                                    default='completed')

    batch_label_parser = subparsers.add_parser('batch-label', help='Label multiple issues')
    batch_label_parser.add_argument('numbers', nargs='+', type=int)
    batch_label_parser.add_argument('--add', action='append')
    batch_label_parser.add_argument('--remove', action='append')

    args = parser.parse_args()

    try:
        if args.command == 'create':
            result = create_issue(
                title=args.title,
                body=args.body,
                labels=args.labels,
                assignees=args.assignees,
                milestone=args.milestone,
                project=args.project,
                repo=args.repo
            )
            print(f"Created issue: {result['url']}")

        elif args.command == 'edit':
            edit_issue(
                args.number,
                title=args.title,
                body=args.body,
                add_labels=args.add_labels,
                remove_labels=args.remove_labels,
                add_assignees=args.add_assignees,
                remove_assignees=args.remove_assignees,
                milestone=args.milestone,
                repo=args.repo
            )
            print(f"Updated issue #{args.number}")

        elif args.command == 'close':
            close_issue(args.number, reason=args.reason,
                       comment=args.comment, repo=args.repo)
            print(f"Closed issue #{args.number}")

        elif args.command == 'reopen':
            reopen_issue(args.number, comment=args.comment, repo=args.repo)
            print(f"Reopened issue #{args.number}")

        elif args.command == 'delete':
            if delete_issue(args.number, confirm=args.confirm, repo=args.repo):
                print(f"Deleted issue #{args.number}")

        elif args.command == 'label':
            edit_issue(args.number, add_labels=args.add_labels,
                      remove_labels=args.remove_labels, repo=args.repo)
            print(f"Updated labels on issue #{args.number}")

        elif args.command == 'assign':
            edit_issue(args.number, add_assignees=args.add_users,
                      remove_assignees=args.remove_users, repo=args.repo)
            print(f"Updated assignees on issue #{args.number}")

        elif args.command == 'list':
            issues = list_issues(
                state=args.state,
                labels=args.labels,
                assignee=args.assignee,
                author=args.author,
                milestone=args.milestone,
                search=args.search,
                limit=args.limit,
                repo=args.repo
            )

            if args.json:
                print(json.dumps(issues, indent=2))
            else:
                if not issues:
                    print("No issues found")
                else:
                    for issue in issues:
                        labels = ', '.join(l['name'] for l in issue.get('labels', []))
                        label_str = f" [{labels}]" if labels else ""
                        print(f"#{issue['number']}: {issue['title']}{label_str}")

        elif args.command == 'view':
            issue = view_issue(args.number, repo=args.repo)

            if args.json:
                print(json.dumps(issue, indent=2))
            else:
                print(f"#{issue['number']}: {issue['title']}")
                print(f"State: {issue['state']}")
                print(f"Author: {issue['author']['login']}")
                labels = ', '.join(l['name'] for l in issue.get('labels', []))
                if labels:
                    print(f"Labels: {labels}")
                assignees = ', '.join(a['login'] for a in issue.get('assignees', []))
                if assignees:
                    print(f"Assignees: {assignees}")
                print(f"URL: {issue['url']}")
                if issue.get('body'):
                    print(f"\n{issue['body']}")

        elif args.command == 'comment':
            add_comment(args.number, args.body, repo=args.repo)
            print(f"Added comment to issue #{args.number}")

        elif args.command == 'rate-limit':
            info = check_rate_limit()
            if info:
                print(f"Rate Limit: {info.remaining}/{info.limit} remaining")
                print(f"Used: {info.used}")
                print(f"Resets at: {info.reset_at}")
            else:
                print("Could not retrieve rate limit info")

        elif args.command == 'create-label':
            create_label(args.name, color=args.color,
                        description=args.description, repo=args.repo)
            print(f"Created label: {args.name}")

        elif args.command == 'list-labels':
            labels = list_labels(repo=args.repo)
            if args.json:
                print(json.dumps(labels, indent=2))
            else:
                for label in labels:
                    desc = f" - {label['description']}" if label.get('description') else ""
                    print(f"{label['name']} (#{label['color']}){desc}")

        elif args.command == 'batch-close':
            results = batch_close(args.numbers, reason=args.reason, repo=args.repo)
            success = sum(1 for r in results if r['success'])
            print(f"Closed {success}/{len(results)} issues")

        elif args.command == 'batch-label':
            results = batch_label(args.numbers, add=args.add,
                                 remove=args.remove, repo=args.repo)
            success = sum(1 for r in results if r['success'])
            print(f"Updated {success}/{len(results)} issues")

    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr or e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
