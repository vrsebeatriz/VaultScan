import os
import yaml
import logging
from typing import List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

class EntropyConfig(BaseSettings):
    hex: float = 3.0
    base64: float = 4.5
    # Default bounds that can be adjusted via config

class ScanConfig(BaseSettings):
    exclude_paths: List[str] = Field(default_factory=list)
    exclude_extensions: List[str] = Field(default_factory=list)
    max_commits: int = 500
    entropy_threshold: EntropyConfig = Field(default_factory=EntropyConfig)
    
    model_config = SettingsConfigDict(
        env_prefix='VAULTSCAN_',
        env_nested_delimiter='__',
        extra='allow' # Allow extra to warn about unknown keys
    )
    
    @model_validator(mode='after')
    def warn_extra_fields(self) -> 'ScanConfig':
        if self.model_extra:
            for key in self.model_extra:
                logger.warning(f"Unknown configuration key ignored: {key}")
        return self

def load_config(path: str = "vaultscan.yml") -> ScanConfig:
    data = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    config = ScanConfig(**data)
    
    logger.info("VaultScan Configuration Loaded:")
    logger.info(f" - Exclude paths: {config.exclude_paths}")
    logger.info(f" - Exclude exts: {config.exclude_extensions}")
    logger.info(f" - Max commits: {config.max_commits}")
    
    return config
