"""Shared SQLite helper with WAL mode enabled.

Usage:
    from db_helper import get_connection

    with get_connection("state.db") as conn:
        conn.execute("SELECT ...")

Or for long-lived connections:
    from db_helper import setup_connection

    conn = setup_connection("state.db")
    # ... use conn ...
    conn.close()
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Union

PathLike = Union[str, Path]


@contextmanager
def get_connection(
    db_path: str | Path,
    *,
    timeout: float = 30.0,
    check_same_thread: bool = False,
    isolation_level: str | None = None,
    **kwargs,
) -> Generator[sqlite3.Connection, None, None]:
    """Get a SQLite connection with WAL journal mode enabled.

    WAL mode allows concurrent readers and one writer without
    'database is locked' errors.

    Parameters:
        db_path: Path to the SQLite database file.
        timeout: Seconds to wait before raising OperationalError on lock.
        check_same_thread: Allow connection to be used from multiple threads.
        isolation_level: Transaction isolation level (None = manual commits).

    Yields:
        A sqlite3.Connection with PRAGMA journal_mode=WAL set.
    """
    conn = sqlite3.connect(
        str(db_path),
        timeout=timeout,
        check_same_thread=check_same_thread,
        isolation_level=isolation_level,
        **kwargs,
    )
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
    finally:
        conn.close()


def setup_connection(
    db_path: str | Path,
    *,
    timeout: float = 30.0,
    check_same_thread: bool = False,
    isolation_level: str | None = None,
    row_factory: type | None = sqlite3.Row,
    **kwargs,
) -> sqlite3.Connection:
    """Create and configure a SQLite connection with WAL mode.

    For long-lived connections (e.g., held by a class instance).
    The caller is responsible for closing the connection.

    Parameters:
        db_path: Path to the SQLite database file.
        timeout: Seconds to wait before raising OperationalError on lock.
        check_same_thread: Allow connection to be used from multiple threads.
        isolation_level: Transaction isolation level (None = manual commits).
        row_factory: Row factory (default: sqlite3.Row for dict-like access).

    Returns:
        A configured sqlite3.Connection with WAL mode enabled.
    """
    conn = sqlite3.connect(
        str(db_path),
        timeout=timeout,
        check_same_thread=check_same_thread,
        isolation_level=isolation_level,
        **kwargs,
    )
    if row_factory is not None:
        conn.row_factory = row_factory
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
