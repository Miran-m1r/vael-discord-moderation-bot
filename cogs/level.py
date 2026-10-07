import random
import time

import discord
from discord.ext import commands

from utils.channels import require_channel
from utils.discord_compat import add_cog


class Seviye(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.odul_rolleri = {}

    @staticmethod
    def xp_hesapla(level):
        return 100 * level**2

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith("!") or not message.guild:
            return
        before = await self.bot.db.get_level(message.author.id)
        data = await self.bot.db.add_xp(message.author.id, random.randint(15, 25), time.time())
        if int(data["level"]) > int(before["level"]):
            await message.channel.send(
                f"🎉 {message.author.mention} **Seviye {data['level']}** seviyesine ulaştınız!")
            role_id = self.odul_rolleri.get(int(data["level"]))
            role = message.guild.get_role(role_id) if role_id else None
            if role:
                await message.author.add_roles(role)

    @discord.slash_command(name="seviye", description="Kullanıcının seviye ve XP durumunu görüntüler.")
    async def seviye(self, ctx: discord.ApplicationContext, uye: discord.Member = None):
        if not await require_channel(ctx, "chat_channel"):
            return
        uye = uye or ctx.author
        data = await self.bot.db.get_level(uye.id)
        xp, level = int(data["xp"]), int(data["level"])
        target = self.xp_hesapla(level)
        filled = min(10, int(xp / target * 10))
        embed = discord.Embed(title=f"📊 {uye.name}", color=discord.Color.purple())
        embed.add_field(name="Seviye", value=f"**{level}**")
        embed.add_field(name="XP", value=f"**{xp} / {target}**")
        embed.add_field(name="İlerleme", value=f"`{'🟩' * filled}{'⬛' * (10 - filled)}`", inline=False)
        await ctx.send(embed=embed)


def setup(bot):
    return add_cog(bot, Seviye(bot))
