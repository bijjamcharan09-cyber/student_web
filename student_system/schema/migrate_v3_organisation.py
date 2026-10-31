"""
Idempotent Database Migration Script: V3 Organisation-Level Access Control
Applies:
1. `organisations` table creation
2. Default organisation insertion (VREC - Vijay Rural Engineering College)
3. `organisation_id` column addition with foreign key constraints to:
   - users, students, faculty, subjects, semesters, marks, attendance, attendance_sessions
4. Verification of data consistency and record preservation
"""

import sys
import pymysql

sys.path.insert(0, r"C:\Users\bijja\student_web\student_system")
from config import Config


def run_migration():
    print("Connecting to database...")
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        autocommit=False,
    )
    cur = conn.cursor()

    try:
        # 1. Create organisations table
        print("Creating organisations table if not exists...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `organisations` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `name` VARCHAR(150) NOT NULL,
                `code` VARCHAR(50) NOT NULL UNIQUE,
                `status` VARCHAR(20) NOT NULL DEFAULT 'Active',
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 2. Insert default organisation
        print("Ensuring default organisation (id=1, VREC) exists...")
        cur.execute("""
            INSERT INTO `organisations` (`id`, `name`, `code`, `status`)
            VALUES (1, 'Vijay Rural Engineering College', 'VREC', 'Active')
            ON DUPLICATE KEY UPDATE `name` = VALUES(`name`), `status` = VALUES(`status`);
        """)

        # 3. Add organisation_id to target tables
        tables = [
            "users",
            "students",
            "faculty",
            "subjects",
            "semesters",
            "marks",
            "attendance",
            "attendance_sessions",
        ]

        for table in tables:
            cur.execute(f"DESCRIBE `{table}`")
            cols = [r[0] for r in cur.fetchall()]
            if "organisation_id" not in cols:
                print(f"Adding `organisation_id` column to table `{table}`...")
                cur.execute(f"""
                    ALTER TABLE `{table}`
                    ADD COLUMN `organisation_id` INT NOT NULL DEFAULT 1;
                """)
                cur.execute(f"""
                    ALTER TABLE `{table}`
                    ADD INDEX `idx_{table}_organisation_id` (`organisation_id`);
                """)
                # Add foreign key constraint
                fk_name = f"fk_{table}_organisation"
                cur.execute(f"""
                    ALTER TABLE `{table}`
                    ADD CONSTRAINT `{fk_name}`
                    FOREIGN KEY (`organisation_id`) REFERENCES `organisations` (`id`)
                    ON DELETE RESTRICT ON UPDATE CASCADE;
                """)
            else:
                print(f"Table `{table}` already has `organisation_id`.")

        conn.commit()
        print("\nMigration V3 successfully applied!")

        # Verification check
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM `{table}` WHERE `organisation_id` = 1")
            count = cur.fetchone()[0]
            print(f"  Verified `{table}`: {count} rows associated with organisation_id=1")

    except Exception as e:
        conn.rollback()
        print(f"ERROR applying migration: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
