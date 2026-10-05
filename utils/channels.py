from __future__ import annotations

import os

import discord
from discord.ext import commands


def _configured_role_id() -> int | None:
    value = os.getenv("ADMIN_ROLE_ID", "").strip()
    if not value:
        return None
    try:
        role_id = int(value)
    except ValueError:
        return None
    return role_id if role_id > 0 else None


async def require_admin_role(ctx: commands.Context) -> bool:
    """Allow management commands only to members with the configured role."""
    if not ctx.guild or not isinstance(ctx.author, discord.Member):
        return False

    role_id = _configured_role_id()
    if role_id is None:
        await ctx.send("Yönetim komutları kapalı: `.env` içinde geçerli bir `ADMIN_ROLE_ID` tanımlayın.")
        return False

    if ctx.author.get_role(role_id) is None:
        await ctx.send("Bu komut için gerekli yönetici rolüne sahip değilsin.")
        return False
    return True


def admin_role_only():
    return commands.check(require_admin_role)


async def require_channel(ctx: commands.Context, setting: str) -> bool:
    if not ctx.guild:
        return False
    settings = await ctx.bot.db.get_settings(ctx.guild.id)
    channel_id = settings.get(setting) if settings else None
    channel = ctx.guild.get_channel(channel_id) if channel_id else None
    if channel is None:
        await ctx.send("Kanal kurulumu yapılmamış. Önce `!kurulum` çalıştırılmalı.")
        return False
    if ctx.channel.id != channel.id:
        await ctx.send(f"Bu komut yalnızca {channel.mention} kanalında kullanılabilir.")
        return False
    return True


async def send_log(bot: commands.Bot, guild: discord.Guild, **kwargs) -> None:
    settings = await bot.db.get_settings(guild.id)
    channel_id = settings.get("log_channel") if settings else None
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel:
        await channel.send(**kwargs)
