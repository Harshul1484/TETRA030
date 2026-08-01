from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "curricualign"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5"
    chroma_path: str = "/app/data/chroma"
    llm_cache_path: str = "/app/data/llm_cache"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
