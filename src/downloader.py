import os
import shutil
import subprocess
from dataclasses import dataclass

from src.config import Config


class FileTooLargeError(Exception):
    def __init__(self, file_size_mb: float, max_size_mb: int):
        self.file_size_mb = file_size_mb
        self.max_size_mb = max_size_mb
        super().__init__(
            f"File too large: {file_size_mb:.1f} MB (max {max_size_mb} MB)"
        )


class DownloadError(Exception):
    pass


@dataclass
class DownloadedFile:
    path: str
    title: str
    size_mb: float


class Downloader:
    def __init__(self, config: Config):
        self._config = config
        os.makedirs(config.download_dir, exist_ok=True)
        self._cookies_path: str | None = None
        if config.cookies_file:
            cookies_dest = os.path.join(config.download_dir, "cookies.txt")
            shutil.copy2(config.cookies_file, cookies_dest)
            self._cookies_path = cookies_dest

    def _run_ytdlp(self, args: list[str]) -> str:
        cmd = ["yt-dlp", "--no-playlist"]
        if self._cookies_path:
            cmd += ["--cookies", self._cookies_path]
        cmd += args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise DownloadError(
                f"yt-dlp failed:\n{result.stderr.strip() or result.stdout.strip()}"
            )
        return result.stdout.strip()

    def download(self, url: str) -> DownloadedFile:
        video_id = self._run_ytdlp(["--get-id", url])
        title = self._run_ytdlp(["--get-title", url])

        output_template = os.path.join(
            self._config.download_dir, "%(id)s.%(ext)s"
        )

        self._run_ytdlp(
            [
                "--merge-output-format",
                "mp4",
                "-o",
                output_template,
                url,
            ]
        )

        expected_path = os.path.join(self._config.download_dir, f"{video_id}.mp4")

        if not os.path.exists(expected_path):
            raise DownloadError(f"Downloaded file not found: {expected_path}")

        stat = os.stat(expected_path)
        size_mb = stat.st_size / (1024 * 1024)

        if size_mb > self._config.max_file_size_mb:
            os.unlink(expected_path)
            raise FileTooLargeError(size_mb, self._config.max_file_size_mb)

        return DownloadedFile(path=expected_path, title=title, size_mb=size_mb)

    def cleanup(self, filepath: str) -> None:
        try:
            os.unlink(filepath)
        except OSError:
            pass
