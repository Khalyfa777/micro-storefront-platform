import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        user="postgres",
        password="postgres",
        database="storefront_dev",
        host="127.0.0.1",
        port=5433,
    )
    print(await conn.fetchval("select current_database()"))
    await conn.close()

asyncio.run(main())
