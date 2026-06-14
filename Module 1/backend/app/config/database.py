"""
SQLite database initialization and connection management.

Creates all required tables and seeds configuration data on startup.
"""

import aiosqlite
import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "second_life.db")


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """Initialize the database schema and seed default configuration data."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await _create_tables(db)
        await _seed_return_windows(db)
        await _seed_category_weights(db)
        await _seed_cost_lookup(db)
        await db.commit()


async def _create_tables(db: aiosqlite.Connection) -> None:
    """Create all required tables."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS returns (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            category TEXT NOT NULL,
            delivery_date TEXT NOT NULL,
            initiated_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'initiated',
            qa_answers TEXT,
            media_uris TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS health_cards (
            id TEXT PRIMARY KEY,
            return_id TEXT NOT NULL REFERENCES returns(id),
            health_card_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS cost_lookup (
            category TEXT PRIMARY KEY,
            reverse_logistics REAL NOT NULL,
            inspection REAL NOT NULL,
            refurbishment REAL NOT NULL,
            storage REAL NOT NULL,
            total_processing_cost REAL GENERATED ALWAYS AS (
                reverse_logistics + inspection + refurbishment + storage
            ) STORED
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS category_weights (
            category TEXT PRIMARY KEY,
            w1_anomaly REAL NOT NULL DEFAULT 30.0,
            w2_defect REAL NOT NULL DEFAULT 25.0,
            w3_reason REAL NOT NULL DEFAULT 20.0,
            w4_wear REAL NOT NULL DEFAULT 25.0
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS return_windows (
            category TEXT PRIMARY KEY,
            window_days INTEGER NOT NULL DEFAULT 30
        )
    """)


async def _seed_return_windows(db: aiosqlite.Connection) -> None:
    """Seed return window configuration with default values."""
    windows = [
        ("Food & Grocery", 7),
        ("Electronics", 30),
        ("Clothing & Footwear", 15),
        ("Other", 30),
    ]
    await db.executemany(
        "INSERT OR IGNORE INTO return_windows (category, window_days) VALUES (?, ?)",
        windows,
    )


async def _seed_category_weights(db: aiosqlite.Connection) -> None:
    """Seed category weight configuration with default values."""
    weights = [
        ("Food & Grocery", 20.0, 30.0, 30.0, 20.0),
        ("Electronics", 30.0, 25.0, 25.0, 20.0),
        ("Clothing & Footwear", 20.0, 20.0, 20.0, 40.0),
        ("Other", 25.0, 25.0, 25.0, 25.0),
    ]
    await db.executemany(
        """INSERT OR IGNORE INTO category_weights
           (category, w1_anomaly, w2_defect, w3_reason, w4_wear)
           VALUES (?, ?, ?, ?, ?)""",
        weights,
    )


async def _seed_cost_lookup(db: aiosqlite.Connection) -> None:
    """Seed cost lookup table with default processing costs per category."""
    costs = [
        ("Food & Grocery", 50.0, 20.0, 10.0, 15.0),
        ("Electronics", 200.0, 150.0, 300.0, 100.0),
        ("Clothing & Footwear", 80.0, 50.0, 60.0, 30.0),
        ("Other", 100.0, 75.0, 100.0, 50.0),
    ]
    await db.executemany(
        """INSERT OR IGNORE INTO cost_lookup
           (category, reverse_logistics, inspection, refurbishment, storage)
           VALUES (?, ?, ?, ?, ?)""",
        costs,
    )
