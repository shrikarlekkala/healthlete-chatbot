import json
from functools import lru_cache
import os
from typing import List, Optional
import urllib.request
from dotenv import load_dotenv

load_dotenv()


def _get_aws_region() -> Optional[str]:
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        return region
    try:
        req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=1) as resp:
            token = resp.read().decode("utf-8")
        reg_req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/placement/region",
            headers={"X-aws-ec2-metadata-token": token},
        )
        with urllib.request.urlopen(reg_req, timeout=1) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        pass
    return "us-east-1"


def _load_aws_secrets():
    if os.getenv("DISABLE_AWS_SECRETS", "false").lower() in ("true", "1", "yes"):
        return

    secret_name = os.getenv("AWS_SECRET_NAME", "healthlete/prod/database")
    region_name = _get_aws_region()

    try:
        import boto3

        client = boto3.client("secretsmanager", region_name=region_name)
        response = client.get_secret_value(SecretId=secret_name)

        if "SecretString" in response:
            secrets = json.loads(response["SecretString"])

            field_mappings = {
                "host": "DB_HOST",
                "endpoint": "DB_HOST",
                "port": "DB_PORT",
                "username": "DB_USER",
                "user": "DB_USER",
                "password": "DB_PASSWORD",
                "dbname": "DB_NAME",
                "database": "DB_NAME",
            }

            for key, val in secrets.items():
                val_str = str(val)
                os.environ[key] = val_str
                os.environ[key.upper()] = val_str
                lower_key = key.lower()
                if lower_key in field_mappings:
                    os.environ[field_mappings[lower_key]] = val_str
    except Exception:
        pass


_load_aws_secrets()


class Settings:
    def __init__(self):
        # API
        self.API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
        self.API_PORT: int = int(os.getenv("API_PORT", "8000"))
        self.THREAD_POOL_LIMIT: int = int(os.getenv("THREAD_POOL_LIMIT", "100"))
        self.ALLOWED_ORIGINS: List[str] = [
            o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
        ]

        # Security
        self.CHAT_API_KEY: str = os.getenv("CHAT_API_KEY")
        self.RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
        self.MAX_QUERY_LENGTH: int = int(os.getenv("MAX_QUERY_LENGTH", "500"))

        # Database
        self.DB_HOST: str = os.getenv("DB_HOST", "localhost")
        self.DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
        self.DB_USER: str = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
        self.DB_NAME: str = os.getenv("DB_NAME", "healthlete")
        self.DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "2"))
        self.DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "20"))
        self.DB_POOL_TIMEOUT: float = float(os.getenv("DB_POOL_TIMEOUT", "10.0"))

        # OpenAI
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o")
        self.WEB_SEARCH_MODEL: str = os.getenv("WEB_SEARCH_MODEL", "gpt-4.1")

        # Chat pipeline
        self.RETRIEVAL_LIMIT: int = int(os.getenv("RETRIEVAL_LIMIT", "8"))
        self.SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
        self.MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "800"))
        self.TEMPERATURE: float = float(os.getenv("CHAT_TEMPERATURE", "0.2"))
        self.HISTORY_TURNS: int = int(os.getenv("HISTORY_TURNS", "3"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

API_HOST: str = settings.API_HOST
API_PORT: int = settings.API_PORT
THREAD_POOL_LIMIT: int = settings.THREAD_POOL_LIMIT
ALLOWED_ORIGINS: List[str] = settings.ALLOWED_ORIGINS

CHAT_API_KEY: str = settings.CHAT_API_KEY
RATE_LIMIT_PER_MINUTE: int = settings.RATE_LIMIT_PER_MINUTE
MAX_QUERY_LENGTH: int = settings.MAX_QUERY_LENGTH

DB_HOST: str = settings.DB_HOST
DB_PORT: int = settings.DB_PORT
DB_USER: str = settings.DB_USER
DB_PASSWORD: str = settings.DB_PASSWORD
DB_NAME: str = settings.DB_NAME
DB_POOL_MIN: int = settings.DB_POOL_MIN
DB_POOL_MAX: int = settings.DB_POOL_MAX
DB_POOL_TIMEOUT: float = settings.DB_POOL_TIMEOUT

OPENAI_API_KEY: str = settings.OPENAI_API_KEY
EMBEDDING_MODEL: str = settings.EMBEDDING_MODEL
CHAT_MODEL: str = settings.CHAT_MODEL
WEB_SEARCH_MODEL: str = settings.WEB_SEARCH_MODEL

RETRIEVAL_LIMIT: int = settings.RETRIEVAL_LIMIT
SIMILARITY_THRESHOLD: float = settings.SIMILARITY_THRESHOLD
MAX_TOKENS: int = settings.MAX_TOKENS
TEMPERATURE: float = settings.TEMPERATURE
HISTORY_TURNS: int = settings.HISTORY_TURNS
