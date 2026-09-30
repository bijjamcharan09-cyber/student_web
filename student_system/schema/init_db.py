"""
Database initialization script for Student Management System.
Executes schema.sql and optionally seed.sql against the configured MySQL server.
"""

import sys
import argparse
from pathlib import Path
import pymysql
from pymysql.constants import CLIENT

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config


def parse_sql_statements(sql_file_path: Path):
    """Read an SQL file and split it into executable statements."""
    with open(sql_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    statements = []
    current_stmt = []
    for line in content.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("--") or trimmed.startswith("/*"):
            continue
        current_stmt.append(line)
        if trimmed.endswith(";"):
            statements.append("\n".join(current_stmt))
            current_stmt = []
    return statements


def init_database(seed: bool = False):
    """Initialize database tables and optionally seed test data."""
    print("=" * 60)
    print("Initializing Student Management System Database")
    print("=" * 60)
    print(f"Host: {Config.DB_HOST}:{Config.DB_PORT}")
    print(f"User: {Config.DB_USER}")
    print(f"Target Database: {Config.DB_NAME}")

    schema_file = PROJECT_ROOT / "schema" / "schema.sql"
    seed_file = PROJECT_ROOT / "schema" / "seed.sql"

    if not schema_file.exists():
        print(f"Error: schema file not found at {schema_file}")
        sys.exit(1)

    try:
        # First connect without specifying DB to ensure it exists
        conn = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            charset=Config.DB_CHARSET,
            client_flag=CLIENT.MULTI_STATEMENTS,
            autocommit=True,
        )
        print("Connected to MySQL server successfully.")

        with conn.cursor() as cursor:
            try:
                print(f"Attempting to create database '{Config.DB_NAME}' if not exists...")
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            except pymysql.MySQLError as e:
                err_no = getattr(e, "args", [None])[0]
                if err_no == 1044:
                    print(f"\n[Note] User '{Config.DB_USER}' does not have global 'CREATE DATABASE' privilege.")
                    print(f"Checking if database '{Config.DB_NAME}' already exists and is accessible...")
                else:
                    raise

            try:
                cursor.execute(f"USE `{Config.DB_NAME}`;")
            except pymysql.MySQLError as e:
                err_no = getattr(e, "args", [None])[0]
                if err_no == 1044 or err_no == 1049:
                    print(f"\n[Permission Error] User '{Config.DB_USER}' cannot access '{Config.DB_NAME}'.")
                    print("\nTo grant required permissions, run this in your MySQL root console:")
                    print("----------------------------------------------------------------------")
                    print(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}`;")
                    print(f"GRANT ALL PRIVILEGES ON `{Config.DB_NAME}`.* TO '{Config.DB_USER}'@'localhost';")
                    print("FLUSH PRIVILEGES;")
                    print("----------------------------------------------------------------------")
                    print("Or temporarily change DB_USER in your .env to 'root' to run initialization.")
                    sys.exit(1)
                else:
                    raise

            print(f"Executing schema from {schema_file.name}...")
            statements = parse_sql_statements(schema_file)
            for stmt in statements:
                stmt_clean = stmt.strip()
                # Skip CREATE DATABASE or USE statements since we are already inside the target DB
                if stmt_clean.upper().startswith("CREATE DATABASE") or stmt_clean.upper().startswith("USE "):
                    continue
                if stmt_clean:
                    cursor.execute(stmt_clean)
            print("Database schema created successfully.")

            if seed:
                if not seed_file.exists():
                    print(f"Seed file not found at {seed_file}")
                else:
                    print(f"Seeding database with sample data from {seed_file.name}...")
                    seed_statements = parse_sql_statements(seed_file)
                    for stmt in seed_statements:
                        stmt_clean = stmt.strip()
                        if stmt_clean.upper().startswith("USE "):
                            continue
                        if stmt_clean:
                            cursor.execute(stmt_clean)
                    print("Sample seed data inserted successfully.")

        conn.close()
        print("=" * 60)
        print("Database initialization complete!")
        print("=" * 60)

    except pymysql.MySQLError as e:
        print(f"\n[Database Error] Could not initialize database: {e}")
        print("Please check your MySQL service and credentials in .env.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Student Management System MySQL DB")
    parser.add_argument("--seed", action="store_true", help="Populate database with sample seed data")
    args = parser.parse_args()
    init_database(seed=args.seed)