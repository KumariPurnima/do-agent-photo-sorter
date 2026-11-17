from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Agent Photo Sorter"
    digitalocean_token: str = ""
    harness_inference_api_key: str = ""
    harness_inference_model: str = "anthropic-claude-sonnet-4-5"
    harness_spec_path: str = "harness/photo-sorter.yaml"

    spaces_key: str = ""
    spaces_secret: str = ""
    spaces_region: str = "nyc3"
    spaces_bucket: str = ""
    spaces_endpoint: str = ""
    spaces_cdn_endpoint: str = ""

    # If set, API will shell out to doctl; otherwise sessions are simulated for local UI demos.
    doctl_bin: str = "doctl"
    demo_mode: bool = True

    # When app_password is set, HTTP Basic Auth protects the site (except /api/health).
    app_username: str = "admin"
    app_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
