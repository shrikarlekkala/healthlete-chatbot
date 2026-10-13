import psycopg2
import os
from dotenv import load_dotenv

# Load config from the root .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "healthleteai_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

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
    PRIMARY KEY (id, chunk_index)
);
"""
cursor.execute(create_table_query)
conn.commit()

cursor.close()
conn.close()
print("Table created successfully!")
