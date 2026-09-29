from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class BrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=('.env', 'private/atlas.env'), extra='ignore')
    cors_origins: list[str] = []

class Settings(BrowserSettings):
    mongo_uri: str = 'mongodb://localhost:27017/?replicaSet=rs0'
    mongo_database: str = 'assurex'
    redis_url: str = 'redis://localhost:6379/0'
    session_secret: str = Field(min_length=32)
    cookie_secure: bool = True
    evidence_root: Path = Path('private/evidence')
    artifact_root: Path = Path('artifacts')
    summary_model: str = './artifacts/summary'
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 10
