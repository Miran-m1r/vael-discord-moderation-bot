import discord
from discord.ext import commands

from utils.channels import require_channel
from utils.discord_compat import add_cog


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="help", description="Kullanılabilir bot komutlarını listeler.")
    async def help_command(self, ctx: discord.ApplicationContext):
        if not await require_channel(ctx, "chat_channel"):
            return
        embed = discord.Embed(
            title="MekanBot Yardım",
            description="Kullanılabilir komutlar ve ilgili kullanım alanları aşağıda listelenmiştir.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Ekonomi ve Kasa",
            value=(
                "`/cases` — Kasa mağazasını listeler.\n"
                "`/buycase <kasa>` — Kasa satın alır ve açar.\n"
                "`/inventory` — Envanteri görüntüler.\n"
                "`/sell <item_id>` — Eşyayı satar.\n"
                "`/trade <kullanıcı> <item_id>` — Takas teklifi gönderir.\n"
                "`!maaş`, `!bakiye`, `!blackjack`, `!slot`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Satranç",
            value="`/chess [rakip] [bahis]` — Kullanıcıya veya bota karşı oyun başlatır.\n`/pes` — Devam eden oyundan ayrılır.",
            inline=False,
        )
        embed.add_field(
            name="Müzik ve Destek",
            value="`!play`, `!skip`, `!queue`, `!leave` — Müzik işlemleri.\n`!ticket_kur` — Destek panelini oluşturur.",
            inline=False,
        )
        await ctx.send(embed=embed)


def setup(bot):
    return add_cog(bot, Help(bot))
