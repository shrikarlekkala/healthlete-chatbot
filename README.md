# Healthlete AI

Healthlete AI (also known as Healthlete IQ) is a powerful, intelligence-driven API that helps evaluate marketing and commercial partnerships for athletes. By leveraging a vector-based Retrieval-Augmented Generation (RAG) system with OpenAI and PostgreSQL, Healthlete provides instant insights into an athlete's strengths, brand alignment, demographics, and public image.

## Key Features

* **Intelligent Athlete Ingestion:** Cleans and processes raw athlete metadata (like social media stats, causes they support, demographics), generating vector embeddings for accurate search context.
* **Smart RAG Chat System:** Query the AI about an athlete's brand fit. It searches through the database to give you highly specific, data-backed answers.
* **Live Web Fallback:** If the database doesn't have enough context on a specific athlete, the AI falls back to a live web search to bring you the most up-to-date details.
* **Modern API Architecture:** Built with a clean, layered architecture using FastAPI for speed and easy maintainability.

## Project Architecture

We follow a clean, layered structure to keep the code human-readable, testable, and scalable:

* `app/api/` - The FastAPI routes and endpoints (`/chat`, `/ingest`, `/athletes`).
* `app/services/` - Core business logic for cleaning data and orchestrating ingestion.
* `app/ai/` - All AI logic: prompts, vector embedding generation, and ChatGPT conversation routing.
* `app/repositories/` - Safe, parameterized database access layer (no raw SQL anywhere else!).
* `app/core/` - Configuration, environment variables, and thread-safe database connection pooling.
* `tests/` - Standalone tests for ensuring end-to-end reliability (like `test_migration.py`).

## Getting Started

### 1. Requirements
* **Python 3.10+**
* **PostgreSQL** with the `pgvector` extension enabled.

### 2. Setup your Environment

Rename `.env.example` to `.env` and fill in your credentials:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=healthleteai_db
DB_USER=postgres
DB_PASSWORD=your_password_here

OPENAI_API_KEY=sk-your-openai-key-here
```

### 3. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # (On Windows use: .\venv\Scripts\activate)
pip install -r requirements.txt
```

### 4. Initialize the Database
Ensure your PostgreSQL database is running, then create the required tables:
```bash
python scripts/create_db.py
```

### 5. Run the API

**Option A: Local Development (Windows / Mac / Linux)**
For local testing and development, use the provided runner script. It utilizes Uvicorn and supports hot-reloading.
```bash
python run.py
```
*The API will start on `http://0.0.0.0:3236`.*
*You can view the interactive Swagger Documentation at `http://localhost:3236/docs`.*

**Option B: Production (Linux / Unix)**
For a production environment, bypass the python wrapper script. Use Gunicorn as a process manager with Uvicorn workers to efficiently handle multiple concurrent requests:
```bash
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:3236
```
*(Ensure `ENVIRONMENT=production` is set in your `.env` file.)*

## Testing

To test the end-to-end ingestion and chat system with dummy data, you can run the provided migration test script:
```bash
python tests/test_migration.py
```
