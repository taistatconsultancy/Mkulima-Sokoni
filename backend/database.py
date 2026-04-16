"""
Database connection and utility functions for Neon Database
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.pool import PoolError
from contextlib import contextmanager
from config import Config
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_pool = None
_pool_lock = threading.Lock()
_pool_enabled = True


class DatabaseOverloadError(Exception):
    """Raised when transient DB saturation persists after retries."""


def _database_url_with_ssl(database_url):
    if not database_url:
        return database_url
    if 'sslmode' not in database_url.lower():
        if '?' in database_url:
            database_url += '&sslmode=require'
        else:
            database_url += '?sslmode=require'
    return database_url


def _get_connection_pool():
    """
    Lazy ThreadedConnectionPool for warm serverless / long-lived workers.
    Falls back to per-request connect if pool creation fails.
    """
    global _pool, _pool_enabled
    if not _pool_enabled:
        return None
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        database_url = Config.DATABASE_URL or os.getenv('DATABASE_URL')
        if not database_url:
            return None
        database_url = _database_url_with_ssl(database_url)
        try:
            min_conn = max(1, int(os.getenv('DB_POOL_MIN_CONN', '1')))
            max_conn = max(min_conn, int(os.getenv('DB_POOL_MAX_CONN', '20')))
            connect_timeout = max(2, int(os.getenv('DB_CONNECT_TIMEOUT_SEC', '8')))
            _pool = ThreadedConnectionPool(
                min_conn, max_conn, database_url, connect_timeout=connect_timeout
            )
            logger.info(
                'Database ThreadedConnectionPool ready (min=%s, max=%s)',
                min_conn,
                max_conn,
            )
            return _pool
        except Exception as e:
            logger.warning(
                'Connection pool unavailable, using per-request connections: %s', e
            )
            _pool_enabled = False
            return None


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Uses a small connection pool when available; otherwise one-shot connect (Neon-friendly).
    """
    database_url = Config.DATABASE_URL or os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError(
            'DATABASE_URL is not set. Please configure it in environment variables.'
        )

    pool = _get_connection_pool()
    conn = None
    from_pool = False
    try:
        if pool:
            try:
                conn = pool.getconn()
                from_pool = True
            except PoolError as e:
                # Do not fail hard under polling bursts; use one-shot connect as fallback.
                logger.warning(
                    'Connection pool exhausted, falling back to direct connection: %s',
                    e,
                )
                conn = psycopg2.connect(
                    _database_url_with_ssl(database_url),
                    connect_timeout=max(2, int(os.getenv('DB_CONNECT_TIMEOUT_SEC', '8'))),
                )
        else:
            conn = psycopg2.connect(
                _database_url_with_ssl(database_url),
                connect_timeout=max(2, int(os.getenv('DB_CONNECT_TIMEOUT_SEC', '8'))),
            )
        yield conn
        conn.commit()
    except psycopg2.OperationalError as e:
        if conn:
            conn.rollback()
        logger.error(f'Database connection error: {str(e)}')
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f'Database error: {str(e)}')
        raise
    finally:
        if conn:
            if from_pool and pool:
                pool.putconn(conn)
            else:
                conn.close()


def get_db_cursor():
    """
    Get a database cursor with RealDictCursor for easier data access
    """
    url = Config.DATABASE_URL or os.getenv('DATABASE_URL')
    if not url:
        raise ValueError('DATABASE_URL is not set')
    conn = psycopg2.connect(
        _database_url_with_ssl(url),
        connect_timeout=10,
    )
    return conn, conn.cursor(cursor_factory=RealDictCursor)


def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """
    Execute a database query and return results
    RealDictRow objects are dict-like and can be accessed by column name
    """
    retries = max(0, int(os.getenv('DB_RETRY_ATTEMPTS', '2')))
    retry_delays = [0.1, 0.25, 0.4]
    last_error = None
    for attempt in range(retries + 1):
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)

                    if fetch_one:
                        result = cursor.fetchone()
                        return result
                    elif fetch_all:
                        results = cursor.fetchall()
                        return results if results else []
                    else:
                        return cursor.rowcount
        except (PoolError, psycopg2.OperationalError) as e:
            last_error = e
            msg = str(e).lower()
            overloaded = isinstance(e, PoolError) or 'connection pool exhausted' in msg
            if overloaded and attempt < retries:
                time.sleep(retry_delays[min(attempt, len(retry_delays) - 1)])
                continue
            if overloaded:
                logger.error('Database saturation after retries: %s', e)
                raise DatabaseOverloadError('Database is busy, please retry shortly.') from e
            logger.error(f'Database query error: {str(e)}')
            logger.error(f'Query: {query[:100]}...')
            raise
        except psycopg2.Error as e:
            logger.error(f'Database query error: {str(e)}')
            logger.error(f'Query: {query[:100]}...')
            raise
        except Exception as e:
            logger.error(f'Unexpected error in execute_query: {str(e)}')
            raise
    if last_error:
        raise last_error
