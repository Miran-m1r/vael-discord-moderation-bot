import asyncio

import discord
from discord.ext import commands
from utils.channels import admin_role_only


class Kurulum(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    @commands.guild_only()
    @admin_role_only()
    async def kurulum(self, ctx):
        questions = [
            ("log_channel", "Log Kanalı"), ("game_channel", "Kumar / Oyun Kanalı"),
            ("music_channel", "Müzik Kanalı"), ("chat_channel", "Bot Sohbet Kanalı"),
            ("admin_channel", "Bot Komut (Sadece Adminler İçin) Kanalı"),
            ("ticket_channel", "Ticket Paneli Kanalı"),
        ]
        ids = {}
        await ctx.send("Kurulum başladı. Kanal ID'si veya kanal etiketi gönderin (60 saniye).")
        for key, label in questions:
            await ctx.send(f"**{label}:**")

            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel

            try:
                answer = await self.bot.wait_for("message", timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.send("Kurulum zaman aşımına uğradı; değişiklik kaydedilmedi.")
                return
            channel = answer.channel_mentions[0] if answer.channel_mentions else None
            if channel is None:
                try:
                    channel = ctx.guild.get_channel(int(answer.content.strip()))
                except ValueError:
                    channel = None
            if not isinstance(channel, discord.TextChannel):
                await ctx.send("Bu ayar için metin kanalı ID'si/etiketi gerekli; kurulum iptal edildi.")
                return
            ids[key] = channel.id
        await self.bot.db.save_settings(ctx.guild.id, **ids)
        await ctx.send("✅ Kurulum tamamlandı; kanal ayarları veritabanına kaydedildi.")


async def setup(bot):
    await bot.add_cog(Kurulum(bot))
