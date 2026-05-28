# yt-dlp-bot

A chat bot that downloads videos via [yt-dlp](https://github.com/yt-dlp/yt-dlp) and sends them as replies. Currently supports Matrix, with an extensible architecture for adding more platforms (Telegram, Discord, etc.).

## Usage

In any room the bot has joined, type:

```
!fetch https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

The bot will download the video and send it as a reply. If the file exceeds the configured size limit, it will respond with an error message.

## Configuration

All configuration is done via environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `MATRIX_HOMESERVER_URL` | Yes | — | Matrix homeserver URL (e.g. `https://matrix.org`) |
| `MATRIX_USER_ID` | Yes | — | Bot's Matrix user ID (e.g. `@bot:matrix.org`) |
| `MATRIX_ACCESS_TOKEN` | Yes | — | Bot's Matrix access token |
| `MAX_FILE_SIZE_MB` | No | `50` | Maximum file size in MB; files exceeding this are rejected |
| `DOWNLOAD_DIR` | No | `/tmp/yt-dlp-bot` | Directory for temporary video downloads |
| `COOKIES_FILE` | No | — | Path to a Netscape-format cookies file for yt-dlp (see below) |
| `BOT_PREFIX` | No | `!` | Command prefix character |
| `FETCH_COMMAND` | No | `fetch` | Command name (combined with prefix, e.g. `!fetch`) |

### Cookie-based authentication

YouTube may require authentication to verify you're not a bot. If you see errors like `Sign in to confirm you're not a bot`, you need to provide browser cookies to yt-dlp:

1. Install the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/ccleldeahabstforpzhmbaelsjhjcbmm) browser extension
2. Export cookies for `youtube.com` in Netscape format
3. Save the file as `cookies.txt` in a directory visible to the bot

In Docker, mount the cookies file and point `COOKIES_FILE` to it:

```yaml
services:
  yt-dlp-bot:
    image: ghcr.io/haswelldev/yt-dlp-bot:main
    env_file: .env
    restart: unless-stopped
    volumes:
      - downloads:/tmp/yt-dlp-bot
      - ./cookies.txt:/app/cookies.txt:ro
    environment:
      - COOKIES_FILE=/app/cookies.txt
```

### Getting a Matrix access token

1. Log in to your Matrix account (preferably a dedicated bot account)
2. In Element, go to Settings → Help & About → Advanced
3. Copy the access token

Or use `curl`:

```bash
curl -XPOST "https://matrix.org/_matrix/client/v3/login" -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"botusername"},"password":"botpassword"}'
```

## Deployment

### Docker Compose (recommended)

A pre-built Docker image is available at `ghcr.io/haswelldev/yt-dlp-bot`.

1. Create a `.env` file from the template:

```bash
cp .env.example .env
# Edit .env with your Matrix credentials
```

2. Deploy with Docker Compose:

```yaml
# docker-compose.yml
services:
  yt-dlp-bot:
    image: ghcr.io/haswelldev/yt-dlp-bot:main
    env_file: .env
    restart: unless-stopped
    volumes:
      - downloads:/tmp/yt-dlp-bot
      # Uncomment the next line if you need cookies for YouTube auth:
      # - ./cookies.txt:/app/cookies.txt:ro

volumes:
  downloads:
```

Then run:

```bash
docker compose up -d
```

### Build from source

Alternatively, build the image yourself:

```bash
git clone https://github.com/haswelldev/yt-dlp-bot.git
cd yt-dlp-bot
docker compose up -d
```

This uses the included `Dockerfile` and `docker-compose.yml` which build from source.

### Running locally (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export MATRIX_HOMESERVER_URL=https://matrix.org
export MATRIX_USER_ID=@bot:matrix.org
export MATRIX_ACCESS_TOKEN=syt_...

python -m src.main
```

## Architecture

```
src/
├── main.py              # Entry point
├── config.py            # Environment variable configuration
├── downloader.py        # yt-dlp wrapper with size checks
├── bot.py               # Abstract Bot interface
└── platforms/
    └── matrix_bot.py    # Matrix implementation
```

The `Bot` abstract base class defines a minimal interface (`run()`). Adding a new platform requires implementing this interface and registering it in `main.py`. The `Downloader` and `Config` are shared across all platforms.

### Adding a new platform

1. Create `src/platforms/telegram_bot.py` implementing the `Bot` ABC
2. Add platform selection logic in `src/main.py`
3. Add any platform-specific config to `src/config.py`

## License

MIT