"""
HAYAT v2.0 — Core Configuration
Enterprise-grade settings with validation and environment awareness.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "HAYAT v2.0 — Bangladesh Legal Intelligence Platform"
    app_version: str = "2.0.0"
    environment: str = Field(default="development", pattern=r"^(development|staging|production)$")
    debug: bool = False
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # Security
    jwt_secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    password_hash_rounds: int = 12
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",")]
        return v

    # Database — PostgreSQL (Metadata & Structured Data)
    database_url: PostgresDsn = Field(...)
    database_pool_size: int = 20
    database_max_overflow: int = 40
    database_pool_timeout: int = 30
    database_echo: bool = False

    # Neo4j — Knowledge Graph
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = Field(..., min_length=8)
    neo4j_max_connection_lifetime: int = 3600
    neo4j_max_connection_pool_size: int = 50

    # Redis — Cache & Sessions
    redis_url: RedisDsn = Field(...)
    redis_socket_timeout: int = 5
    redis_socket_connect_timeout: int = 5

    # MinIO — Object Storage (PDFs, Images, Documents)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = Field(...)
    minio_secret_key: str = Field(...)
    minio_bucket: str = "hayat-documents"
    minio_secure: bool = False
    minio_presigned_url_expiry: int = 3600  # 1 hour

    # OpenSearch — Full-Text Search
    opensearch_hosts: List[str] = ["http://localhost:9200"]
    opensearch_timeout: int = 30
    opensearch_max_retries: int = 3
    opensearch_index_prefix: str = "hayat"

    @field_validator("opensearch_hosts", mode="before")
    @classmethod
    def parse_opensearch_hosts(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # Qdrant — Vector Embeddings
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "hayat-legal-embeddings"
    qdrant_vector_size: int = 3072  # text-embedding-3-large

    # RabbitMQ — Job Queue
    rabbitmq_url: str = "amqp://hayat:hayat_rabbit@localhost:5672/"
    rabbitmq_heartbeat: int = 600

    # AI / LLM
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1  # Low temperature for legal accuracy
    llm_max_tokens: int = 4096
    llm_timeout: int = 120

    # Legal Sources (Bangladesh)
    bangladesh_code_api_url: str = "https://api.bangladeshcode.gov.bd"
    supreme_court_api_url: str = "https://api.supremecourt.gov.bd"
    gazette_api_url: str = "https://api.gazette.gov.bd"

    # Processing
    max_upload_size_mb: int = 100
    supported_document_types: List[str] = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/html",
        "image/png",
        "image/jpeg",
        "image/tiff",
    ]
    ocr_dpi: int = 300
    ocr_language: str = "ben+eng"  # Bengali + English

    # Feature Flags
    enable_ai_layer: bool = True
    enable_knowledge_graph: bool = True
    enable_rule_engine: bool = True
    enable_analytics: bool = True
    enable_editorial_layer: bool = True

    # Monitoring
    sentry_dsn: Optional[str] = None
    prometheus_multiproc_dir: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance for performance."""
    return Settings()


settings = get_settings()
