import argparse
import json
import os
import sys
import requests

# Add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.payload_decoder import compress_payload, encrypt_payload
from app.core.config import CHAT_API_KEY


def run_test(target_url: str, mode: str, api_key: str, file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    print(f"\n--- Testing Ingest on: {target_url} ---")
    print(f"Mode: {mode}")
    print(f"Source file: {file_path} ({os.path.getsize(file_path):,} bytes)")

    if mode == "compressed":
        # Mode 1: Compressed Base64
        compressed_str = compress_payload(data)
        print(f"Payload compressed to: {len(compressed_str):,} chars")
        payload = {"compressed": True, "payload": compressed_str}
        res = requests.post(f"{target_url}/ingest", headers=headers, json=payload)

    elif mode == "encrypted":
        # Mode 2: Fernet Encrypted
        encrypted_str = encrypt_payload(data, secret_key=api_key)
        print(f"Payload encrypted to: {len(encrypted_str):,} chars")
        payload = {"encrypted": True, "payload": encrypted_str}
        res = requests.post(f"{target_url}/ingest", headers=headers, json=payload)

    else:
        # Mode 3: Normal Raw JSON
        res = requests.post(f"{target_url}/ingest", headers=headers, json=data)

    print(f"\nStatus Code: {res.status_code}")
    try:
        print("Response JSON:\n", json.dumps(res.json(), indent=2))
    except Exception:
        print("Response Text:\n", res.text[:500])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Ingest API in different modes")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL (e.g. http://127.0.0.1:8000 or https://ai.healthlete.io)")
    parser.add_argument("--mode", choices=["compressed", "encrypted", "raw"], default="compressed", help="Ingest mode")
    parser.add_argument("--key", default=CHAT_API_KEY, help="X-API-Key value")
    parser.add_argument("--file", default="athlete.json", help="Path to athlete JSON")

    args = parser.parse_args()
    run_test(args.url.rstrip("/"), args.mode, args.key, args.file)
