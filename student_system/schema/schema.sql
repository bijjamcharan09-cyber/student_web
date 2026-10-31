-- =============================================================================
-- Production Student Management System (SMS) Schema V3
-- Multi-Organisation Architecture with Role-Based Access Control (RBAC)
-- Database: MySQL 8.0+
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `student_management_db`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `student_management_db`;

-- Drop tables in reverse foreign key order for clean resets if needed
-- (Production deployments should use migrations rather than drop/recreate)
-- DROP TABLE IF EXISTS `attendance_sessions`;
-- DROP TABLE IF EXISTS `campus_settings`;
-- DROP TABLE IF EXISTS `users`;
-- DROP TABLE IF EXISTS `faculty_subjects`;
-- DROP TABLE IF EXISTS `faculty`;
-- DROP TABLE IF EXISTS `attendance`;
-- DROP TABLE IF EXISTS `marks`;
-- DROP TABLE IF EXISTS `student_subjects`;
-- DROP TABLE IF EXISTS `students`;
-- DROP TABLE IF EXISTS `subjects`;
-- DROP TABLE IF EXISTS `semesters`;
-- DROP TABLE IF EXISTS `organisations`;

-- -----------------------------------------------------------------------------
-- 1. Organisations Table (Multi-Tenancy Foundation)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `organisations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(150) NOT NULL COMMENT 'Institution / College name',
    `code` VARCHAR(50) NOT NULL UNIQUE COMMENT 'Unique identifier, e.g. VREC',
    `status` VARCHAR(20) NOT NULL DEFAULT 'Active' COMMENT 'Active, Suspended, Inactive',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_org_status` ON `organisations` (`status`);

-- Default Seed: Vijay Rural Engineering College
INSERT INTO `organisations` (`id`, `name`, `code`, `status`)
VALUES (1, 'Vijay Rural Engineering College', 'VREC', 'Active')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- -----------------------------------------------------------------------------
-- 2. Semesters Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `semesters` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `name` VARCHAR(50) NOT NULL COMMENT 'e.g., Fall 2025 or Semester 1',
    `semester_number` TINYINT UNSIGNED NOT NULL COMMENT '1 to 12',
    `academic_year` VARCHAR(20) NOT NULL COMMENT 'e.g., 2025-2026',
    `start_date` DATE NOT NULL,
    `end_date` DATE NOT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `chk_semester_dates` CHECK (`start_date` <= `end_date`),
    CONSTRAINT `chk_semester_number` CHECK (`semester_number` >= 1 AND `semester_number` <= 12),
    CONSTRAINT `uq_semesters_org_name` UNIQUE (`organisation_id`, `name`),
    CONSTRAINT `fk_semesters_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_semesters_org` ON `semesters` (`organisation_id`);
CREATE INDEX `idx_semesters_active` ON `semesters` (`is_active`);
CREATE INDEX `idx_semesters_year` ON `semesters` (`academic_year`);

-- -----------------------------------------------------------------------------
-- 3. Subjects Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `subjects` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `subject_code` VARCHAR(20) NOT NULL COMMENT 'e.g., CS101, MATH201',
    `name` VARCHAR(100) NOT NULL,
    `credits` DECIMAL(3, 1) NOT NULL DEFAULT 3.0,
    `department` VARCHAR(100) NOT NULL,
    `semester_id` INT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `chk_credits_range` CHECK (`credits` > 0 AND `credits` <= 12),
    CONSTRAINT `uq_subjects_org_code` UNIQUE (`organisation_id`, `subject_code`),
    CONSTRAINT `fk_subjects_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_subjects_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_subjects_org` ON `subjects` (`organisation_id`);
CREATE INDEX `idx_subjects_code` ON `subjects` (`subject_code`);
CREATE INDEX `idx_subjects_dept` ON `subjects` (`department`);
CREATE INDEX `idx_subjects_semester` ON `subjects` (`semester_id`);

-- -----------------------------------------------------------------------------
-- 4. Students Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `students` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `roll_number` VARCHAR(30) NOT NULL COMMENT 'Unique identifier per organisation',
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(20) NULL,
    `date_of_birth` DATE NOT NULL,
    `gender` ENUM('Male', 'Female', 'Other') NOT NULL,
    `current_semester_id` INT NULL,
    `enrollment_date` DATE NOT NULL,
    `status` ENUM('Active', 'Inactive', 'Suspended', 'Graduated') NOT NULL DEFAULT 'Active',
    `address` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `uq_students_org_roll` UNIQUE (`organisation_id`, `roll_number`),
    CONSTRAINT `uq_students_org_email` UNIQUE (`organisation_id`, `email`),
    CONSTRAINT `fk_students_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_students_semester` FOREIGN KEY (`current_semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_students_org` ON `students` (`organisation_id`);
CREATE INDEX `idx_students_roll` ON `students` (`roll_number`);
CREATE INDEX `idx_students_name` ON `students` (`last_name`, `first_name`);
CREATE INDEX `idx_students_status` ON `students` (`status`);
CREATE INDEX `idx_students_current_sem` ON `students` (`current_semester_id`);

-- -----------------------------------------------------------------------------
-- 5. Student Subject Registrations (Junction Table for Enrollment)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `student_subjects` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `semester_id` INT NOT NULL,
    `enrolled_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `uq_student_subject_sem` UNIQUE (`student_id`, `subject_id`, `semester_id`),
    CONSTRAINT `fk_ss_student` FOREIGN KEY (`student_id`)
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_ss_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_ss_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_ss_student` ON `student_subjects` (`student_id`);
CREATE INDEX `idx_ss_subject` ON `student_subjects` (`subject_id`);

-- -----------------------------------------------------------------------------
-- 6. Faculty Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `faculty` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `faculty_code` VARCHAR(30) NOT NULL,
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(20) NULL,
    `department` VARCHAR(100) NOT NULL,
    `designation` VARCHAR(100) NOT NULL DEFAULT 'Lecturer',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `uq_faculty_org_code` UNIQUE (`organisation_id`, `faculty_code`),
    CONSTRAINT `uq_faculty_org_email` UNIQUE (`organisation_id`, `email`),
    CONSTRAINT `fk_faculty_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_faculty_org` ON `faculty` (`organisation_id`);
CREATE INDEX `idx_faculty_code` ON `faculty` (`faculty_code`);
CREATE INDEX `idx_faculty_dept` ON `faculty` (`department`);

-- -----------------------------------------------------------------------------
-- 7. Faculty Subject Assignments
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `faculty_subjects` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `faculty_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `semester_id` INT NOT NULL,
    `assigned_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `uq_faculty_subject_sem` UNIQUE (`faculty_id`, `subject_id`, `semester_id`),
    CONSTRAINT `fk_fs_faculty` FOREIGN KEY (`faculty_id`)
        REFERENCES `faculty` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_fs_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_fs_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_fs_faculty` ON `faculty_subjects` (`faculty_id`);
CREATE INDEX `idx_fs_subject` ON `faculty_subjects` (`subject_id`);

-- -----------------------------------------------------------------------------
-- 8. Users Table (Authentication & RBAC)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `username` VARCHAR(80) NOT NULL UNIQUE,
    `email` VARCHAR(120) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` VARCHAR(50) NOT NULL DEFAULT 'Student' COMMENT 'Super Admin, Admin, Organisation, Faculty, Student',
    `student_id` INT NULL,
    `faculty_id` INT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_users_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_users_student` FOREIGN KEY (`student_id`)
        REFERENCES `students` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_users_faculty` FOREIGN KEY (`faculty_id`)
        REFERENCES `faculty` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_users_org` ON `users` (`organisation_id`);
CREATE INDEX `idx_users_role` ON `users` (`role`);
CREATE INDEX `idx_users_username` ON `users` (`username`);

-- -----------------------------------------------------------------------------
-- 9. Marks Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `marks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `student_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `semester_id` INT NOT NULL,
    `exam_type` ENUM('Quiz', 'Assignment', 'Midterm', 'Final', 'Practical') NOT NULL,
    `marks_obtained` DECIMAL(5, 2) NOT NULL,
    `max_marks` DECIMAL(5, 2) NOT NULL DEFAULT 100.00,
    `remarks` VARCHAR(255) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `chk_marks_positive` CHECK (`marks_obtained` >= 0 AND `max_marks` > 0),
    CONSTRAINT `chk_marks_valid` CHECK (`marks_obtained` <= `max_marks`),
    CONSTRAINT `uq_student_subject_exam` UNIQUE (`student_id`, `subject_id`, `semester_id`, `exam_type`),
    CONSTRAINT `fk_marks_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_marks_student` FOREIGN KEY (`student_id`)
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_marks_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_marks_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_marks_org` ON `marks` (`organisation_id`);
CREATE INDEX `idx_marks_student_subject` ON `marks` (`student_id`, `subject_id`);
CREATE INDEX `idx_marks_exam_type` ON `marks` (`exam_type`);

-- -----------------------------------------------------------------------------
-- 10. Attendance Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `attendance` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `student_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `date` DATE NOT NULL,
    `status` ENUM('Present', 'Absent', 'Late', 'Excused') NOT NULL DEFAULT 'Present',
    `remarks` VARCHAR(255) NULL,
    `session_id` INT NULL,
    `verified_lat` DECIMAL(10, 8) NULL,
    `verified_lng` DECIMAL(11, 8) NULL,
    `verified_accuracy` DECIMAL(8, 2) NULL,
    `distance_from_campus` DECIMAL(8, 2) NULL,
    `verified_at` VARCHAR(50) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `uq_student_subject_date` UNIQUE (`student_id`, `subject_id`, `date`),
    CONSTRAINT `fk_att_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_att_student` FOREIGN KEY (`student_id`)
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_att_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_att_org` ON `attendance` (`organisation_id`);
CREATE INDEX `idx_att_student_subject` ON `attendance` (`student_id`, `subject_id`);
CREATE INDEX `idx_att_date` ON `attendance` (`date`);
CREATE INDEX `idx_att_status` ON `attendance` (`status`);

-- -----------------------------------------------------------------------------
-- 11. Campus Settings Table (GPS & Institution Config)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `campus_settings` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `setting_key` VARCHAR(100) NOT NULL,
    `setting_value` TEXT NOT NULL,
    `description` VARCHAR(255) NULL,
    `updated_by` INT NULL,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `uq_campus_settings_org_key` UNIQUE (`organisation_id`, `setting_key`),
    CONSTRAINT `fk_cs_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_cs_org` ON `campus_settings` (`organisation_id`);

-- -----------------------------------------------------------------------------
-- 12. Attendance Sessions Table (GPS Session Verification)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `attendance_sessions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `organisation_id` INT NOT NULL DEFAULT 1,
    `subject_id` INT NOT NULL,
    `faculty_id` INT NOT NULL,
    `semester_id` INT NOT NULL,
    `session_date` DATE NOT NULL,
    `start_time` TIME NOT NULL,
    `end_time` TIME NOT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_by` INT NOT NULL,
    `faculty_lat` DECIMAL(10, 8) NULL,
    `faculty_lng` DECIMAL(11, 8) NULL,
    `faculty_accuracy` DECIMAL(8, 2) NULL,
    `notes` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `uq_att_session_slot` UNIQUE (`subject_id`, `faculty_id`, `session_date`, `start_time`),
    CONSTRAINT `fk_as_org` FOREIGN KEY (`organisation_id`)
        REFERENCES `organisations` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_as_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_as_faculty` FOREIGN KEY (`faculty_id`)
        REFERENCES `faculty` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_as_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_as_org` ON `attendance_sessions` (`organisation_id`);
CREATE INDEX `idx_as_active` ON `attendance_sessions` (`is_active`);
