"""Create only the isolated installation's empty tenant; never process/demo data."""
import asyncio
import json
import os
from uuid import UUID

import asyncpg


async def main():
    mapping = json.loads(os.environ["RPY_BEARER_TOKENS"])
    if len(mapping) != 1:
        raise RuntimeError("Homologation requires exactly one generated tenant")
    tenant = UUID(next(iter(mapping.values())))
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        await conn.execute(
            "INSERT INTO tenants(id, name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
            tenant, "Homologação local - Grupo Villela",
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
