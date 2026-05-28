import os
from dataclasses import dataclass, field


@dataclass
class Config:
    homeserver_url: str
    user_id: str
    access_token: str
    max_file_size_mb: int = 50
    download_dir: str = "/tmp/yt-dlp-bot"
    bot_prefix: str = "!"
    fetch_command: str = "fetch"

    @classmethod
    def from_env(cls) -> "Config":
        homeserver_url = os.environ["MATRIX_HOMESERVER_URL"]
        user_id = os.environ["MATRIX_USER_ID"]
        access_token = os.environ["MATRIX_ACCESS_TOKEN"]

        return cls(
            homeserver_url=homeserver_url,
            user_id=user_id,
            access_token=access_token,
            max_file_size_mb=int(os.environ.get("MAX_FILE_SIZE_MB", "50")),
            download_dir=os.environ.get("DOWNLOAD_DIR", "/tmp/yt-dlp-bot"),
            bot_prefix=os.environ.get("BOT_PREFIX", "!"),
            fetch_command=os.environ.get("FETCH_COMMAND", "fetch"),
        )
