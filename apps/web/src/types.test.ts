import { describe, it, expect } from 'vitest';
import type { GoogleUser, Course, Student } from './types';

describe('Types', () => {
  describe('GoogleUser', () => {
    it('should have required properties', () => {
      const user: GoogleUser = {
        email: 'test@example.com',
        name: 'Test User',
        picture: 'https://example.com/photo.jpg',
      };

      expect(user.email).toBe('test@example.com');
      expect(user.name).toBe('Test User');
      expect(user.picture).toBe('https://example.com/photo.jpg');
    });
  });

  describe('Course', () => {
    it('should have required properties', () => {
      const course: Course = {
        id: 'course-123',
        name: 'Math 101',
        ownerId: 'owner-456',
      };

      expect(course.id).toBe('course-123');
      expect(course.name).toBe('Math 101');
      expect(course.ownerId).toBe('owner-456');
    });

    it('should support optional properties', () => {
      const course: Course = {
        id: 'course-123',
        name: 'Math 101',
        ownerId: 'owner-456',
        section: 'Period 1',
        description: 'Introduction to Mathematics',
        room: 'Room 101',
        courseState: 'ACTIVE',
      };

      expect(course.section).toBe('Period 1');
      expect(course.description).toBe('Introduction to Mathematics');
      expect(course.room).toBe('Room 101');
      expect(course.courseState).toBe('ACTIVE');
    });
  });

  describe('Student', () => {
    it('should have required properties', () => {
      const student: Student = {
        courseId: 'course-123',
        userId: 'user-789',
        profile: {
          id: 'profile-789',
          name: {
            givenName: 'John',
            familyName: 'Doe',
            fullName: 'John Doe',
          },
          emailAddress: 'john.doe@example.com',
        },
      };

      expect(student.courseId).toBe('course-123');
      expect(student.userId).toBe('user-789');
      expect(student.profile.name.fullName).toBe('John Doe');
      expect(student.profile.emailAddress).toBe('john.doe@example.com');
    });

    it('should support optional photo URL', () => {
      const student: Student = {
        courseId: 'course-123',
        userId: 'user-789',
        profile: {
          id: 'profile-789',
          name: {
            givenName: 'Jane',
            familyName: 'Smith',
            fullName: 'Jane Smith',
          },
          emailAddress: 'jane.smith@example.com',
          photoUrl: 'https://example.com/jane.jpg',
        },
      };

      expect(student.profile.photoUrl).toBe('https://example.com/jane.jpg');
    });
  });
});
