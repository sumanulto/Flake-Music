import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import and_, select, update
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

neon_engine = None
mysql_engine = None
primary_engine = None
engine = None

runtime_engine = None

async_session_factory = None


def _set_runtime_engine(selected_engine) -> None:
    global runtime_engine, async_session_factory
    runtime_engine = selected_engine
    async_session_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("No database is enabled. Set USE_NEON_DB and/or USE_MYSQL_DB to true.")
    async with async_session_factory() as session:
        yield session

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("No database is enabled. Set USE_NEON_DB and/or USE_MYSQL_DB to true.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def _fetch_table_map(conn, table, primary_keys: list[str]) -> dict[tuple, dict]:
    result = await conn.execute(select(table))
    rows = result.mappings().all()
    row_map: dict[tuple, dict] = {}
    for row in rows:
        row_dict = dict(row)
        key = tuple(row_dict[pk] for pk in primary_keys)
        row_map[key] = row_dict
    return row_map


async def _apply_snapshot(conn, table, snapshot: dict[tuple, dict], primary_keys: list[str]) -> tuple[int, int]:
    current_map = await _fetch_table_map(conn, table, primary_keys)
    inserted = 0
    updated = 0

    for key, row in snapshot.items():
        if key not in current_map:
            await conn.execute(table.insert().values(**row))
            inserted += 1
            continue

        current_row = current_map[key]
        if current_row == row:
            continue

        update_values = {column: value for column, value in row.items() if column not in primary_keys}
        if not update_values:
            continue

        conditions = [table.c[pk] == row[pk] for pk in primary_keys]
        await conn.execute(update(table).where(and_(*conditions)).values(**update_values))
        updated += 1

    return inserted, updated


async def _delete_rows_not_in_snapshot(
    conn, table, snapshot: dict[tuple, dict], primary_keys: list[str]
) -> int:
    """Delete rows from `conn` whose primary keys are absent from `snapshot`."""
    current_map = await _fetch_table_map(conn, table, primary_keys)
    deleted = 0
    for key in current_map:
        if key not in snapshot:
            conditions = [table.c[pk] == val for pk, val in zip(primary_keys, key)]
            await conn.execute(table.delete().where(and_(*conditions)))
            deleted += 1
    return deleted


async def _sync_dual_databases() -> None:
    """Two-phase sync between NeonDB (primary) and MySQL (fallback).

    Phase 1 — NeonDB → MySQL  (additive only):
        Rows that exist in NeonDB but NOT in MySQL are inserted into MySQL.
        These are rows written to NeonDB while MySQL was unavailable.
        Conflicts (same PK, different data) are resolved in favour of MySQL.

    Phase 2 — MySQL → NeonDB  (full mirror, including deletes):
        NeonDB is brought to exactly match MySQL.
        Rows deleted from MySQL are deleted from NeonDB.
        Rows updated in MySQL are updated in NeonDB.

    Net effect:
        • Outage data survives (NeonDB → MySQL in Phase 1).
        • MySQL is the canonical truth for everything else.
        • Deletes propagate correctly from MySQL to NeonDB.
    """
    if neon_engine is None or mysql_engine is None:
        return

    logger.info("Both databases enabled. Starting NeonDB <-> MySQL synchronization.")

    async with neon_engine.begin() as neon_conn:
        async with mysql_engine.begin() as mysql_conn:
            for table in Base.metadata.sorted_tables:
                primary_keys = [col.name for col in table.primary_key.columns]
                if not primary_keys:
                    logger.warning("Skipping sync for table %s: no primary key.", table.name)
                    continue

                neon_map = await _fetch_table_map(neon_conn, table, primary_keys)
                mysql_map = await _fetch_table_map(mysql_conn, table, primary_keys)

                # --- Phase 1: NeonDB → MySQL (outage recovery, additive only) ---
                neon_only = {k: v for k, v in neon_map.items() if k not in mysql_map}
                ph1_inserted = 0
                for key, row in neon_only.items():
                    await mysql_conn.execute(table.insert().values(**row))
                    ph1_inserted += 1

                # Refresh mysql_map after Phase 1 inserts so Phase 2 is accurate
                if ph1_inserted:
                    mysql_map = await _fetch_table_map(mysql_conn, table, primary_keys)

                # --- Phase 2: MySQL → NeonDB (full mirror, MySQL is truth) ---
                ph2_inserted, ph2_updated = await _apply_snapshot(
                    neon_conn, table, mysql_map, primary_keys
                )
                ph2_deleted = await _delete_rows_not_in_snapshot(
                    neon_conn, table, mysql_map, primary_keys
                )

                logger.info(
                    "Synced table %s | Phase1 MySQL+%s | Phase2 NeonDB +%s ~%s -%s",
                    table.name,
                    ph1_inserted,
                    ph2_inserted,
                    ph2_updated,
                    ph2_deleted,
                )

    logger.info("Database synchronization completed.")


async def _init_schema_for_engine(engine_name: str, db_engine) -> bool:
    if db_engine is None:
        return False

    try:
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("%s schema initialized.", engine_name)
        return True
    except SQLAlchemyError as exc:
        logger.error("%s connection/init failed: %s", engine_name, exc)
        return False


async def init_db():
    global neon_engine, mysql_engine, primary_engine, engine

    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    USE_NEON_DB = _env_bool("USE_NEON_DB", True)
    USE_MYSQL_DB = _env_bool("USE_MYSQL_DB", False)

    NEON_DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://flake:flake_password@postgres:5432/flake_music",
    )
    if NEON_DATABASE_URL:
        if NEON_DATABASE_URL.startswith("postgresql://"):
            NEON_DATABASE_URL = NEON_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg does not support these query parameters
        NEON_DATABASE_URL = NEON_DATABASE_URL.replace("?sslmode=require&channel_binding=require", "")
        NEON_DATABASE_URL = NEON_DATABASE_URL.replace("?sslmode=require", "")
        NEON_DATABASE_URL = NEON_DATABASE_URL.replace("&sslmode=require", "")

    MYSQL_DATABASE_URL = os.getenv(
        "MYSQL_DATABASE_URL",
        "mysql+aiomysql://flake:flake_password@localhost:3306/flake_music",
    )

    if USE_NEON_DB:
        try:
            neon_engine = create_async_engine(
                NEON_DATABASE_URL,
                echo=True,
                pool_pre_ping=True,
                pool_recycle=240,
                pool_size=3,
                max_overflow=2,
            )
        except Exception as e:
            logger.error(f"Failed to initialize NeonDB engine: {e}")
            neon_engine = None
    if USE_MYSQL_DB:
        mysql_engine = create_async_engine(
            MYSQL_DATABASE_URL,
            echo=True,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    primary_engine = mysql_engine if mysql_engine is not None else neon_engine
    engine = primary_engine

    if not USE_NEON_DB and not USE_MYSQL_DB:
        logger.warning("Both USE_NEON_DB and USE_MYSQL_DB are false. Bot startup is blocked.")
        raise RuntimeError("No database enabled. Set at least one of USE_NEON_DB or USE_MYSQL_DB to true.")

    neon_ok = await _init_schema_for_engine("NeonDB", neon_engine) if USE_NEON_DB else False
    mysql_ok = await _init_schema_for_engine("MySQL", mysql_engine) if USE_MYSQL_DB else False

    if USE_NEON_DB and USE_MYSQL_DB and neon_ok and mysql_ok:
        await _sync_dual_databases()

    if mysql_ok:
        _set_runtime_engine(mysql_engine)
        return
        
    if neon_ok:
        _set_runtime_engine(neon_engine)
        return

    logger.warning("No reachable database found. Startup is blocked.")
    raise RuntimeError("No enabled database could be initialized. Check DATABASE_URL/MYSQL_DATABASE_URL.")
