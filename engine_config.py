import json

class Config:
    _config = {}

    @classmethod
    def load(cls, config_file: str):
        with open(config_file) as f:
            cls._config = json.load(f)

    @classmethod
    def get(cls, key: str, default=None):
        return cls._config.get(key, default)
