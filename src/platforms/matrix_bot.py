import asyncio
import logging
import os
import signal
import traceback

import nio

from src.bot import Bot
from src.config import Config
from src.downloader import DownloadError, Downloader, FileTooLargeError
from src.sync_store import SyncStore

logger = logging.getLogger(__name__)


class MatrixBot(Bot):
    def __init__(self, config: Config):
        self._config = config
        self._downloader = Downloader(config)
        self._store = SyncStore(config)
        self._client = nio.AsyncClient(
            homeserver=config.homeserver_url,
            user=config.user_id,
        )
        self._client.access_token = config.access_token
        self._running = True

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, self._shutdown)
        loop.add_signal_handler(signal.SIGTERM, self._shutdown)

        self._client.add_event_callback(self._on_message, nio.RoomMessageText)

        sync_token = self._store.load()

        if sync_token is None:
            logger.info("No saved sync token, catching up on history...")
            response = await self._client.sync(timeout=30000)
            if isinstance(response, nio.SyncResponse):
                sync_token = response.next_batch
                self._store.save(sync_token)
                logger.info("Caught up, resuming from %s", sync_token)
            elif isinstance(response, nio.SyncError):
                logger.error("Initial sync error: %s", response.message)

        while self._running:
            try:
                response = await self._client.sync(
                    timeout=30000,
                    since=sync_token,
                )
                if isinstance(response, nio.SyncResponse):
                    sync_token = response.next_batch
                    self._store.save(sync_token)
                elif isinstance(response, nio.SyncError):
                    logger.error("Sync error: %s", response.message)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Sync exception:\n%s", traceback.format_exc())

        await self._client.close()
        logger.info("Bot shutdown complete")

    def _shutdown(self) -> None:
        logger.info("Shutting down...")
        self._running = False

    async def _on_message(self, room: nio.MatrixRoom, event: nio.RoomMessageText) -> None:
        if event.sender == self._config.user_id:
            return

        prefix = self._config.bot_prefix + self._config.fetch_command
        body = event.body.strip()

        if not body.startswith(prefix):
            return

        url = body[len(prefix):].strip()
        if not url:
            await self._send_text(room.room_id, event.event_id, "Usage: !fetch <URL>")
            return

        logger.info("Downloading: %s (requested by %s)", url, event.sender)

        try:
            loop = asyncio.get_running_loop()
            downloaded = await loop.run_in_executor(
                None, self._downloader.download, url
            )
        except FileTooLargeError as e:
            await self._send_text(
                room.room_id,
                event.event_id,
                f"Video too large: {e.file_size_mb:.1f} MB (max {e.max_size_mb} MB)",
            )
            return
        except DownloadError as e:
            await self._send_text(
                room.room_id,
                event.event_id,
                f"Download failed: {e}",
            )
            return
        except Exception as e:
            logger.error("Unexpected error:\n%s", traceback.format_exc())
            await self._send_text(
                room.room_id,
                event.event_id,
                f"Unexpected error: {e}",
            )
            return

        try:
            await self._send_video(room.room_id, event.event_id, downloaded.path)
        finally:
            self._downloader.cleanup(downloaded.path)

    async def _send_text(self, room_id: str, reply_to: str, text: str) -> None:
        content = {
            "msgtype": "m.text",
            "body": text,
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": reply_to,
                },
            },
        }
        await self._client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
        )

    async def _send_video(
        self, room_id: str, reply_to: str, filepath: str
    ) -> None:
        filename = os.path.basename(filepath)
        stat = os.stat(filepath)

        upload_response, _ = await self._client.upload(
            lambda got_429, got_timeouts: open(filepath, "rb"),
            content_type="video/mp4",
            filename=filename,
            filesize=stat.st_size,
        )

        if not isinstance(upload_response, nio.UploadResponse):
            logger.error("Upload failed: %s", upload_response)
            await self._send_text(room_id, reply_to, "Failed to upload video.")
            return

        content = {
            "msgtype": "m.video",
            "body": filename,
            "info": {
                "size": stat.st_size,
                "mimetype": "video/mp4",
            },
            "url": upload_response.content_uri,
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": reply_to,
                },
            },
        }

        await self._client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
        )

        logger.info("Sent video: %s to %s", filename, room_id)