"""
Database initialization script for Student Management System.
Supports TiDB Cloud Starter with verified TLS and local MySQL environments.
Executes schema.sql and optionally seed.sql against the configured database.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Union
import pymysql

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from app.db import get_connection


def parse_sql_statements(sql_source: Union[Path, str]) -> List[str]:
    """
    Parse an SQL script file or string into individual executable statements.
    
    Robustly handles:
    - Multi-line statements
    - Single-line comments (-- and #)
    - Multi-line block comments (/* ... */)
    - Semicolons inside single-quoted strings ('...')
    - Semicolons inside double-quoted strings ("...")
    - Semicolons inside backtick identifier quotes (`...`)
    - Escape sequences (\\', \\", \\\\, etc.)
    """
    if isinstance(sql_source, Path) or (isinstance(sql_source, str) and "\n" not in sql_source and Path(sql_source).is_file()):
        with open(sql_source, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = str(sql_source)

    statements: List[str] = []
    current: List[str] = []
    in_single_quote = False
    in_double_quote = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False

    i = 0
    n = len(content)
    while i < n:
        c = content[i]
        next_c = content[i + 1] if i + 1 < n else ""

        # Handling single-line comments (-- or #)
        if in_line_comment:
            if c == "\n":
                in_line_comment = False
                current.append("\n")
            i += 1
            continue

        # Handling multi-line comments (/* ... */)
        if in_block_comment:
            if c == "*" and next_c == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        # Handling single-quoted string ('...')
        if in_single_quote:
            current.append(c)
            if c == "\\" and next_c:
                current.append(next_c)
                i += 2
                continue
            elif c == "'":
                if next_c == "'":  # SQL escaped single quote ('')
                    current.append(next_c)
                    i += 2
                    continue
                else:
                    in_single_quote = False
            i += 1
            continue

        # Handling double-quoted string ("...")
        if in_double_quote:
            current.append(c)
            if c == "\\" and next_c:
                current.append(next_c)
                i += 2
                continue
            elif c == '"':
                if next_c == '"':  # SQL escaped double quote ("")
                    current.append(next_c)
                    i += 2
                    continue
                else:
                    in_double_quote = False
            i += 1
            continue

        # Handling backticks (`...`)
        if in_backtick:
            current.append(c)
            if c == "`":
                if next_c == "`":
                    current.append(next_c)
                    i += 2
                    continue
                else:
                    in_backtick = False
            i += 1
            continue

        # Check comment starts
        if c == "-" and next_c == "-":
            in_line_comment = True
            i += 2
            continue
        if c == "#":
            in_line_comment = True
            i += 1
            continue
        if c == "/" and next_c == "*":
            in_block_comment = True
            i += 2
            continue

        # Check quote starts
        if c == "'":
            in_single_quote = True
            current.append(c)
            i += 1
            continue
        if c == '"':
            in_double_quote = True
            current.append(c)
            i += 1
            continue
        if c == "`":
            in_backtick = True
            current.append(c)
            i += 1
            continue

        # Check statement delimiter
        if c == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(c)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def execute_sql_file(cursor, conn, file_path: Path, label: str) -> Tuple[int, int]:
    """Execute statements from an SQL file with tracking and error handling."""
    if not file_path.exists():
        raise FileNotFoundError(f"{label} file not found at {file_path}")

    print(f"\nParsing {label} from {file_path.name}...")
    statements = parse_sql_statements(file_path)
    total = len(statements)
    print(f"Found {total} statement(s) to process.")

    executed_count = 0
    skipped_count = 0

    for idx, stmt in enumerate(statements, 1):
        clean_stmt = stmt.strip()
        if not clean_stmt:
            continue

        # Normalise uppercase leading token
        upper_stmt = clean_stmt.upper()

        # Connect directly to the configured DB, so skip CREATE DATABASE and USE
        if upper_stmt.startswith("CREATE DATABASE") or upper_stmt.startswith("USE "):
            first_line = clean_stmt.splitlines()[0][:70]
            print(f"[{idx}/{total}] [Info] Skipped ({first_line}) - Database already connected.")
            skipped_count += 1
            continue

        first_line = clean_stmt.splitlines()[0][:70]
        try:
            cursor.execute(clean_stmt)
            conn.commit()
            executed_count += 1
            print(f"[{idx}/{total}] [OK] {first_line}")
        except pymysql.MySQLError as err:
            err_no = getattr(err, "args", [None])[0] if err.args else None
            # Handle benign idempotent errors (table already exists: 1050, duplicate key/index: 1061)
            if err_no in (1050, 1061):
                err_msg = err.args[1] if len(err.args) > 1 else str(err)
                print(f"[{idx}/{total}] [Notice] Already exists ({err_no}): {err_msg}")
                skipped_count += 1
            else:
                conn.rollback()
                print(f"\n[Error] Execution failed at statement [{idx}/{total}]:")
                print(f"SQL: {clean_stmt}")
                print(f"Error Code {err_no}: {err}")
                raise

    return executed_count, skipped_count


def init_database(seed: bool = False):
    """Initialize database tables and optionally seed test data."""
    print("=" * 70)
    print("Initializing Student Management System Database")
    print("=" * 70)
    print(f"Target Host     : {Config.DB_HOST}:{Config.DB_PORT}")
    print(f"Database Name   : {Config.DB_NAME}")
    print(f"Database User   : {Config.DB_USER}")
    ssl_status = (
        f"Verified TLS (CA: {Config.DB_SSL.get('ca')})"
        if (Config.DB_SSL and Config.DB_SSL.get("ca"))
        else "Plain connection (no TLS CA configured)"
    )
    print(f"Security/TLS    : {ssl_status}")
    print("=" * 70)

    schema_file = PROJECT_ROOT / "schema" / "schema.sql"
    seed_file = PROJECT_ROOT / "schema" / "seed.sql"

    if not schema_file.exists():
        print(f"[Error] Schema file not found at: {schema_file}")
        sys.exit(1)

    conn = None
    cursor = None
    try:
        # Reuse existing verified application connection
        conn = get_connection()
        cursor = conn.cursor()
        print("Connected to target database successfully.")

        # Execute Schema
        schema_exec, schema_skip = execute_sql_file(cursor, conn, schema_file, "Schema")

        # Execute Seed if requested
        seed_exec, seed_skip = 0, 0
        if seed:
            if not seed_file.exists():
                print(f"\n[Notice] Seed file not found at {seed_file}. Seeding skipped.")
            else:
                seed_exec, seed_skip = execute_sql_file(cursor, conn, seed_file, "Seed Data")

        print("\n" + "=" * 70)
        print("Database initialization complete!")
        print(f"Schema statements : {schema_exec} executed, {schema_skip} skipped.")
        if seed and seed_file.exists():
            print(f"Seed statements   : {seed_exec} executed, {seed_skip} skipped.")
        print("=" * 70)

    except pymysql.MySQLError as e:
        print(f"\n[Database Error] Initialization failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Unexpected Error] Initialization failed: {e}")
        sys.exit(1)
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize Student Management System MySQL/TiDB Cloud DB"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Populate database with sample seed data if seed.sql exists",
    )
    args = parser.parse_args()
    init_database(seed=args.seed)
