"""
profile.py — Database access layer for profile_chunks
=======================================================
All raw SQL queries for the profile_chunks table live here.
No other module should execute SQL against this table directly.
"""

import logging
from typing import Dict, List, Optional, Tuple

from psycopg2.extras import execute_batch

from app.core.database import get_db_connection

log = logging.getLogger("healthlete.repository")


def get_profile_name(athlete_id: str) -> Optional[str]:
    """Reads the athlete name from the stored chunks (id = athlete id)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT profile_name FROM profile_chunks WHERE id = %s "
                "ORDER BY chunk_index ASC LIMIT 1",
                (athlete_id,),
            )
            row = cur.fetchone()
        return row[0] if row else None


def get_existing_chunk_hashes(athlete_id: str) -> Dict[int, str]:
    """Returns a dict of {chunk_index: chunk_hash} for an athlete."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT chunk_index, chunk_hash FROM profile_chunks WHERE id = %s",
                (athlete_id,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}


UPSERT_QUERY = """
    INSERT INTO profile_chunks 
       (id, profile_name, chunk_text, chunk_hash, embedding, chunk_index) 
       VALUES (%s, %s, %s, %s, %s, %s)
       ON CONFLICT (id, chunk_index) 
       DO UPDATE SET 
         profile_name = EXCLUDED.profile_name,
         chunk_text = EXCLUDED.chunk_text,
         chunk_hash = EXCLUDED.chunk_hash,
         embedding = EXCLUDED.embedding
"""


def upsert_chunks(params_list: List[Tuple]) -> None:
    """Batch upserts a list of (id, profile_name, chunk_text, chunk_hash,
    embedding, chunk_index) tuples into profile_chunks."""
    if not params_list:
        return
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            execute_batch(cur, UPSERT_QUERY, params_list)
        conn.commit()


def delete_orphan_chunks(athlete_id: str, max_chunk_index: int) -> int:
    """Deletes chunks with index greater than max_chunk_index. Returns count."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM profile_chunks WHERE id = %s AND chunk_index > %s",
                (athlete_id, max_chunk_index),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted


def delete_all_chunks(athlete_id: str) -> Dict[str, any]:
    """Removes every chunk for this athlete id. Returns status dict."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT profile_name FROM profile_chunks WHERE id = %s LIMIT 1",
                (athlete_id,),
            )
            row = cur.fetchone()
            profile_name = row[0] if row else None

            cur.execute("DELETE FROM profile_chunks WHERE id = %s", (athlete_id,))
            deleted_chunks = cur.rowcount
        conn.commit()
    return {
        "deleted": deleted_chunks > 0,
        "profile_name": profile_name,
        "deleted_chunks": deleted_chunks,
    }


def search_similar_chunks(
    athlete_id: str, embedding: list, limit: int
) -> List[Dict]:
    """Returns the nearest chunks for this athlete by cosine distance."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_text, profile_name, chunk_index,
                       (embedding <=> %s::vector) AS distance
                FROM profile_chunks
                WHERE id = %s
                ORDER BY distance ASC
                LIMIT %s
                """,
                (embedding, athlete_id, limit),
            )
            rows = cur.fetchall()

    return [
        {"text": r[0], "profile_name": r[1], "index": int(r[2]),
         "distance": float(r[3])}
        for r in rows
    ]
