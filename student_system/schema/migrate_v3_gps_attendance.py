"""
V3 Database Migration Script — GPS Attendance Sessions.

Creates three new structures:
  1. campus_settings   — configurable campus coordinates + geofence radius
  2. attendance_sessions — faculty-created sessions (subject/time-bounded)
  3. Adds session_id, verified_lat, verified_lng, verified_accuracy columns
     to the existing 'attendance' table (backward-compatible; NULLable).

Safety guarantees:
  - Uses CREATE TABLE IF NOT EXISTS everywhere.
  - Uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS (MySQL 8.0+ compatible).
  - Does NOT drop tables, alter existing columns, or delete rows.
  - Preserves all existing attendance records (session_id will be NULL for legacy rows).
"""

import sys
from pathlib import Path
import pymysql

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import Config


# ─────────────────────────────────────────────────────────────────────────────
# VREC campus coordinates — verified from official VREC website (vrec.ac.in)
# Address: Rochis Valley, Manikbhandar, NH-16, Borgaon, Nizamabad, Telangana 503003
# ─────────────────────────────────────────────────────────────────────────────
VREC_LAT = 18.9972
VREC_LNG = 78.2497
VREC_COLLEGE_NAME = "Vijay Rural Engineering College"
VREC_LOCATION_LABEL = "Nizamabad, Telangana, India"

V3_MIGRATION_SQL = [
    # ── 1. Campus Settings ────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `campus_settings` (
        `id`               INT AUTO_INCREMENT PRIMARY KEY,
        `setting_key`      VARCHAR(80)  NOT NULL UNIQUE,
        `setting_value`    VARCHAR(255) NOT NULL,
        `description`      VARCHAR(255) NULL,
        `updated_by`       INT NULL COMMENT 'users.id who last changed this setting',
        `updated_at`       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX `idx_campus_key` (`setting_key`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='Configurable campus GPS and attendance settings'
    """,

    # ── 2. Attendance Sessions ────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `attendance_sessions` (
        `id`              INT AUTO_INCREMENT PRIMARY KEY,
        `subject_id`      INT  NOT NULL,
        `faculty_id`      INT  NOT NULL,
        `semester_id`     INT  NOT NULL,
        `session_date`    DATE NOT NULL,
        `start_time`      DATETIME NOT NULL COMMENT 'Server-authoritative start (UTC stored, app converts)',
        `end_time`        DATETIME NOT NULL COMMENT 'Server-authoritative end',
        `is_active`       BOOLEAN  NOT NULL DEFAULT TRUE,
        `created_by`      INT      NOT NULL COMMENT 'users.id of the faculty user who created session',
        `faculty_lat`     DECIMAL(10,7) NULL COMMENT 'Faculty GPS lat when session was created',
        `faculty_lng`     DECIMAL(10,7) NULL COMMENT 'Faculty GPS lng when session was created',
        `faculty_accuracy` DECIMAL(8,2) NULL COMMENT 'Reported accuracy in metres',
        `notes`           VARCHAR(255) NULL,
        `created_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        `updated_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        CONSTRAINT `uq_session_subject_faculty_date_start`
            UNIQUE (`subject_id`, `faculty_id`, `session_date`, `start_time`),
        CONSTRAINT `chk_session_times` CHECK (`end_time` > `start_time`),
        CONSTRAINT `fk_as_subject`  FOREIGN KEY (`subject_id`)
            REFERENCES `subjects`  (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_as_faculty`  FOREIGN KEY (`faculty_id`)
            REFERENCES `faculty`   (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_as_semester` FOREIGN KEY (`semester_id`)
            REFERENCES `semesters` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        INDEX `idx_as_subject`      (`subject_id`),
        INDEX `idx_as_faculty`      (`faculty_id`),
        INDEX `idx_as_date`         (`session_date`),
        INDEX `idx_as_active`       (`is_active`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='Faculty-created time-bounded attendance sessions'
    """,
]

# These are individual ALTER TABLE statements — run conditionally after checking information_schema
# Tuples of (column_name, DDL_fragment)
ALTER_COLUMNS = [
    (
        "session_id",
        "INT NULL COMMENT 'Links to attendance_sessions.id (NULL for legacy records)'"
    ),
    (
        "verified_lat",
        "DECIMAL(10,7) NULL COMMENT 'Student GPS latitude at submission'"
    ),
    (
        "verified_lng",
        "DECIMAL(10,7) NULL COMMENT 'Student GPS longitude at submission'"
    ),
    (
        "verified_accuracy",
        "DECIMAL(8,2) NULL COMMENT 'Browser-reported GPS accuracy in metres'"
    ),
    (
        "distance_from_campus",
        "DECIMAL(8,2) NULL COMMENT 'Haversine distance from campus in metres (server-computed)'"
    ),
    (
        "verified_at",
        "DATETIME NULL COMMENT 'Server timestamp when attendance was recorded'"
    ),
]

# Index to add after columns exist
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS `idx_att_session` ON `attendance` (`session_id`)",
]

# Default campus_settings seed data
DEFAULT_SETTINGS = [
    ("campus_latitude",    str(VREC_LAT),    f"Campus GPS Latitude — {VREC_COLLEGE_NAME}"),
    ("campus_longitude",   str(VREC_LNG),    f"Campus GPS Longitude — {VREC_COLLEGE_NAME}"),
    ("campus_name",        VREC_COLLEGE_NAME, "College name"),
    ("campus_location",    VREC_LOCATION_LABEL, "Human-readable campus location"),
    ("geofence_radius_m",  "150",            "Geofence radius in metres (default 150m)"),
    ("max_gps_accuracy_m", "50",             "Reject GPS readings with accuracy > this (metres)"),
    ("attendance_enabled", "true",           "Master switch: enables/disables GPS attendance"),
]


def column_exists(cursor, table: str, column: str, db_name: str) -> bool:
    cursor.execute(
        """SELECT COUNT(*) AS cnt
           FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (db_name, table, column)
    )
    row = cursor.fetchone()
    return (row[0] if isinstance(row, tuple) else row["cnt"]) > 0


def fk_exists(cursor, table: str, constraint_name: str, db_name: str) -> bool:
    cursor.execute(
        """SELECT COUNT(*) AS cnt
           FROM information_schema.TABLE_CONSTRAINTS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
             AND CONSTRAINT_NAME = %s AND CONSTRAINT_TYPE = 'FOREIGN KEY'""",
        (db_name, table, constraint_name)
    )
    row = cursor.fetchone()
    return (row[0] if isinstance(row, tuple) else row["cnt"]) > 0


def run_migration():
    print("=" * 65)
    print("V3 Migration — GPS Attendance Sessions")
    print("=" * 65)
    print(f"Target DB: {Config.DB_NAME} on {Config.DB_HOST}:{Config.DB_PORT}")
    print()

    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset=Config.DB_CHARSET,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with conn.cursor() as cursor:

            # ── Step 1: CREATE TABLE statements ──────────────────────────────
            print("Step 1: Creating new tables (campus_settings, attendance_sessions)...")
            for stmt in V3_MIGRATION_SQL:
                s = stmt.strip()
                if s:
                    cursor.execute(s)
            print("  ✅  Tables created / already existed.")

            # ── Step 2: ALTER attendance table ───────────────────────────────
            print("\nStep 2: Adding new columns to 'attendance' table...")
            for col_name, col_ddl in ALTER_COLUMNS:
                if not column_exists(cursor, "attendance", col_name, Config.DB_NAME):
                    cursor.execute(
                        f"ALTER TABLE `attendance` ADD COLUMN `{col_name}` {col_ddl}"
                    )
                    print(f"  OK   Column '{col_name}' added.")
                else:
                    print(f"  --   Column '{col_name}' already existed — skipped.")

            # ── Step 3: Add FK from attendance.session_id → attendance_sessions.id ──
            print("\nStep 3: Adding foreign key for attendance.session_id...")
            if column_exists(cursor, "attendance", "session_id", Config.DB_NAME):
                fk_name = "fk_att_session"
                if not fk_exists(cursor, "attendance", fk_name, Config.DB_NAME):
                    cursor.execute(f"""
                        ALTER TABLE `attendance`
                        ADD CONSTRAINT `{fk_name}` FOREIGN KEY (`session_id`)
                            REFERENCES `attendance_sessions` (`id`)
                            ON DELETE SET NULL ON UPDATE CASCADE
                    """)
                    print(f"  ✅  Foreign key '{fk_name}' added.")
                else:
                    print(f"  ⚠️   Foreign key '{fk_name}' already existed — skipped.")
            else:
                print("  ⚠️   'session_id' column not found — FK skipped.")

            # ── Step 4: Add index ─────────────────────────────────────────────
            print("\nStep 4: Adding session index...")
            cursor.execute(
                """SELECT COUNT(*) AS cnt FROM information_schema.STATISTICS
                   WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'attendance'
                     AND INDEX_NAME = 'idx_att_session'""",
                (Config.DB_NAME,)
            )
            row = cursor.fetchone()
            cnt = row[0] if isinstance(row, tuple) else row["cnt"]
            if cnt == 0:
                cursor.execute(
                    "CREATE INDEX `idx_att_session` ON `attendance` (`session_id`)"
                )
                print("  OK   Index 'idx_att_session' created.")
            else:
                print("  --   Index 'idx_att_session' already existed — skipped.")

            # ── Step 5: Seed campus_settings ─────────────────────────────────
            print("\nStep 5: Seeding default campus_settings...")
            for key, value, description in DEFAULT_SETTINGS:
                cursor.execute(
                    "SELECT id FROM campus_settings WHERE setting_key = %s",
                    (key,)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        """INSERT INTO campus_settings (setting_key, setting_value, description)
                           VALUES (%s, %s, %s)""",
                        (key, value, description)
                    )
                    print(f"  ✅  Setting '{key}' = '{value}' inserted.")
                else:
                    print(f"  ⚠️   Setting '{key}' already exists — skipped.")

        print()
        print("=" * 65)
        print("V3 Migration Completed Successfully!")
        print(f"  Campus: {VREC_COLLEGE_NAME}")
        print(f"  Location: {VREC_LOCATION_LABEL}")
        print(f"  Latitude: {VREC_LAT}  |  Longitude: {VREC_LNG}")
        print(f"  Geofence: 150 m  |  Max GPS accuracy: 50 m")
        print()
        print("  All existing attendance records are preserved.")
        print("  New columns (session_id, verified_lat/lng) are NULL for legacy rows.")
        print("=" * 65)

    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
