import asyncio
import logging

from app.logging_config import configure_logging
from app.services.hunter import scrape_jobs


async def main() -> None:
    configure_logging()
    count = await scrape_jobs()
    logging.getLogger(__name__).info("one-shot scrape complete", extra={"new_jobs": count})


if __name__ == "__main__":
    asyncio.run(main())
