"""
Database management module for Student Management System.
Provides thread-safe connection handling, parameterized query execution,
and ACID transaction management using PyMySQL.
"""

from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union
import pymysql
from pymysql.constants import CLIENT
from pymysql.cursors import DictCursor

from config import Config
from app.utils.exceptions import ConflictError, DatabaseError, ValidationError, NotFoundError

# Global hook for test mocking / dependency injection
_connection_override = None


def set_connection_override(conn_factory):
    """Set an override connection factory for testing."""
    global _connection_override
    _connection_override = conn_factory


def get_connection():
    """Obtain a new database connection configured with dictionary cursors."""
    global _connection_override
    if _connection_override is not None:
        return _connection_override()

    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset=Config.DB_CHARSET,
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=Config.DB_CONNECT_TIMEOUT,
            read_timeout=Config.DB_READ_TIMEOUT,
            write_timeout=Config.DB_WRITE_TIMEOUT,
        )
        return connection
    except pymysql.MySQLError as e:
        raise DatabaseError(f"Database connection error: {str(e)}")


def handle_mysql_error(e: pymysql.MySQLError):
    """Map MySQL error codes to domain exceptions."""
    err_no = getattr(e, "args", [None])[0] if e.args else None
    err_msg = str(e)

    if err_no == 1062:
        raise ConflictError(f"Unique constraint violation: {err_msg}")
    elif err_no == 1452:
        raise ValidationError(f"Referenced record does not exist: {err_msg}")
    elif err_no == 1451:
        raise ConflictError(f"Cannot delete record because related records depend on it: {err_msg}")
    else:
        raise DatabaseError(f"Database operation failed: {err_msg}")


@contextmanager
def transaction():
    """
    Context manager for atomic database transactions.
    Automatically commits on success or rolls back on exception.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except pymysql.MySQLError as e:
        conn.rollback()
        handle_mysql_error(e)
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def query_one(sql: str, params: Optional[Union[tuple, list, dict]] = None) -> Optional[Dict[str, Any]]:
    """Execute a read query and return a single row or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            result = cursor.fetchone()
            return result
    except pymysql.MySQLError as e:
        handle_mysql_error(e)
    finally:
        conn.close()


def query_all(sql: str, params: Optional[Union[tuple, list, dict]] = None) -> List[Dict[str, Any]]:
    """Execute a read query and return all matching rows."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            result = cursor.fetchall()
            return list(result) if result else []
    except pymysql.MySQLError as e:
        handle_mysql_error(e)
    finally:
        conn.close()


def execute_insert(sql: str, params: Optional[Union[tuple, list, dict]] = None) -> int:
    """Execute an INSERT statement and return the inserted row ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            row_id = cursor.lastrowid
        conn.commit()
        return row_id
    except pymysql.MySQLError as e:
        conn.rollback()
        handle_mysql_error(e)
    finally:
        conn.close()


def execute_update(sql: str, params: Optional[Union[tuple, list, dict]] = None) -> int:
    """Execute an UPDATE or DELETE statement and return affected rows count."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            affected = cursor.execute(sql, params or ())
        conn.commit()
        return affected
    except pymysql.MySQLError as e:
        conn.rollback()
        handle_mysql_error(e)
    finally:
        conn.close()
