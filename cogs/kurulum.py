import asyncio

import discord
from discord.ext import commands
from utils.discord_compat import add_cog


class Kurulum(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="kurulum", description="Sunucu kanal ayarlarını etkileşimli olarak yapılandırır.")
    @commands.has_permissions(administrator=True)
    async def kurulum(self, ctx: discord.ApplicationContext):
        questions = [
            ("log_channel", "Log Kanalı"), ("game_channel", "Kumar / Oyun Kanalı"),
            ("music_channel", "Müzik Kanalı"), ("chat_channel", "Bot Sohbet Kanalı"),
            ("admin_channel", "Bot Komut (Sadece Adminler İçin) Kanalı"),
            ("ticket_channel", "Ticket Paneli Kanalı"),
        ]
        ids = {}
        await ctx.respond("Kurulum başlatıldı. Lütfen her soru için kanal ID'sini veya kanal etiketini 60 saniye içinde gönderiniz.")
        for key, label in questions:
            await ctx.respond(f"**{label}:**")

            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel

            try:
                answer = await self.bot.wait_for("message", timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.respond("Kurulum zaman aşımına uğradı; herhangi bir değişiklik kaydedilmedi.")
                return
            channel = answer.channel_mentions[0] if answer.channel_mentions else None
            if channel is None:
                try:
                    channel = ctx.guild.get_channel(int(answer.content.strip()))
                except ValueError:
                    channel = None
            if not isinstance(channel, discord.TextChannel):
                await ctx.respond("Bu ayar için metin kanalı ID'si/etiketi gerekli; kurulum iptal edildi.")
                return
            ids[key] = channel.id
        await self.bot.db.save_settings(ctx.guild.id, **ids)
        await ctx.respond("✅ Kurulum tamamlandı. Kanal ayarları veritabanına kaydedildi.")


def setup(bot):
    return add_cog(bot, Kurulum(bot))
