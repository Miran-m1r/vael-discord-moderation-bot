from __future__ import annotations

import os
import asyncio
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path or os.getenv("DATABASE_PATH", "data/mekanbot.sqlite3"))
        self.connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.connection:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS ekonomi (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            bakiye INTEGER NOT NULL DEFAULT 500,
            son_maas REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS seviye_sistemi (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            son_mesaj REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS sunucu_ayarlari (
            guild_id INTEGER PRIMARY KEY,
            log_channel INTEGER,
            game_channel INTEGER,
            music_channel INTEGER,
            chat_channel INTEGER,
            admin_channel INTEGER,
            ticket_channel INTEGER,
            mod_role INTEGER,
            admin_role INTEGER,
            zindan_role INTEGER
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            float_value REAL NOT NULL,
            price INTEGER NOT NULL,
            image_url TEXT
        );
        CREATE TABLE IF NOT EXISTS sosyal_kredi (
            guild_id INTEGER,
            user_id INTEGER,
            puan INTEGER NOT NULL DEFAULT 100,
            PRIMARY KEY (guild_id, user_id)
        );
        """)

        # Migration checks for sunucu_ayarlari columns
        async with self.connection.execute("PRAGMA table_info(sunucu_ayarlari)") as cursor:
            setting_cols = [column["name"] for column in await cursor.fetchall()]
        for col in ("ticket_channel", "mod_role", "admin_role", "zindan_role"):
            if col not in setting_cols:
                await self.connection.execute(
                    f"ALTER TABLE sunucu_ayarlari ADD COLUMN {col} INTEGER"
                )

        # Migration checks for legacy tables missing guild_id
        async with self.connection.execute("PRAGMA table_info(ekonomi)") as cursor:
            ekonomi_cols = [c["name"] for c in await cursor.fetchall()]
        if ekonomi_cols and "guild_id" not in ekonomi_cols:
            await self.connection.execute("ALTER TABLE ekonomi ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")

        async with self.connection.execute("PRAGMA table_info(seviye_sistemi)") as cursor:
            seviye_cols = [c["name"] for c in await cursor.fetchall()]
        if seviye_cols and "guild_id" not in seviye_cols:
            await self.connection.execute("ALTER TABLE seviye_sistemi ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")

        async with self.connection.execute("PRAGMA table_info(inventory)") as cursor:
            inventory_cols = [c["name"] for c in await cursor.fetchall()]
        if inventory_cols and "guild_id" not in inventory_cols:
            await self.connection.execute("ALTER TABLE inventory ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")

        await self.connection.commit()

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def _one(self, query: str, params: tuple[Any, ...] = ()):
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def get_settings(self, guild_id: int) -> dict[str, int | None] | None:
        row = await self._one(
            "SELECT log_channel, game_channel, music_channel, chat_channel, admin_channel, "
            "ticket_channel, mod_role, admin_role, zindan_role "
            "FROM sunucu_ayarlari WHERE guild_id = ?", (guild_id,))
        return dict(row) if row else None

    async def save_settings(self, guild_id: int, **settings: int | None) -> None:
        allowed = {
            "log_channel", "game_channel", "music_channel", "chat_channel",
            "admin_channel", "ticket_channel", "mod_role", "admin_role", "zindan_role",
        }
        if set(settings) - allowed:
            raise ValueError("Unknown server setting")
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self._lock:
            existing = await self.get_settings(guild_id) or {}
            merged = {key: settings[key] if key in settings else existing.get(key) for key in allowed}
            await self.connection.execute(
                """INSERT INTO sunucu_ayarlari
                (guild_id, log_channel, game_channel, music_channel, chat_channel, admin_channel,
                 ticket_channel, mod_role, admin_role, zindan_role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                log_channel=excluded.log_channel, game_channel=excluded.game_channel,
                music_channel=excluded.music_channel, chat_channel=excluded.chat_channel,
                admin_channel=excluded.admin_channel, ticket_channel=excluded.ticket_channel,
                mod_role=excluded.mod_role, admin_role=excluded.admin_role,
                zindan_role=excluded.zindan_role""",
                (guild_id, merged["log_channel"], merged["game_channel"], merged["music_channel"],
                 merged["chat_channel"], merged["admin_channel"], merged["ticket_channel"],
                 merged["mod_role"], merged["admin_role"], merged["zindan_role"]))
            await self.connection.commit()

    async def get_economy(self, guild_id: int, user_id: int) -> dict[str, int | float]:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute(
            "INSERT OR IGNORE INTO ekonomi (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        await self.connection.commit()
        return dict(await self._one(
            "SELECT bakiye, son_maas FROM ekonomi WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ))

    async def add_balance(self, guild_id: int, user_id: int, amount: int) -> int:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self._lock:
            await self.connection.execute(
                "INSERT OR IGNORE INTO ekonomi (guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id),
            )
            await self.connection.execute(
                "UPDATE ekonomi SET bakiye=bakiye+? WHERE guild_id=? AND user_id=?",
                (amount, guild_id, user_id),
            )
            await self.connection.commit()
            row = await self._one(
                "SELECT bakiye FROM ekonomi WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            )
            return int(row["bakiye"])

    async def try_withdraw(self, guild_id: int, user_id: int, amount: int) -> bool:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        if amount <= 0:
            return False
        async with self._lock:
            await self.connection.execute(
                "INSERT OR IGNORE INTO ekonomi (guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id),
            )
            cursor = await self.connection.execute(
                "UPDATE ekonomi SET bakiye=bakiye-? WHERE guild_id=? AND user_id=? AND bakiye>=?",
                (amount, guild_id, user_id, amount),
            )
            await self.connection.commit()
            return cursor.rowcount == 1

    async def try_withdraw_pair(self, guild_id: int, first_user_id: int, second_user_id: int, amount: int) -> bool:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        if amount <= 0 or first_user_id == second_user_id:
            return False
        async with self._lock:
            await self.connection.execute(
                "INSERT OR IGNORE INTO ekonomi (guild_id, user_id) VALUES (?, ?)",
                (guild_id, first_user_id),
            )
            await self.connection.execute(
                "INSERT OR IGNORE INTO ekonomi (guild_id, user_id) VALUES (?, ?)",
                (guild_id, second_user_id),
            )
            async with self.connection.execute(
                "SELECT user_id, bakiye FROM ekonomi WHERE guild_id = ? AND user_id IN (?, ?)",
                (guild_id, first_user_id, second_user_id),
            ) as cursor:
                balances = {int(row["user_id"]): int(row["bakiye"]) for row in await cursor.fetchall()}
            if balances.get(first_user_id, 0) < amount or balances.get(second_user_id, 0) < amount:
                return False
            await self.connection.execute(
                "UPDATE ekonomi SET bakiye = bakiye - ? WHERE guild_id = ? AND user_id IN (?, ?)",
                (amount, guild_id, first_user_id, second_user_id),
            )
            await self.connection.commit()
            return True

    async def claim_salary(self, guild_id: int, user_id: int, now: float) -> tuple[bool, int, float]:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self._lock:
            await self.connection.execute(
                "INSERT OR IGNORE INTO ekonomi (guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id),
            )
            row = await self._one(
                "SELECT bakiye, son_maas FROM ekonomi WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            )
            last = float(row["son_maas"])
            cooldown = 6 * 3600 if last else 0
            if now - last < cooldown:
                return False, int(row["bakiye"]), last
            amount = 500 if not last else 100
            await self.connection.execute(
                "UPDATE ekonomi SET bakiye=bakiye+?, son_maas=? WHERE guild_id=? AND user_id=?",
                (amount, now, guild_id, user_id),
            )
            await self.connection.commit()
            return True, int(row["bakiye"]) + amount, now

    async def get_level(self, guild_id: int, user_id: int) -> dict[str, int | float]:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute(
            "INSERT OR IGNORE INTO seviye_sistemi (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        await self.connection.commit()
        return dict(await self._one(
            "SELECT xp, level, son_mesaj FROM seviye_sistemi WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ))

    async def add_xp(self, guild_id: int, user_id: int, amount: int, now: float) -> dict[str, int | float]:
        data = await self.get_level(guild_id, user_id)
        if now - float(data["son_mesaj"]) < 60:
            return data
        xp, level = int(data["xp"]) + amount, int(data["level"])
        while xp >= 100 * level**2:
            level += 1
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute(
            "UPDATE seviye_sistemi SET xp=?, level=?, son_mesaj=? WHERE guild_id=? AND user_id=?",
            (xp, level, now, guild_id, user_id),
        )
        await self.connection.commit()
        return {"xp": xp, "level": level, "son_mesaj": now}

    async def add_inventory_item(
        self, guild_id: int, user_id: int, item_name: str, rarity: str, float_value: float, price: int,
        image_url: str | None = None
    ) -> int:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self._lock:
            cursor = await self.connection.execute(
                """INSERT INTO inventory (guild_id, user_id, item_name, rarity, float_value, price, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (guild_id, user_id, item_name, rarity, float_value, price, image_url),
            )
            await self.connection.commit()
            return int(cursor.lastrowid)

    async def list_inventory(self, guild_id: int, user_id: int, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self.connection.execute(
            """SELECT id, item_name, rarity, float_value, price, image_url
               FROM inventory WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?""",
            (guild_id, user_id, limit, offset),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def count_inventory(self, guild_id: int, user_id: int) -> int:
        row = await self._one("SELECT COUNT(*) AS count FROM inventory WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        return int(row["count"])

    async def owns_inventory_item(self, guild_id: int, user_id: int, item_id: int) -> bool:
        row = await self._one(
            "SELECT 1 FROM inventory WHERE id = ? AND guild_id = ? AND user_id = ?", (item_id, guild_id, user_id)
        )
        return row is not None

    async def sell_inventory_item(self, guild_id: int, user_id: int, item_id: int) -> int | None:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self._lock:
            row = await self._one(
                "SELECT price FROM inventory WHERE id = ? AND guild_id = ? AND user_id = ?", (item_id, guild_id, user_id)
            )
            if row is None:
                return None
            await self.connection.execute(
                "INSERT OR IGNORE INTO ekonomi (guild_id, user_id) VALUES (?, ?)",
                (guild_id, user_id),
            )
            await self.connection.execute(
                "DELETE FROM inventory WHERE id = ? AND guild_id = ? AND user_id = ?",
                (item_id, guild_id, user_id),
            )
            await self.connection.execute(
                "UPDATE ekonomi SET bakiye = bakiye + ? WHERE guild_id = ? AND user_id = ?",
                (int(row["price"]), guild_id, user_id),
            )
            await self.connection.commit()
            return int(row["price"])

    async def transfer_inventory_item(self, guild_id: int, sender_id: int, receiver_id: int, item_id: int) -> dict[str, Any] | None:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self._lock:
            row = await self._one(
                "SELECT id, item_name, rarity, float_value, price, image_url FROM inventory "
                "WHERE id = ? AND guild_id = ? AND user_id = ?",
                (item_id, guild_id, sender_id),
            )
            if row is None:
                return None
            await self.connection.execute(
                "UPDATE inventory SET user_id = ? WHERE id = ? AND guild_id = ? AND user_id = ?",
                (receiver_id, item_id, guild_id, sender_id),
            )
            await self.connection.commit()
            return dict(row)

    async def get_trust_score(self, guild_id: int, user_id: int) -> int:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute(
            "INSERT OR IGNORE INTO sosyal_kredi (guild_id, user_id, puan) VALUES (?, ?, 100)",
            (guild_id, user_id),
        )
        await self.connection.commit()
        row = await self._one(
            "SELECT puan FROM sosyal_kredi WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return int(row["puan"]) if row else 100

    async def update_trust_score(self, guild_id: int, user_id: int, amount: int) -> int:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        async with self._lock:
            await self.connection.execute(
                "INSERT OR IGNORE INTO sosyal_kredi (guild_id, user_id, puan) VALUES (?, ?, 100)",
                (guild_id, user_id),
            )
            await self.connection.execute(
                "UPDATE sosyal_kredi SET puan = puan + ? WHERE guild_id = ? AND user_id = ?",
                (amount, guild_id, user_id),
            )
            await self.connection.commit()
            row = await self._one(
                "SELECT puan FROM sosyal_kredi WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            return int(row["puan"])
