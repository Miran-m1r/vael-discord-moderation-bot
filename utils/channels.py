from __future__ import annotations

import discord
from discord.ext import commands


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
