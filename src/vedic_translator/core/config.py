"""Application configuration loaded from environment variables and YAML files."""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelStageConfig(BaseModel):
    """Configuration for a specific translation pipeline stage."""

    provider: str = "gemini"
    model: str = "gemini-2.5-pro"
    temperature: float = 0.2


class PipelineConfig(BaseModel):
    """Configuration for the 4-stage pipeline and concurrency."""

    literal_stage: ModelStageConfig = Field(
        default_factory=lambda: ModelStageConfig(
            provider="gemini", model="gemini-2.5-pro", temperature=0.1
        )
    )
    philosophical_stage: ModelStageConfig = Field(
        default_factory=lambda: ModelStageConfig(
            provider="anthropic", model="claude-3-7-sonnet-20250219", temperature=0.2
        )
    )
    literary_stage: ModelStageConfig = Field(
        default_factory=lambda: ModelStageConfig(provider="openai", model="gpt-4o", temperature=0.3)
    )
    terminology_stage: ModelStageConfig = Field(
        default_factory=lambda: ModelStageConfig(
            provider="gemini", model="gemini-2.5-pro", temperature=0.0
        )
    )
    max_parallel_blocks: int = 4
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 100000
    max_retries: int = 5
    base_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 60.0


class QualityControlConfig(BaseModel):
    """Thresholds for automated quality auditing."""

    min_terminology_fidelity_score: float = 99.0
    min_diacritics_completeness_score: float = 98.0
    enforce_verse_structural_invariance: bool = True
    min_length_ratio: float = 0.90
    max_length_ratio: float = 1.55


class AppSettings(BaseSettings):
    """Global settings for Vedic Book Translator."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # API Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    # Local LLM Endpoint
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "llama3:latest"

    # Default Providers
    default_translation_provider: str = "gemini"
    default_translation_model: str = "gemini-2.5-pro"

    # Paths & Storage
    database_url: str = "sqlite:///./data/vedic_translator.db"
    translation_memory_store: str = "./data/translation_memory.jsonl"
    checkpoint_dir: str = "./data/checkpoints"

    # Sub-configurations
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    qc: QualityControlConfig = Field(default_factory=QualityControlConfig)


# Global singleton instance
settings = AppSettings()
