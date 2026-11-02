import asyncio

import discord
from discord.ext import commands
from utils.discord_compat import add_cog


class Kurulum(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="kurulum", description="Sunucu kanal ve rol ayarlarını etkileşimli olarak yapılandırır.")
    @commands.has_permissions(administrator=True)
    async def kurulum(self, ctx: discord.ApplicationContext):
        channel_questions = [
            ("log_channel", "Log Kanalı"),
            ("game_channel", "Kumar / Oyun Kanalı"),
            ("music_channel", "Müzik Kanalı"),
            ("chat_channel", "Bot Sohbet Kanalı"),
            ("admin_channel", "Bot Komut (Sadece Adminler İçin) Kanalı"),
            ("ticket_channel", "Ticket Paneli Kanalı"),
        ]
        role_questions = [
            ("mod_role", "Moderatör Rolü"),
            ("admin_role", "Yönetici (Admin) Rolü"),
            ("zindan_role", "Zindan (Kısıtlama) Rolü"),
        ]
        ids = {}
        await ctx.respond("Kurulum başlatıldı. Lütfen her soru için istenen kanal veya rol ID'sini / etiketini 60 saniye içinde gönderiniz.")

        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel

        for key, label in channel_questions:
            await ctx.respond(f"**{label} (Kanal ID veya #kanal):**")
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

        for key, label in role_questions:
            await ctx.respond(f"**{label} (Rol ID veya @rol):**")
            try:
                answer = await self.bot.wait_for("message", timeout=60, check=check)
            except asyncio.TimeoutError:
                await ctx.respond("Kurulum zaman aşımına uğradı; herhangi bir değişiklik kaydedilmedi.")
                return
            role = answer.role_mentions[0] if answer.role_mentions else None
            if role is None:
                try:
                    role = ctx.guild.get_role(int(answer.content.strip()))
                except ValueError:
                    role = None
            if not isinstance(role, discord.Role):
                await ctx.respond("Bu ayar için geçerli bir rol ID'si/etiketi gerekli; kurulum iptal edildi.")
                return
            ids[key] = role.id

        await self.bot.db.save_settings(ctx.guild.id, **ids)
        await ctx.respond("✅ Kurulum tamamlandı. Kanal ve rol ayarları veritabanına kaydedildi.")


def setup(bot):
    return add_cog(bot, Kurulum(bot))
