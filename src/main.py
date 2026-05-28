import asyncio
import logging

from src.config import Config
from src.platforms.matrix_bot import MatrixBot


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = Config.from_env()
    bot = MatrixBot(config)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
