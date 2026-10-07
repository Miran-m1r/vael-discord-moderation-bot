import discord
from discord.ext import commands

from utils.channels import require_channel
from utils.discord_compat import add_cog


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="help", description="Kullanılabilir bot komutlarını listeler.")
    async def help_command(self, ctx: discord.ApplicationContext):
        if not await require_channel(ctx, "chat_channel"):
            return
        commands_by_cog = {}
        registered = list(getattr(self.bot, "application_commands", []) or [])
        registered.extend(getattr(self.bot, "pending_application_commands", []) or [])
        unique = {id(command): command for command in registered}
        for command in sorted(unique.values(), key=lambda item: item.name):
            if not getattr(command, "name", None) or command.name == "help":
                continue
            cog_name = getattr(command, "cog_name", None) or getattr(
                getattr(command, "cog", None), "__class__", type("", (), {})
            ).__name__
            category = cog_name or "Genel"
            commands_by_cog.setdefault(category, []).append(
                f"`/{command.name}` - {getattr(command, 'description', None) or 'Komut açıklaması bulunmuyor.'}"
            )
        embed = discord.Embed(
            title="MekanBot Yardım",
            description="Botta etkin olan slash komutları aşağıda kategorilere ayrılmıştır.",
            color=discord.Color.blurple(),
        )
        for category, entries in commands_by_cog.items():
            embed.add_field(name=category, value="\n".join(entries)[:1024], inline=False)
        if not commands_by_cog:
            embed.description = "Henüz kayıtlı slash komutu bulunmamaktadır."
        await ctx.send(embed=embed)


def setup(bot):
    return add_cog(bot, Help(bot))
