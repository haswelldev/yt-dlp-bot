import json
import os

from src.config import Config


class SyncStore:
    def __init__(self, config: Config):
        self._path = os.path.join(config.download_dir, "sync_token.json")

    def load(self) -> str | None:
        try:
            with open(self._path) as f:
                data = json.load(f)
            return data.get("next_batch")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None

    def save(self, token: str) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump({"next_batch": token}, f)