"""config/settings.py — Central settings loaded from .env"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # GCP
    gcp_project_id: str = "local"
    gcp_region: str = "us-central1"

    # Vertex / Claude
    vertex_claude_model: str = "claude-sonnet-4-6"
    vertex_claude_location: str = "us-east5"

    # Vector Store
    vector_store_backend: str = "chroma"
    chroma_persist_dir: str = "./data/chroma_db"
    vertex_index_id: str = ""
    vertex_endpoint_id: str = ""
    vertex_deployed_index_id: str = ""
    embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768

    # MCP Gateway
    mcp_gateway_url: str = "http://localhost:8080"
    mcp_gateway_api_key: str = "local-dev-key"

    # Auth
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_idp_url: str = ""

    # Cache
    redis_url: str = "redis://localhost:6379/0"
    use_fake_redis: bool = True
    anthropic_api_key: str = ""
    anthropic_api_key: str = ""

    # GCS
    gcs_bucket: str = "nakoba-rag-data"

    # BigQuery
    bq_dataset: str = "nakoba_audit"
    bq_audit_table: str = "gateway_events"

    # HITL
    hitl_slack_webhook: str = ""

    # Live source systems
    zabbix_url: str = ""
    zabbix_token: str = ""
    dynatrace_url: str = ""
    dynatrace_token: str = ""
    servicenow_url: str = ""
    servicenow_user: str = ""
    servicenow_pass: str = ""
    jira_url: str = ""
    jira_email: str = ""
    jira_token: str = ""
    confluence_url: str = ""
    confluence_token: str = ""
    gcp_obs_project: str = ""
    sentinel_one_url: str = ""
    sentinel_one_token: str = ""
    puppet_url: str = ""
    puppet_token: str = ""
    leanix_url: str = ""
    leanix_token: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()