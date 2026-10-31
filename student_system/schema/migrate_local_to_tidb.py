"""
Migration Script: Local MySQL to TiDB Cloud
Migrates all local database records (organisations, semesters, subjects, students,
users, marks, faculty, attendance, campus_settings) into TiDB Cloud.
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Set
import pymysql

# Set project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from app.db import get_connection

# Local MySQL credentials
LOCAL_DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "student_app",
    "password": r";7kWAGd+1uBs_3",
    "database": "student_management_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# Tables in strict foreign-key dependency order
TABLES_ORDER = [
    "organisations",
    "semesters",
    "subjects",
    "students",
    "student_subjects",
    "faculty",
    "faculty_subjects",
    "users",
    "marks",
    "campus_settings",
    "attendance_sessions",
    "attendance",
]

BACKUP_JSON_PATH = Path(r"C:\Users\bijja\backup_sms_migration.json")


def get_local_connection():
    """Connect to the source local MySQL instance."""
    try:
        return pymysql.connect(**LOCAL_DB_CONFIG)
    except pymysql.MySQLError as e:
        print(f"[Warning] Failed to connect with student_app: {e}")
        # Try root with blank or env password
        alt_config = LOCAL_DB_CONFIG.copy()
        alt_config["user"] = "root"
        alt_config["password"] = os.getenv("LOCAL_DB_PASSWORD", "")
        return pymysql.connect(**alt_config)


def get_table_columns(cursor, table_name: str) -> List[str]:
    """Retrieve list of column names for a given table."""
    cursor.execute(f"DESCRIBE `{table_name}`")
    return [row["Field"] for row in cursor.fetchall()]


def migrate_data():
    print("=" * 70)
    print("MIGRATING LOCAL MYSQL RECORDS TO TIDB CLOUD")
    print("=" * 70)
    print(f"Source : Local MySQL ({LOCAL_DB_CONFIG['host']}:{LOCAL_DB_CONFIG['port']}/{LOCAL_DB_CONFIG['database']})")
    print(f"Target : TiDB Cloud ({Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME})")
    print("=" * 70)

    # Load backup JSON if available for supplemental records
    backup_data: Dict[str, List[Dict[str, Any]]] = {}
    if BACKUP_JSON_PATH.exists():
        try:
            with open(BACKUP_JSON_PATH, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
            print(f"[Info] Supplemental backup JSON loaded from {BACKUP_JSON_PATH.name}")
        except Exception as e:
            print(f"[Notice] Could not parse backup JSON: {e}")

    try:
        local_conn = get_local_connection()
        print("Connected to local MySQL successfully.")
    except Exception as e:
        print(f"[Error] Could not connect to local MySQL: {e}")
        sys.exit(1)

    try:
        tidb_conn = get_connection()
        print("Connected to TiDB Cloud successfully (Verified TLS).")
    except Exception as e:
        print(f"[Error] Could not connect to TiDB Cloud: {e}")
        local_conn.close()
        sys.exit(1)

    results: Dict[str, Dict[str, int]] = {}

    try:
        with local_conn.cursor() as loc_cur, tidb_conn.cursor() as tidb_cur:
            # Disable foreign key checks temporarily in destination to prevent ordering deadlocks
            tidb_cur.execute("SET FOREIGN_KEY_CHECKS = 0;")

            for table in TABLES_ORDER:
                print(f"\n--- Migrating Table: `{table}` ---")
                target_columns = get_table_columns(tidb_cur, table)
                target_col_set = set(target_columns)

                # Fetch rows from local MySQL
                loc_cur.execute(f"SELECT * FROM `{table}`")
                local_rows = loc_cur.fetchall()
                print(f"  Source rows found in local MySQL: {len(local_rows)}")

                # Check if backup JSON has additional unique records (by primary key 'id')
                known_ids: Set[Any] = {r.get("id") for r in local_rows if "id" in r}
                supplemental_rows = []
                if table in backup_data:
                    for b_row in backup_data[table]:
                        if b_row.get("id") not in known_ids:
                            supplemental_rows.append(b_row)
                            known_ids.add(b_row.get("id"))
                if supplemental_rows:
                    print(f"  Supplemental rows merged from backup: {len(supplemental_rows)}")

                all_rows = list(local_rows) + supplemental_rows
                if not all_rows:
                    print(f"  No records to migrate for `{table}`.")
                    results[table] = {"source": 0, "migrated": 0}
                    continue

                migrated_count = 0
                for row in all_rows:
                    # Filter and prepare row dict for target columns
                    clean_row: Dict[str, Any] = {}
                    for col in target_columns:
                        if col in row:
                            clean_row[col] = row[col]
                        elif col == "organisation_id":
                            # Default to organisation 1 (VREC) if column was missing in source
                            clean_row["organisation_id"] = 1
                        else:
                            clean_row[col] = None

                    # Construct upsert query (INSERT ... ON DUPLICATE KEY UPDATE)
                    cols = list(clean_row.keys())
                    col_names = ", ".join([f"`{c}`" for c in cols])
                    placeholders = ", ".join(["%s"] * len(cols))
                    updates = ", ".join([f"`{c}` = VALUES(`{c}`)" for c in cols if c != "id"])

                    sql = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates};"
                    tidb_cur.execute(sql, tuple(clean_row[c] for c in cols))
                    migrated_count += 1

                tidb_conn.commit()
                print(f"  [OK] Successfully migrated/upserted {migrated_count} records into TiDB `{table}`.")
                results[table] = {"source": len(all_rows), "migrated": migrated_count}

            # Re-enable foreign key checks
            tidb_cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
            tidb_conn.commit()

        print("\n" + "=" * 70)
        print("MIGRATION SUMMARY")
        print("=" * 70)
        print(f"{'Table Name':<25} | {'Source Rows':<12} | {'TiDB Migrated':<12}")
        print("-" * 55)
        for t, res in results.items():
            print(f"{t:<25} | {res['source']:<12} | {res['migrated']:<12}")
        print("=" * 70)

        # Verification query directly on TiDB
        print("\n--- Verifying Live TiDB Cloud Records ---")
        with tidb_conn.cursor() as cur:
            cur.execute("SELECT id, name, code, status FROM organisations")
            orgs = cur.fetchall()
            print(f"\nOrganisations ({len(orgs)}):")
            for o in orgs:
                print(f"  ID {o['id']}: {o['name']} ({o['code']}) - {o['status']}")

            cur.execute("SELECT id, roll_number, first_name, last_name, email, organisation_id FROM students")
            students = cur.fetchall()
            print(f"\nStudents ({len(students)}):")
            for s in students:
                print(f"  ID {s['id']}: {s['roll_number']} - {s['first_name']} {s['last_name']} ({s['email']}) [Org: {s['organisation_id']}]")

            cur.execute("SELECT id, username, email, role, organisation_id FROM users")
            users = cur.fetchall()
            print(f"\nUsers ({len(users)}):")
            for u in users:
                print(f"  ID {u['id']}: {u['username']} ({u['email']}) - Role: {u['role']} [Org: {u['organisation_id']}]")

            cur.execute("SELECT COUNT(*) as cnt FROM marks")
            print(f"\nMarks count: {cur.fetchone()['cnt']} rows")

            cur.execute("SELECT COUNT(*) as cnt FROM subjects")
            print(f"Subjects count: {cur.fetchone()['cnt']} rows")

            cur.execute("SELECT COUNT(*) as cnt FROM semesters")
            print(f"Semesters count: {cur.fetchone()['cnt']} rows")

            cur.execute("SELECT COUNT(*) as cnt FROM campus_settings")
            print(f"Campus Settings count: {cur.fetchone()['cnt']} rows")

    except Exception as e:
        print(f"\n[Migration Error] Migration failed: {e}")
        tidb_conn.rollback()
        raise
    finally:
        local_conn.close()
        tidb_conn.close()


if __name__ == "__main__":
    migrate_data()
