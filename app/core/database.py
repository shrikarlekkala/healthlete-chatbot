"""
database.py — Thread-safe connection pool with pgvector support
================================================================
Migrated from the original db.py. Now imports configuration from
app.core.config instead of reading os.getenv() directly.
"""

import logging
import threading
import time
from contextlib import contextmanager
from queue import Empty, Queue
from typing import Optional

import psycopg2
from pgvector.psycopg2 import register_vector

from app.core.config import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    DB_POOL_MIN, DB_POOL_MAX, DB_POOL_TIMEOUT,
)

log = logging.getLogger("healthlete.db")


class BlockingConnectionPool:
    """Thread-safe connection pool with queue-backed blocking checkout,
    health checks, and automatic pgvector registration."""

    def __init__(
        self,
        minconn: int = 2,
        maxconn: int = 20,
        timeout: float = 10.0,
        **conn_kwargs,
    ):
        self.minconn = max(1, minconn)
        self.maxconn = max(self.minconn, maxconn)
        self.timeout = timeout
        self.conn_kwargs = conn_kwargs
        self.queue: Queue = Queue(maxsize=self.maxconn)
        self.created_connections = 0
        self.pool_lock = threading.Lock()
        self.is_closed = False

        for _ in range(self.minconn):
            try:
                conn = self.create_new_connection()
                self.queue.put(conn)
            except Exception as e:
                log.warning("Could not pre-warm connection during pool init: %s", e)
                break

    def create_new_connection(self):
        conn = psycopg2.connect(**self.conn_kwargs)
        register_vector(conn)
        with self.pool_lock:
            self.created_connections += 1
        return conn

    def getconn(self, timeout: Optional[float] = None):
        if self.is_closed:
            raise RuntimeError("Database connection pool is closed.")

        timeout_val = self.timeout if timeout is None else timeout
        deadline = time.time() + timeout_val

        while time.time() < deadline:
            try:
                conn = self.queue.get_nowait()
                if not conn.closed:
                    return conn
                with self.pool_lock:
                    self.created_connections = max(0, self.created_connections - 1)
                continue
            except Empty:
                pass

            with self.pool_lock:
                if self.created_connections < self.maxconn:
                    try:
                        conn = psycopg2.connect(**self.conn_kwargs)
                        register_vector(conn)
                        self.created_connections += 1
                        return conn
                    except Exception as e:
                        log.error("Failed to create new database connection: %s", e)

            remaining = max(0.01, deadline - time.time())
            try:
                conn = self.queue.get(timeout=min(0.2, remaining))
                if conn.closed:
                    with self.pool_lock:
                        self.created_connections = max(0, self.created_connections - 1)
                    continue
                return conn
            except Empty:
                continue

        raise TimeoutError(
            f"Could not acquire database connection from pool within {timeout_val}s."
        )

    def putconn(self, conn, close: bool = False):
        if close or self.is_closed or conn.closed:
            try:
                conn.close()
            except Exception:
                pass
            with self.pool_lock:
                self.created_connections = max(0, self.created_connections - 1)
            return

        try:
            conn.rollback()
            self.queue.put_nowait(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            with self.pool_lock:
                self.created_connections = max(0, self.created_connections - 1)

    def closeall(self):
        with self.pool_lock:
            self.is_closed = True
        while not self.queue.empty():
            try:
                conn = self.queue.get_nowait()
                conn.close()
            except Exception:
                pass
        with self.pool_lock:
            self.created_connections = 0


global_pool: Optional[BlockingConnectionPool] = None
global_pool_lock = threading.Lock()


def init_db_pool(
    minconn: Optional[int] = None,
    maxconn: Optional[int] = None,
) -> BlockingConnectionPool:
    """Initializes the database connection pool (called on app startup)."""
    global global_pool
    with global_pool_lock:
        if global_pool is not None and not global_pool.is_closed:
            return global_pool

        min_c = minconn if minconn is not None else DB_POOL_MIN
        max_c = maxconn if maxconn is not None else DB_POOL_MAX

        log.info(
            "Initializing database connection pool (min=%d, max=%d) to %s:%d/%s",
            min_c, max_c, DB_HOST, DB_PORT, DB_NAME,
        )
        global_pool = BlockingConnectionPool(
            minconn=min_c,
            maxconn=max_c,
            timeout=DB_POOL_TIMEOUT,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        return global_pool


def get_db_pool() -> BlockingConnectionPool:
    """Returns the active database pool, lazily creating it if needed."""
    global global_pool
    if global_pool is None or global_pool.is_closed:
        return init_db_pool()
    return global_pool


def close_db_pool() -> None:
    """Gracefully closes all connections in the pool (called on app shutdown)."""
    global global_pool
    with global_pool_lock:
        if global_pool is not None and not global_pool.is_closed:
            log.info("Closing database connection pool.")
            global_pool.closeall()
            global_pool = None


@contextmanager
def get_db_connection():
    """Context manager for thread-safe database connection checkout.

    Guarantees:
    - Connection is returned to the pool even when exceptions occur.
    - Any active transaction is rolled back on error.
    - Stale connections are detected and replaced.
    """
    pool = get_db_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        if not conn.closed:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        pool.putconn(conn)
