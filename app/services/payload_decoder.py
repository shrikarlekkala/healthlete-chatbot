import base64
import gzip
import hashlib
import json
import time
from collections import defaultdict
from typing import Any, Dict, Optional, Tuple
import zlib

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None


def _derive_fernet(secret_key: str):
    if not Fernet or not secret_key:
        return None
    key_bytes = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def decode_payload(payload: Dict[str, Any], secret_key: str = "") -> Dict[str, Any]:
    """
    Decodes incoming payload transparently:
    - Normal JSON passes through untouched.
    - Base64 / gzip-compressed payloads are decompressed.
    - Fernet/AES encrypted payloads are decrypted using secret_key.
    """
    if not isinstance(payload, dict):
        return payload

    # If it is already a full athlete JSON structure
    if "athlete" in payload or ("data" in payload and isinstance(payload.get("data"), dict) and "athlete" in payload["data"]):
        return payload

    raw_data = payload.get("payload") or payload.get("data")
    if not raw_data or not isinstance(raw_data, str):
        return payload

    raw_str = raw_data.strip()

    # 1. Check if Fernet encrypted
    is_encrypted = payload.get("encrypted", False) or raw_str.startswith("gAAAAA")
    if is_encrypted and Fernet and secret_key:
        fernet = _derive_fernet(secret_key)
        if fernet:
            try:
                decrypted_bytes = fernet.decrypt(raw_str.encode("utf-8"))
                try:
                    decrypted_bytes = gzip.decompress(decrypted_bytes)
                except Exception:
                    pass
                return json.loads(decrypted_bytes.decode("utf-8"))
            except Exception:
                pass

    # 2. Check if Base64 encoded or Gzip compressed
    try:
        decoded_bytes = base64.b64decode(raw_str)
        try:
            decompressed = gzip.decompress(decoded_bytes)
        except Exception:
            try:
                decompressed = zlib.decompress(decoded_bytes)
            except Exception:
                decompressed = decoded_bytes
        return json.loads(decompressed.decode("utf-8"))
    except Exception:
        pass

    return payload


def encrypt_payload(data: Dict[str, Any], secret_key: str, compress: bool = True) -> str:
    """Helper to encrypt a JSON payload using Fernet (for tests and clients)."""
    if not Fernet:
        raise RuntimeError("cryptography package is required for encryption")
    json_bytes = json.dumps(data).encode("utf-8")
    if compress:
        json_bytes = gzip.compress(json_bytes)
    fernet = _derive_fernet(secret_key)
    if not fernet:
        raise ValueError("Valid secret_key required for encryption")
    return fernet.encrypt(json_bytes).decode("utf-8")


def compress_payload(data: Dict[str, Any]) -> str:
    """Helper to gzip and base64-encode a JSON payload."""
    json_bytes = json.dumps(data).encode("utf-8")
    compressed = gzip.compress(json_bytes)
    return base64.b64encode(compressed).decode("utf-8")

