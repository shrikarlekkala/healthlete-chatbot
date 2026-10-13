"""
ingestion.py — Athlete profile ingestion orchestration
======================================================
Migrated from the original embed.py. Relies on the AI embedding module
and the profile repository.
"""

import hashlib
import logging
import re
from typing import Dict, List, Tuple

from app.ai.embeddings import embed_batch
from app.repositories import profile

log = logging.getLogger("healthlete.ingestion")

id_regex = re.compile(r'Id:\s*([a-fA-F0-9\-]+)')
name_regex = re.compile(r'Full Name:\s*([^;]+)')


def extract_metadata(text: str) -> Tuple[str, str]:
    """Extracts Athlete ID and Full Name directly from the flattened text."""
    id_match = id_regex.search(text)
    name_match = name_regex.search(text)

    if id_match and name_match:
        return id_match.group(1).strip(), name_match.group(1).strip()
    raise ValueError("Could not find Id or Full Name in the text file.")


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """Splits flattened text into smaller chunks with overlap."""
    words = text.split()
    step = max(1, chunk_size - overlap)
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), step)]
    log.info("Formed %s chunks", len(chunks))
    return chunks


def process_and_store_flattened_text(
    flattened_text: str,
    athlete_id: str,
    profile_name: str,
) -> Dict[str, int]:
    """Chunks, embeds and stores the flattened text. Returns a summary dict
    of what was skipped / inserted / updated / deleted."""
    chunks = chunk_text(flattened_text)

    skipped_count = 0
    updated_count = 0
    inserted_count = 0

    existing_chunks = profile.get_existing_chunk_hashes(athlete_id)

    chunks_to_embed = []
    for index, chunk in enumerate(chunks):
        chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        chunk_index = index + 1  # 1-based indexing

        if chunk_index in existing_chunks and existing_chunks[chunk_index] == chunk_hash:
            skipped_count += 1
        else:
            chunks_to_embed.append({
                "index": chunk_index,
                "chunk": chunk,
                "hash": chunk_hash,
                "is_update": chunk_index in existing_chunks,
            })

    BATCH_SIZE = 15
    for i in range(0, len(chunks_to_embed), BATCH_SIZE):
        batch = chunks_to_embed[i:i + BATCH_SIZE]
        log.info("Processing batch %s: chunks %s-%s", 
                 (i // BATCH_SIZE) + 1, batch[0]['index'], batch[-1]['index'])

        inputs = [item["chunk"] for item in batch]
        embeddings = embed_batch(inputs)

        params = [
            (
                athlete_id,
                profile_name,
                item["chunk"],
                item["hash"],
                embeddings[j],
                item["index"],
            )
            for j, item in enumerate(batch)
        ]
        
        profile.upsert_chunks(params)

        for item in batch:
            if item["is_update"]:
                updated_count += 1
            else:
                inserted_count += 1

    deleted_count = profile.delete_orphan_chunks(athlete_id, len(chunks))

    log.info("Processed %s chunks (Skipped: %s, Inserted: %s, Updated: %s, Deleted orphans: %s)",
             len(chunks), skipped_count, inserted_count, updated_count, deleted_count)
             
    return {
        "total_chunks": len(chunks),
        "skipped_unchanged": skipped_count,
        "inserted_new": inserted_count,
        "updated_changed": updated_count,
        "deleted_orphans": deleted_count,
    }


def delete_athlete(athlete_id: str) -> Dict[str, any]:
    """Removes every chunk, hash and embedding stored for this athlete id."""
    return profile.delete_all_chunks(athlete_id)
