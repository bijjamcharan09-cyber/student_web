-- =============================================================================
-- Production Student Management System (SMS) Schema
-- Database: MySQL 8.0+
-- Normalization: 3NF (Third Normal Form)
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `student_management_db`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `student_management_db`;

-- Drop tables in reverse foreign key order for clean resets
DROP TABLE IF EXISTS `attendance`;
DROP TABLE IF EXISTS `marks`;
DROP TABLE IF EXISTS `student_subjects`;
DROP TABLE IF EXISTS `students`;
DROP TABLE IF EXISTS `subjects`;
DROP TABLE IF EXISTS `semesters`;

-- -----------------------------------------------------------------------------
-- 1. Semesters Table
-- -----------------------------------------------------------------------------
CREATE TABLE `semesters` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(50) NOT NULL UNIQUE COMMENT 'e.g., Fall 2025 or Semester 1',
    `semester_number` TINYINT UNSIGNED NOT NULL COMMENT '1 to 12',
    `academic_year` VARCHAR(20) NOT NULL COMMENT 'e.g., 2025-2026',
    `start_date` DATE NOT NULL,
    `end_date` DATE NOT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `chk_semester_dates` CHECK (`start_date` <= `end_date`),
    CONSTRAINT `chk_semester_number` CHECK (`semester_number` >= 1 AND `semester_number` <= 12)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_semesters_active` ON `semesters` (`is_active`);
CREATE INDEX `idx_semesters_year` ON `semesters` (`academic_year`);

-- -----------------------------------------------------------------------------
-- 2. Subjects Table
-- -----------------------------------------------------------------------------
CREATE TABLE `subjects` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `subject_code` VARCHAR(20) NOT NULL UNIQUE COMMENT 'e.g., CS101, MATH201',
    `name` VARCHAR(100) NOT NULL,
    `credits` DECIMAL(3, 1) NOT NULL DEFAULT 3.0,
    `department` VARCHAR(100) NOT NULL,
    `semester_id` INT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `chk_credits_range` CHECK (`credits` > 0 AND `credits` <= 12),
    CONSTRAINT `fk_subjects_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_subjects_code` ON `subjects` (`subject_code`);
CREATE INDEX `idx_subjects_dept` ON `subjects` (`department`);
CREATE INDEX `idx_subjects_semester` ON `subjects` (`semester_id`);

-- -----------------------------------------------------------------------------
-- 3. Students Table
-- -----------------------------------------------------------------------------
CREATE TABLE `students` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `roll_number` VARCHAR(30) NOT NULL UNIQUE COMMENT 'Unique identifier across the institution',
    `first_name` VARCHAR(50) NOT NULL,
    `last_name` VARCHAR(50) NOT NULL,
    `email` VARCHAR(100) NOT NULL UNIQUE,
    `phone` VARCHAR(20) NULL,
    `date_of_birth` DATE NOT NULL,
    `gender` ENUM('Male', 'Female', 'Other') NOT NULL,
    `current_semester_id` INT NULL,
    `enrollment_date` DATE NOT NULL,
    `status` ENUM('Active', 'Inactive', 'Suspended', 'Graduated') NOT NULL DEFAULT 'Active',
    `address` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_students_semester` FOREIGN KEY (`current_semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_students_roll` ON `students` (`roll_number`);
CREATE INDEX `idx_students_email` ON `students` (`email`);
CREATE INDEX `idx_students_name` ON `students` (`last_name`, `first_name`);
CREATE INDEX `idx_students_status` ON `students` (`status`);
CREATE INDEX `idx_students_current_sem` ON `students` (`current_semester_id`);

-- -----------------------------------------------------------------------------
-- 4. Student Subject Registrations (Junction Table for Enrollment)
-- -----------------------------------------------------------------------------
CREATE TABLE `student_subjects` (
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
-- 5. Marks Table
-- -----------------------------------------------------------------------------
CREATE TABLE `marks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
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
    CONSTRAINT `fk_marks_student` FOREIGN KEY (`student_id`)
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_marks_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_marks_semester` FOREIGN KEY (`semester_id`)
        REFERENCES `semesters` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_marks_student_subject` ON `marks` (`student_id`, `subject_id`);
CREATE INDEX `idx_marks_exam_type` ON `marks` (`exam_type`);

-- -----------------------------------------------------------------------------
-- 6. Attendance Table
-- -----------------------------------------------------------------------------
CREATE TABLE `attendance` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `subject_id` INT NOT NULL,
    `date` DATE NOT NULL,
    `status` ENUM('Present', 'Absent', 'Late', 'Excused') NOT NULL DEFAULT 'Present',
    `remarks` VARCHAR(255) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `uq_student_subject_date` UNIQUE (`student_id`, `subject_id`, `date`),
    CONSTRAINT `fk_att_student` FOREIGN KEY (`student_id`)
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_att_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX `idx_att_student_subject` ON `attendance` (`student_id`, `subject_id`);
CREATE INDEX `idx_att_date` ON `attendance` (`date`);
CREATE INDEX `idx_att_status` ON `attendance` (`status`);
