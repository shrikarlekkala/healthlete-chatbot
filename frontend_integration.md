# Frontend Integration Guide: Athlete Ingestion API

This guide provides simple, clean instructions for frontend developers to send athlete profile datasets to the HealthLete Ingestion API.

---

## 1. Quick Overview

- **Endpoint**: `POST /ingest`
- **Authentication**: `X-API-Key: <YOUR_API_KEY>`
- **Content-Type**: `application/json`
- **Method**: Send your athlete JSON as a **Gzip-compressed Base64 string**.

### Why Gzip Compression?
An athlete profile JSON is typically ~100 KB. Compressing it with Gzip reduces it to **~12 KB** (an **88% reduction**). 
This allows:
- Near-instant network upload (< 50ms)
- Seamless transport through AWS WAF and ALB without hitting body size limits or false positive inspection rules
- 100% stateless, single-request architecture

---

## 2. API Request & Response Format

### Request Format:
```json
{
  "compressed": true,
  "payload": "H4sICG3sOmUCA2F0aGxldGUuanNvbgDtPctv2zYQwP9VIJwN6FqkJ...=="
}
```

### Successful Response (`200 OK`):
```json
{
  "success": true,
  "athlete_id": "511164d5-603d-4f52-a7d3-3b8a1424479c",
  "profile_name": "Tyson Fury",
  "word_count": 2189,
  "total_chunks": 14,
  "skipped_unchanged": 14,
  "inserted_new": 0,
  "updated_changed": 0,
  "deleted_orphans": 0
}
```

---

## 3. Frontend Implementation (JavaScript / TypeScript)

Install the standard `pako` compression library:
```bash
npm install pako
```

### Ready-to-Use Helper:
```typescript
import pako from 'pako';

/**
 * Compresses an athlete profile JSON and sends it to the ingestion API.
 */
export async function ingestAthlete(athleteData: object, apiKey: string, apiBaseUrl = 'https://api.yourdomain.com') {
  // 1. Encode JSON string to UTF-8 bytes
  const jsonString = JSON.stringify(athleteData);
  const rawBytes = new TextEncoder().encode(jsonString);

  // 2. Gzip compress
  const compressedBytes = pako.gzip(rawBytes);

  // 3. Convert Uint8Array to Base64
  let binary = '';
  for (let i = 0; i < compressedBytes.length; i++) {
    binary += String.fromCharCode(compressedBytes[i]);
  }
  const base64Payload = btoa(binary);

  // 4. Send single POST request
  const response = await fetch(`${apiBaseUrl}/ingest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({
      compressed: true,
      payload: base64Payload,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(`Ingest failed (${response.status}): ${errorBody.detail || 'Unknown error'}`);
  }

  return await response.json();
}
```

---

## 4. Best Practices for High Volume / Bulk Ingestion

If your frontend is syncing or ingesting multiple athletes in bulk:
1. **Concurrency Throttling**: Do not trigger 100+ parallel `fetch` calls simultaneously. Limit browser concurrency to **5 to 10 parallel requests** using a simple queue.
2. **Automatic Retry with Backoff**: If a request encounters a transient network timeout, retry after 1-2 seconds.
3. **Smart Hash Diffing**: Re-uploading an existing athlete is ultra-fast because the backend hashes chunks and skips re-embedding unchanged data.
