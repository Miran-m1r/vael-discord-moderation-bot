import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, find_dotenv
from utils.channels import require_channel
from utils.discord_compat import add_cog

load_dotenv(find_dotenv())


class Genel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sahip_id = int(os.getenv("OWNER_ID", 0))

    @discord.slash_command(name="feedback", description="Yöneticiye geri bildirim veya öneri iletir.")
    async def feedback(self, ctx: discord.ApplicationContext, mesaj: str):
        """Kullanıcıların şikayet, istek veya önerilerini direkt senin DM kutuna atar"""
        if not await require_channel(ctx, "chat_channel"):
            return

        # Komutun kullanıldığı mesajı hemen silelim ki ortalıkta kirlilik olmasın
        # Sahibin ID'sini bulup DM nesnesini oluşturalım
        sahip = await self.bot.fetch_user(self.sahip_id)
        if not sahip:
            return await ctx.respond("Sistem yöneticisi tanımlanamadığı için geri bildiriminiz iletilemedi.")

        # Sana gelecek şekilli şüküllü Embed raporu
        embed = discord.Embed(
            title="📥 Yeni Geri Bildirim / İstek!",
            description=mesaj,
            color=discord.Color.blurple()
        )
        embed.set_author(name=f"{ctx.author.name} ({ctx.author.id})", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Sunucu:", value=ctx.guild.name, inline=True)
        embed.add_field(name="Kanal:", value=ctx.channel.name, inline=True)
        embed.set_footer(text="Mekan Bot Raporlama Sistemi")

        try:
            # Doğruca senin DM'ine çakıyoruz
            await sahip.send(embed=embed)

            # Adama kanaldan geçici olarak onay verelim (3 saniye sonra uçuyor)
            gecici_mesaj = await ctx.respond(
                f"✅ {ctx.author.mention}, geri bildiriminiz sistem yöneticisine başarıyla iletildi. Teşekkür ederiz.")
            await gecici_mesaj.delete(delay=3)

        except Exception as e:
            await ctx.respond("Geri bildirim iletilirken bir hata oluştu.")


def setup(bot):
    return add_cog(bot, Genel(bot))