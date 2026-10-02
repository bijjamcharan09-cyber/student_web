"""
V2 Database Migration Script.
Safely creates users, faculty, and faculty_subjects tables,
and seeds initial administrative and faculty accounts.
Does NOT drop or alter any existing V1 tables or student data.
"""

import sys
from pathlib import Path
import pymysql
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config


V2_MIGRATION_SQL = """
-- 1. Create Faculty table
CREATE TABLE IF NOT EXISTS `faculty` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `faculty_code` VARCHAR(30) NOT NULL UNIQUE,
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `phone` VARCHAR(20) NULL,
    `department` VARCHAR(100) NOT NULL,
    `designation` VARCHAR(50) NOT NULL DEFAULT 'Lecturer',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_faculty_dept` (`department`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Create Users table for RBAC authentication
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('Admin', 'Faculty', 'Student') NOT NULL,
    `student_id` INT NULL,
    `faculty_id` INT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_role` (`role`),
    CONSTRAINT `fk_users_student` FOREIGN KEY (`student_id`)
        REFERENCES `students` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_users_faculty` FOREIGN KEY (`faculty_id`)
        REFERENCES `faculty` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Create Faculty-Subject assignment table
CREATE TABLE IF NOT EXISTS `faculty_subjects` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `faculty_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `semester_id` INT NOT NULL,
    `assigned_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_faculty_subject_sem` (`faculty_id`, `subject_id`, `semester_id`),
    INDEX `idx_fs_faculty` (`faculty_id`),
    INDEX `idx_fs_subject` (`subject_id`),
    CONSTRAINT `fk_fs_faculty` FOREIGN KEY (`faculty_id`)
        REFERENCES `faculty` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_fs_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_fs_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def run_migration():
    print("=" * 60)
    print("Running V2 Database Schema Migration (RBAC & Faculty Support)")
    print("=" * 60)
    print(f"Connecting to {Config.DB_HOST}:{Config.DB_PORT} as {Config.DB_USER}...")

    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset=Config.DB_CHARSET,
        autocommit=True,
    )

    with conn.cursor() as cursor:
        # Execute DDL statements
        for stmt in V2_MIGRATION_SQL.strip().split(";"):
            clean_stmt = stmt.strip()
            if clean_stmt:
                cursor.execute(clean_stmt)
        print("V2 tables created/verified successfully.")

        # Seed initial Admin user if not exists
        cursor.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        if not cursor.fetchone():
            admin_hash = generate_password_hash("Admin@123")
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, 'Admin', TRUE)
                """,
                ("admin", "admin@sms.edu", admin_hash),
            )
            print("Created default Admin user: admin (Password: Admin@123)")

        # Seed sample Faculty member & user if not exists
        cursor.execute("SELECT id FROM faculty WHERE faculty_code = %s", ("FAC-001",))
        fac_row = cursor.fetchone()
        if not fac_row:
            cursor.execute(
                """
                INSERT INTO faculty (faculty_code, first_name, last_name, email, department, designation)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                ("FAC-001", "Robert", "Turing", "r.turing@sms.edu", "Computer Science", "Associate Professor"),
            )
            faculty_id = cursor.lastrowid
            fac_hash = generate_password_hash("Faculty@123")
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, role, faculty_id, is_active)
                VALUES (%s, %s, %s, 'Faculty', %s, TRUE)
                """,
                ("faculty_turing", "r.turing@sms.edu", fac_hash, faculty_id),
            )
            print("Created default Faculty: faculty_turing (Password: Faculty@123)")

            # Assign first available subject to this faculty member if subjects exist
            cursor.execute("SELECT id, semester_id FROM subjects LIMIT 1")
            sub = cursor.fetchone()
            if sub and sub[1]:
                cursor.execute(
                    """
                    INSERT IGNORE INTO faculty_subjects (faculty_id, subject_id, semester_id)
                    VALUES (%s, %s, %s)
                    """,
                    (faculty_id, sub[0], sub[1]),
                )
                print(f"Assigned subject ID {sub[0]} to faculty ID {faculty_id}.")

        # Check existing students and create matching Student user accounts
        cursor.execute("SELECT id, roll_number, email FROM students")
        students = cursor.fetchall()
        for stu_id, roll_no, stu_email in students:
            username = f"student_{roll_no.lower().replace('-', '_')}"
            cursor.execute("SELECT id FROM users WHERE username = %s OR student_id = %s", (username, stu_id))
            if not cursor.fetchone():
                stu_hash = generate_password_hash("Student@123")
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role, student_id, is_active)
                    VALUES (%s, %s, %s, 'Student', %s, TRUE)
                    """,
                    (username, stu_email, stu_hash, stu_id),
                )
                print(f"Created student user account: {username} (Password: Student@123)")

    conn.close()
    print("=" * 60)
    print("V2 Migration Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
