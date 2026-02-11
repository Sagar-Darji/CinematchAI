"""Application settings using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="CineMatch AI", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # LLM Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama server URL"
    )
    ollama_model_main: str = Field(
        default="llama3.1:70b", description="Main Ollama model for complex tasks"
    )
    ollama_model_fast: str = Field(
        default="llama3.1:8b", description="Fast Ollama model for simple tasks"
    )

    # Groq API (Backup)
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key")

    # TMDB API
    tmdb_api_key: Optional[str] = Field(default=None, description="TMDB API key")
    tmdb_rate_limit: int = Field(
        default=40, description="TMDB API rate limit (requests per 10 seconds)"
    )

    # Vector Database
    chroma_persist_dir: Path = Field(
        default=Path("./data/vectordb"), description="Chroma persistence directory"
    )
    chroma_collection_movies: str = Field(
        default="cinematch_movies", description="Chroma collection name for movies"
    )
    chroma_collection_users: str = Field(
        default="cinematch_users", description="Chroma collection name for users"
    )

    # API Settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")

    # Streamlit Settings
    streamlit_server_port: int = Field(default=8501, description="Streamlit server port")
    streamlit_server_address: str = Field(
        default="0.0.0.0", description="Streamlit server address"
    )

    # Recommendation Settings
    default_num_recommendations: int = Field(
        default=10, description="Default number of recommendations"
    )
    max_recommendations: int = Field(default=50, description="Maximum number of recommendations")
    exploration_rate: float = Field(
        default=0.3, description="Exploration rate for serendipity (0-1)"
    )

    # Cache Settings
    cache_dir: Path = Field(default=Path("./cache"), description="Cache directory")
    cache_ttl_hours: int = Field(default=1, description="Default cache TTL in hours")
    profile_cache_ttl_minutes: int = Field(
        default=60, description="User profile cache TTL in minutes"
    )
    recommendation_cache_ttl_minutes: int = Field(
        default=15, description="Recommendation cache TTL in minutes"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./data/cinematch.db", description="Database URL"
    )

    # Embedding Settings
    text_embedding_model: str = Field(
        default="sentence-transformers/all-mpnet-base-v2",
        description="Text embedding model",
    )
    image_embedding_model: str = Field(
        default="openai/clip-vit-base-patch32", description="Image embedding model"
    )
    hybrid_text_weight: float = Field(
        default=0.7, description="Weight for text embeddings in hybrid mode"
    )
    hybrid_image_weight: float = Field(
        default=0.3, description="Weight for image embeddings in hybrid mode"
    )

    # Deployment
    deployment_env: str = Field(
        default="development", description="Deployment environment (development, staging, production)"
    )
    hf_space: bool = Field(default=False, description="Running on Hugging Face Spaces")

    # Data Paths
    data_dir: Path = Field(default=Path("./data"), description="Data directory")
    raw_data_dir: Path = Field(default=Path("./data/raw"), description="Raw data directory")
    processed_data_dir: Path = Field(
        default=Path("./data/processed"), description="Processed data directory"
    )
    embeddings_dir: Path = Field(
        default=Path("./data/embeddings"), description="Embeddings directory"
    )

    @field_validator("exploration_rate")
    @classmethod
    def validate_exploration_rate(cls, v: float) -> float:
        """Validate exploration rate is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("exploration_rate must be between 0 and 1")
        return v

    @field_validator("hybrid_text_weight", "hybrid_image_weight")
    @classmethod
    def validate_weights(cls, v: float) -> float:
        """Validate embedding weights are between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Embedding weights must be between 0 and 1")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.deployment_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.deployment_env == "development"

    def create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.data_dir,
            self.raw_data_dir,
            self.processed_data_dir,
            self.embeddings_dir,
            self.chroma_persist_dir,
            self.cache_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
