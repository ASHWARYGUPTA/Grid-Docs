import asyncio

from grid_unlocked.db.session import SessionLocal, init_db
from grid_unlocked.ingestion.csv_replay import replay_astram_csv


def main() -> None:
    async def _run() -> None:
        await init_db()
        async with SessionLocal() as session:
            stats = await replay_astram_csv(session, limit=100)
            print(stats)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
