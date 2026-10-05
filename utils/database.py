from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path or os.getenv("DATABASE_PATH", "data/mekanbot.sqlite3"))
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self.connection:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS ekonomi (
            user_id INTEGER PRIMARY KEY, bakiye INTEGER NOT NULL DEFAULT 500,
            son_maas REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS seviye_sistemi (
            user_id INTEGER PRIMARY KEY, xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1, son_mesaj REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sunucu_ayarlari (
            guild_id INTEGER PRIMARY KEY, log_channel INTEGER, game_channel INTEGER,
            music_channel INTEGER, chat_channel INTEGER, admin_channel INTEGER
        );
        """)
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
            "SELECT log_channel, game_channel, music_channel, chat_channel, admin_channel "
            "FROM sunucu_ayarlari WHERE guild_id = ?", (guild_id,))
        return dict(row) if row else None

    async def save_settings(self, guild_id: int, **channels: int | None) -> None:
        allowed = {"log_channel", "game_channel", "music_channel", "chat_channel", "admin_channel"}
        if set(channels) - allowed:
            raise ValueError("Unknown server setting")
        values = {key: channels.get(key) for key in allowed}
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute(
            """INSERT INTO sunucu_ayarlari
            (guild_id, log_channel, game_channel, music_channel, chat_channel, admin_channel)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
            log_channel=excluded.log_channel, game_channel=excluded.game_channel,
            music_channel=excluded.music_channel, chat_channel=excluded.chat_channel,
            admin_channel=excluded.admin_channel""",
            (guild_id, values["log_channel"], values["game_channel"], values["music_channel"],
             values["chat_channel"], values["admin_channel"]))
        await self.connection.commit()

    async def get_economy(self, user_id: int) -> dict[str, int | float]:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute("INSERT OR IGNORE INTO ekonomi (user_id) VALUES (?)", (user_id,))
        await self.connection.commit()
        return dict(await self._one("SELECT bakiye, son_maas FROM ekonomi WHERE user_id = ?", (user_id,)))

    async def add_balance(self, user_id: int, amount: int) -> int:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.get_economy(user_id)
        await self.connection.execute("UPDATE ekonomi SET bakiye=bakiye+? WHERE user_id=?", (amount, user_id))
        await self.connection.commit()
        return int((await self.get_economy(user_id))["bakiye"])

    async def try_withdraw(self, user_id: int, amount: int) -> bool:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.get_economy(user_id)
        cursor = await self.connection.execute(
            "UPDATE ekonomi SET bakiye=bakiye-? WHERE user_id=? AND bakiye>=?", (amount, user_id, amount))
        await self.connection.commit()
        return cursor.rowcount == 1

    async def claim_salary(self, user_id: int, now: float) -> tuple[bool, int, float]:
        data = await self.get_economy(user_id)
        cooldown = 6 * 3600 if data["son_maas"] else 0
        if now - float(data["son_maas"]) < cooldown:
            return False, int(data["bakiye"]), float(data["son_maas"])
        amount = 0 if not data["son_maas"] else 100
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute(
            "UPDATE ekonomi SET bakiye=bakiye+?, son_maas=? WHERE user_id=?", (amount, now, user_id))
        await self.connection.commit()
        return True, int(data["bakiye"]) + amount, now

    async def get_level(self, user_id: int) -> dict[str, int | float]:
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute("INSERT OR IGNORE INTO seviye_sistemi (user_id) VALUES (?)", (user_id,))
        await self.connection.commit()
        return dict(await self._one(
            "SELECT xp, level, son_mesaj FROM seviye_sistemi WHERE user_id=?", (user_id,)))

    async def add_xp(self, user_id: int, amount: int, now: float) -> dict[str, int | float]:
        data = await self.get_level(user_id)
        if now - float(data["son_mesaj"]) < 60:
            return data
        xp, level = int(data["xp"]) + amount, int(data["level"])
        while xp >= 100 * level**2:
            level += 1
        if not self.connection:
            raise RuntimeError("Database is not connected")
        await self.connection.execute(
            "UPDATE seviye_sistemi SET xp=?, level=?, son_mesaj=? WHERE user_id=?",
            (xp, level, now, user_id))
        await self.connection.commit()
        return {"xp": xp, "level": level, "son_mesaj": now}