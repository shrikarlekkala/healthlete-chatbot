# HealthLete IQ - Streaming Chatbot API 

Branch: `staging`

HealthLete IQ is an intelligence-driven analytics API built to evaluate athlete performance, audience demographics, and commercial brand fit.

It serves two kinds of chatbot:

| Chatbot | Used by | Endpoints | Key |
|---|---|---|---|
| Athlete AI Analyst (one athlete, uses embeddings) | Frontend server proxy (`/healthlete-ai`) | `/ingest`, `/chat`, `/chat/stream`, `/athlete/{id}` | `CHAT_API_KEY` |
| Brand Assistant (global chat bubble + Home/Discovery AI search, no embeddings) | NestJS backend only | `/assistant/plan`, `/assistant/answer/stream` | `ASSISTANT_API_KEY` |

---

## Key Capabilities

1. Server-Sent Events (SSE) Streaming
   - Real-time token streaming via `POST /chat/stream`.
   - Direct streaming without artificial word buffering or block delays.
   - Structured SSE event lifecycle emitting metadata, token chunks, and final conversation state.

2. In-Memory Vector TTL Cache
   - In-memory cache for athlete profile vectors and chunks with a 10-minute sliding TTL.
   - Vector similarity search runs in memory using vectorized cosine dot-product calculations.
   - Eliminates redundant PostgreSQL pgvector queries on repeat turns.

3. Zero-Login API Security
   - Shared key authentication via `X-API-Key` header.
   - Sliding-window in-memory rate limiting per client IP (default: 10 requests/minute).
   - Request payload validation enforcing a maximum message length of 500 characters.

4. Query Intent and Greeting Routing
   - Conversational pleasantries (e.g., "Hi", "Hello", "Good morning") receive immediate warm greeting responses without triggering vector search or LLM web fallbacks.
   - All athlete-related queries (career, sport, background, stats, brand fit, news) are classified in-scope.
   - If profile data lacks specific facts, the pipeline falls back to OpenAI GPT-4.1 web search.
   - Unrelated non-sports queries (e.g., coding, general trivia) receive a polite scope redirect.

5. In-Memory Config Caching
   - Configuration values in `app/core/config.py` are loaded once from `.env` and cached using `@lru_cache(maxsize=1)`.
   - Avoids repeated disk reads and environment parsing during concurrent requests.

6. Brand Assistant (no per-brand embeddings)
   - The AI turns a question into JSON search criteria; the NestJS backend runs the search on its own database with that brand's scores; the AI then writes the answer from the results.
   - No athlete embeddings are stored per brand, so a brand changing its health conditions needs no re-indexing.
   - Uses `gpt-4o-mini` for both steps and streams the answer over SSE. See [Brand Assistant](#brand-assistant).

---

## Tech Stack

- Framework: FastAPI (Python 3.10+)
- Server: Uvicorn (Development) / Gunicorn with UvicornWorker (Production)
- Database: PostgreSQL with pgvector extension
- AI Models: OpenAI gpt-4o (main analyst), gpt-4.1 (web search fallback), text-embedding-3-small (embeddings)
- Caching: In-memory TTL cache and functools.lru_cache (no Redis dependency)

---

## Repository Structure

```
healthlete-stream-chatbot/
|-- app/
|   |-- main.py                 # FastAPI application, CORS, and connection pool lifecycle
|   |-- api/
|   |   `-- v1/
|   |       |-- router.py       # API v1 router aggregation
|   |       |-- chat.py         # Endpoints: POST /chat and POST /chat/stream
|   |       |-- health.py       # Health checks and system diagnostics
|   |       |-- athletes.py     # Athlete management endpoints
|   |       |-- ingest.py       # Profile ingestion and vector embedding generation
|   |       `-- assistant.py    # Brand assistant: POST /assistant/plan and /assistant/answer/stream
|   |-- ai/
|   |   |-- assistant/          # Brand assistant: tool definitions, prompts, plan + answer service
|   |   |-- chat.py             # Chat pipelines: ask_stream() and ask()
|   |   |-- embeddings.py       # OpenAI vector embedding generation
|   |   |-- retrieval.py        # Vector similarity search and score filtering
|   |   |-- web_search.py       # OpenAI Responses API web search integration
|   |   `-- prompts/            # System instructions, context builders, and response templates
|   |-- core/
|   |   |-- config.py           # Cached environment settings (@lru_cache)
|   |   |-- database.py         # PostgreSQL connection pool
|   |   |-- openai_client.py    # OpenAI sync and async client singletons
|   |   `-- security.py         # API key validation and IP rate limiter
|   |-- repositories/
|   |   |-- profile.py          # Database queries and AthleteVectorTTLCache
|   |   `-- athlete.py          # Athlete record operations
|   |-- schemas/
|   |   |-- chat.py             # ChatRequest and ChatResponse schemas
|   |   |-- assistant.py        # Brand assistant request/response schemas
|   |   `-- athlete.py          # Ingestion schemas
|   `-- utils/
|       |-- format.py           # Text formatting helpers
|       `-- text.py             # Decision parsing and response sanitization
|-- run.py                      # Application runner
|-- requirements.txt            # Python dependencies
`-- .env.example                # Sample environment variables
```

---

## Streaming Event Protocol

The `/chat/stream` endpoint returns a Server-Sent Events stream (`Content-Type: text/event-stream`).

### Event Sequence

1. `meta`: Emitted when the request is validated and the athlete profile is resolved.
```json
data: {"type": "meta", "athlete_id": "511164d5-603d-4f52-a7d3-3b8a1424479c", "profile_name": "Tyson Fury"}
```

2. `content`: Emitted continuously as tokens are generated by the model.
```json
data: {"type": "content", "delta": "Tyson Fury is a professional heavyweight boxer."}
```

3. `done`: Emitted at stream completion with final metadata, decision path, and updated history.
```json
data: {
  "type": "done",
  "athlete_id": "511164d5-603d-4f52-a7d3-3b8a1424479c",
  "profile_name": "Tyson Fury",
  "path": "profile",
  "decision": "PROFILE",
  "answer": "Tyson Fury is a professional heavyweight boxer.",
  "chat_history": [
    {"role": "user", "content": "What sport does he play?"},
    {"role": "assistant", "content": "Tyson Fury is a professional heavyweight boxer."}
  ]
}
```

---

## Security Layer

Every request to `/chat/stream` is evaluated against three checks:

1. API Key Header
   - Requests must provide the `X-API-Key` header matching `CHAT_API_KEY`.
   - Missing or incorrect key returns HTTP `401 Unauthorized`.

2. IP Rate Limiting
   - Managed via an in-memory sliding window per client IP.
   - Configured via `RATE_LIMIT_PER_MINUTE` (default: 20).
   - Exceeding the threshold returns HTTP `429 Too Many Requests`.

3. Payload Length Guard
   - Maximum allowed question length is 500 characters.
   - Messages exceeding the limit return HTTP `422 Unprocessable Entity`.

The `/assistant/*` endpoints use their own key and limits:

- `X-API-Key` must match `ASSISTANT_API_KEY`. This key is shared only with the NestJS backend, never with a browser. If it is not set, the endpoints return `503`.
- Rate limit is per brand (the backend sends `X-Brand-Id`), set by `ASSISTANT_RATE_LIMIT_PER_MINUTE` (default 30). One user question makes 2 requests (plan + answer), so 30 allows about 15 questions a minute per brand.
- Tool results sent for the answer are capped at 24,000 characters (`413` if larger).

Never commit real keys. Keep them in `.env` (gitignored) or AWS Secrets Manager, and generate them with `openssl rand -hex 32`.

---

## Environment Configuration

Create a `.env` file in the project root based on `.env.example`:

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API Secret Key | Required |
| `API_HOST` | Host address to bind | `0.0.0.0` |
| `API_PORT` | Port for the API server | `8000` |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | `*` |
| `THREAD_POOL_LIMIT` | Thread pool token limit for async workers | `100` |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_USER` | PostgreSQL user | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | None |
| `DB_NAME` | Database name | `healthlete` |
| `DB_POOL_MIN` | Minimum connections in pool | `2` |
| `DB_POOL_MAX` | Maximum connections in pool | `20` |
| `DB_POOL_TIMEOUT` | Connection acquisition timeout in seconds | `10.0` |
| `CHAT_MODEL` | Main conversational model | `gpt-4o` |
| `EMBEDDING_MODEL` | Model used for vector embeddings | `text-embedding-3-small` |
| `WEB_SEARCH_MODEL` | Model used for web search fallback | `gpt-4.1` |
| `RETRIEVAL_LIMIT` | Top chunk limit for retrieval | `8` |
| `SIMILARITY_THRESHOLD` | Minimum cosine similarity score | `0.75` |
| `MAX_TOKENS` | Maximum tokens for chat completions | `800` |
| `CHAT_TEMPERATURE` | Sampling temperature | `0.2` |
| `HISTORY_TURNS` | Number of recent conversation turns kept | `3` |
| `CHAT_API_KEY` | Key for the athlete analyst endpoints. Must equal `HEALTHLETE_AI_API_KEY` on the frontend server | Required |
| `RATE_LIMIT_PER_MINUTE` | Maximum allowed requests per IP per minute | `10` |
| `MAX_QUERY_LENGTH` | Maximum allowed character length for message | `500` |
| `ASSISTANT_API_KEY` | Key for `/assistant/*`. Must equal `HEALTHLETE_AI_ASSISTANT_API_KEY` in the NestJS backend | Required for the brand assistant |
| `ASSISTANT_PLAN_MODEL` | Model that turns the question into tool calls | `gpt-4o-mini` |
| `ASSISTANT_ANSWER_MODEL` | Model that writes the streamed answer | `gpt-4o-mini` |
| `ASSISTANT_MAX_TOKENS` | Maximum tokens for an assistant answer | `450` |
| `ASSISTANT_RATE_LIMIT_PER_MINUTE` | Maximum `/assistant/*` requests per brand per minute | `30` |

Which project holds which key:

```
Frontend server  HEALTHLETE_AI_API_KEY            ==  AI  CHAT_API_KEY
NestJS backend   HEALTHLETE_AI_ASSISTANT_API_KEY  ==  AI  ASSISTANT_API_KEY
NestJS backend   HEALTHLETE_AI_API_BASE_URL       =   URL of this AI service
```

---

## Getting Started

### 1. Requirements
- Python 3.10+
- PostgreSQL with pgvector extension enabled

### 2. Setup
```bash
git clone https://github.com/shrikarlekkala/healthlete-chatbot.git healthlete-stream-chatbot
cd healthlete-stream-chatbot
git checkout feature/Streaming-chatbot

python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 3. Running the Server

Local development (with hot-reload):
```bash
python run.py
```

Production deployment:
```bash
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## API Endpoints

### 1. `POST /chat/stream`
Streams token responses for athlete queries over SSE.

Headers:
- `Content-Type: application/json`
- `X-API-Key: <CHAT_API_KEY>`

Request:
```json
{
  "athlete_id": "511164d5-603d-4f52-a7d3-3b8a1424479c",
  "message": "What are his key achievements?",
  "chat_history": []
}
```

Example:
```bash
curl -N -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{"athlete_id": "511164d5-603d-4f52-a7d3-3b8a1424479c", "message": "What are his key achievements?"}'
```

### 2. `POST /chat`
Synchronous JSON response for standard clients.

Headers:
- `Content-Type: application/json`
- `X-API-Key: <CHAT_API_KEY>`

Request:
```json
{
  "athlete_id": "511164d5-603d-4f52-a7d3-3b8a1424479c",
  "message": "Give me an overview of his audience fit.",
  "chat_history": []
}
```

Example:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{"athlete_id": "511164d5-603d-4f52-a7d3-3b8a1424479c", "message": "Give me an overview of his audience fit."}'
```

### 3. `GET /health`
Returns system status and pool metrics.

Example:
```bash
curl http://localhost:8000/health
```

---

## Brand Assistant

Powers the global chat bubble and the Home/Discovery AI search. The browser never calls these endpoints: it calls the NestJS backend (`POST /api/v1/brand/assistant/chat/stream`), which calls this service.

```
1. User asks         "NFL players open about mental health with 90+ match"
2. NestJS            checks the login, takes the brand from it (never from the AI)
3. AI  /plan         -> search_athletes { sport: "NFL", conditions: ["Mental Health"], min_match_score: 90 }
4. NestJS            runs the search on its database with this brand's scores
5. Browser           shows athlete cards straight away
6. AI  /answer       writes the answer from a short summary of the results
7. Browser           shows the answer as it streams
```

Tools the planner can choose (names must match the NestJS assistant module):

| Tool | What the backend does |
|---|---|
| `search_athletes` | Discovery search: conditions, sport, athlete name/text, minimum scores, sort |
| `get_shortlist` | The brand's saved athletes |
| `get_campaigns` | The brand's campaigns, optionally by status |
| `get_partnership_requests` | The brand's partnership requests, optionally by status |
| `platform_help` | How-to answers about the platform |
| `answer_directly` | Greetings and off-topic messages, no data needed |

### `POST /assistant/plan`

Headers: `X-API-Key: <ASSISTANT_API_KEY>`, `X-Brand-Id: <brand id>`

```json
{
  "message": "NFL players open about mental health with 90+ match",
  "chat_history": [],
  "catalog": {
    "conditions": ["Mental Health", "Type 1 Diabetes"],
    "sports": ["NFL", "NBA"],
    "brand_conditions": ["Type 1 Diabetes"]
  }
}
```

Response:
```json
{
  "success": true,
  "tool_calls": [
    {"name": "search_athletes", "arguments": {"sport": "NFL", "conditions": ["Mental Health"], "min_match_score": 90}}
  ]
}
```

### `POST /assistant/answer/stream`

Same headers. The body carries the question, `surface` (`assistant` for the chat bubble, `discover` for the shorter Home/Discovery answer) and up to 6 `tool_results` from the backend. The response is SSE:

```
data: {"type": "content", "delta": "I found 2 NFL athletes..."}
data: {"type": "done", "answer": "I found 2 NFL athletes..."}
data: {"type": "error", "message": "..."}
```

---

## Troubleshooting

- `401 Unauthorized`: Verify the `X-API-Key` header matches `CHAT_API_KEY` in `.env`.
- `429 Too Many Requests`: Client IP exceeded the allowed requests per minute. Wait 60 seconds or adjust `RATE_LIMIT_PER_MINUTE`.
- `422 Unprocessable Entity`: The input message exceeds 500 characters.
- `pgvector extension error`: Verify PostgreSQL has pgvector installed (`CREATE EXTENSION IF NOT EXISTS vector;`).
- `503 The brand assistant is not configured` on `/assistant/*`: set `ASSISTANT_API_KEY` in `.env` and restart.
- `401` on `/assistant/*`: `ASSISTANT_API_KEY` here and `HEALTHLETE_AI_ASSISTANT_API_KEY` in the backend are different.
- `"HealthLete AI is not configured on the server."` from the frontend: `HEALTHLETE_AI_API_KEY` is missing on the frontend server (runtime env, e.g. pm2), not in GitHub secrets.
- `429` on `/assistant/*`: that brand passed `ASSISTANT_RATE_LIMIT_PER_MINUTE`. Wait a minute.
