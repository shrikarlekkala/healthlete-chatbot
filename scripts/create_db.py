import os
import sys
import psycopg2

# Ensure repository root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cursor = conn.cursor()

# Enable pgvector extension
cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

# Create the profile_chunks table
create_table_query = """
CREATE TABLE IF NOT EXISTS profile_chunks (
    id VARCHAR(255) NOT NULL,
    profile_name VARCHAR(255),
    chunk_text TEXT,
    chunk_hash VARCHAR(64),
    embedding vector(1536),
    chunk_index INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, chunk_index)
);

ALTER TABLE profile_chunks ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE profile_chunks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
"""
cursor.execute(create_table_query)
conn.commit()

cursor.close()
conn.close()
print("Table created/updated successfully!")
