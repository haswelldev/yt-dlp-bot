import glob
import os
import shutil
import subprocess
import sys
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
        cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist"]
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

    def _needs_transcode(self, filepath: str) -> bool:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "csv=p=0",
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        video_codec = result.stdout.strip()
        return video_codec not in ("h264", "avc1", "")

    def _transcode(self, filepath: str) -> str:
        output = filepath.rsplit(".", 1)[0] + "_h264.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", filepath,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output,
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=True,
        )
        os.unlink(filepath)
        return output

    def download(self, url: str) -> DownloadedFile:
        video_id = self._run_ytdlp(["--get-id", url])
        title = self._run_ytdlp(["--get-title", url])

        output_template = os.path.join(
            self._config.download_dir, f"{video_id}.%(ext)s"
        )

        try:
            self._run_ytdlp(
                [
                    "-S", "vcodec:h264,res:1080",
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    output_template,
                    url,
                ]
            )
        except DownloadError:
            self._run_ytdlp(
                [
                    "-f", "bestvideo+bestaudio/best",
                    "-o",
                    output_template,
                    url,
                ]
            )

        downloaded = self._find_file(video_id)
        if not downloaded:
            raise DownloadError(
                f"Downloaded file not found for video {video_id}"
            )

        if self._needs_transcode(downloaded):
            downloaded = self._transcode(downloaded)

        stat = os.stat(downloaded)
        size_mb = stat.st_size / (1024 * 1024)

        if size_mb > self._config.max_file_size_mb:
            os.unlink(downloaded)
            raise FileTooLargeError(size_mb, self._config.max_file_size_mb)

        return DownloadedFile(path=downloaded, title=title, size_mb=size_mb)

    def _find_file(self, video_id: str) -> str | None:
        pattern = os.path.join(self._config.download_dir, f"{video_id}.*")
        matches = glob.glob(pattern)
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        for match in sorted(matches, key=lambda f: os.path.getsize(f), reverse=True):
            if os.path.splitext(match)[1].lower() not in image_extensions:
                return match
        return matches[0] if matches else None

    def cleanup(self, filepath: str) -> None:
        try:
            os.unlink(filepath)
        except OSError:
            pass