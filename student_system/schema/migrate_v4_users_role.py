"""
Idempotent Database Migration Script: V4 Users Role Column Expansion
Modifies `users.role` from restrictive `ENUM('Admin', 'Faculty', 'Student')`
to `VARCHAR(50)` to support `Organisation` (and `Super Admin`) roles.
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
        print("Checking column type of `users`.`role`...")
        cur.execute("""
            SELECT COLUMN_TYPE 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = 'role'
        """, (Config.DB_NAME,))
        res = cur.fetchone()
        current_type = res[0] if res else ""
        print(f"Current `users`.`role` type: {current_type}")

        if "enum" in current_type.lower():
            print("Altering `users`.`role` to VARCHAR(50) NOT NULL DEFAULT 'Student'...")
            cur.execute("""
                ALTER TABLE `users` 
                MODIFY COLUMN `role` VARCHAR(50) NOT NULL DEFAULT 'Student' 
                COMMENT 'Super Admin, Admin, Organisation, Faculty, Student';
            """)
            conn.commit()
            print("Successfully updated `users`.`role` to VARCHAR(50)!")
        else:
            print("`users`.`role` is already non-enum/VARCHAR. No alteration needed.")

    except Exception as e:
        conn.rollback()
        print(f"ERROR applying migration: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
