from __future__ import annotations

import os

import discord
from discord.ext import commands

try:
    from discord import app_commands
except ImportError:
    app_commands = None


CommandContext = discord.ApplicationContext | discord.Interaction


def _guild(context: CommandContext) -> discord.Guild | None:
    return context.guild


def _author(context: CommandContext) -> discord.User | discord.Member:
    author = getattr(context, "author", None)
    return author if author is not None else context.user


def _channel(context: CommandContext) -> discord.abc.GuildChannel | None:
    return context.channel


async def _send(context: CommandContext, content: str):
    response = getattr(context, "response", None)
    if response is not None:
        if context.response.is_done():
            return await context.followup.send(content)
        return await context.response.send_message(content)
    return await context.send(content)


def _configured_role_id() -> int | None:
    value = os.getenv("ADMIN_ROLE_ID", "").strip()
    if not value:
        return None
    try:
        role_id = int(value)
    except ValueError:
        return None
    return role_id if role_id > 0 else None


async def require_admin_role(context: CommandContext) -> bool:
    """Allow management commands only to members with the configured role."""
    guild = _guild(context)
    author = _author(context)
    if not guild or not isinstance(author, discord.Member):
        return False

    role_id = _configured_role_id()
    if role_id is None:
        await _send(context, "Yönetim komutları kapalı: `.env` içinde geçerli bir `ADMIN_ROLE_ID` tanımlayın.")
        return False

    if author.get_role(role_id) is None:
        await _send(context, "Bu komut için gerekli yönetici rolüne sahip değilsin.")
        return False
    return True


def admin_role_only():
    def decorator(command):
        command = commands.check(require_admin_role)(command)
        if app_commands is not None:
            command = app_commands.check(require_admin_role)(command)
        return command

    return decorator


async def require_channel(context: CommandContext, setting: str) -> bool:
    """Ensure a command is used in the configured channel."""
    guild = _guild(context)
    if not guild:
        return False
    bot = getattr(context, "bot", None) or getattr(context, "client", None)
    settings = await bot.db.get_settings(guild.id)
    channel_id = settings.get(setting) if settings else None
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel is None:
        await _send(context, "Kanal kurulumu yapılmamış. Önce `/kurulum` çalıştırılmalı.")
        return False
    current_channel = _channel(context)
    if current_channel is None or current_channel.id != channel.id:
        await _send(context, f"Bu komut yalnızca {channel.mention} kanalında kullanılabilir.")
        return False
    return True


async def send_log(bot: commands.Bot, guild: discord.Guild, **kwargs) -> None:
    settings = await bot.db.get_settings(guild.id)
    channel_id = settings.get("log_channel") if settings else None
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel:
        await channel.send(**kwargs)
