import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import Database


COMMAND_DESCRIPTIONS = {
    "kurulum": ("Sunucu kanallarını sırayla yapılandırır.", "Yalnızca ADMIN_ROLE_ID rolü"),
    "ticket_kur": ("Seçilen ticket paneli kanalına ticket açma paneli gönderir.", "Admin kanalı + ADMIN_ROLE_ID"),
    "backup_al": ("Sunucu kanal ve rollerinin yedeğini alır.", "Admin kanalı + ADMIN_ROLE_ID"),
    "backup_yukle": ("Kaydedilen sunucu yedeğini geri yükler.", "Admin kanalı + ADMIN_ROLE_ID"),
    "purge": ("Belirtilen sayıda mesajı siler. En fazla 100.", "Admin kanalı + ADMIN_ROLE_ID"),
    "mute": ("Bir üyeyi dakika cinsinden susturur.", "Admin kanalı + ADMIN_ROLE_ID"),
    "zindan": ("Üyenin rollerini alıp zindan rolünü verir.", "Admin kanalı + ADMIN_ROLE_ID"),
    "ban": ("Bir üyeyi sunucudan yasaklar.", "Admin kanalı + ADMIN_ROLE_ID"),
    "kredi": ("Sosyal kredi puanını gösterir.", "Admin kanalı"),
    "play": ("Şarkı arar veya çalma kuyruğuna ekler.", "Müzik kanalı"),
    "skip": ("Çalan şarkıyı geçer.", "Müzik kanalı"),
    "queue": ("Çalma kuyruğunu gösterir.", "Müzik kanalı"),
    "leave": ("Botu ses kanalından çıkarır ve kuyruğu temizler.", "Müzik kanalı"),
    "maaş": ("Bekleyen maaşını alır.", "Oyun kanalı"),
    "bakiye": ("Mevcut bakiyeni gösterir.", "Oyun kanalı"),
    "blackjack": ("Belirtilen bahisle blackjack oynar.", "Oyun kanalı"),
    "slot": ("Belirtilen bahisle slot oynar.", "Oyun kanalı"),
    "satranç": ("Belirtilen üyeye bahisli satranç daveti gönderir.", "Oyun kanalı"),
    "hamle": ("Devam eden satranç oyununda hamle yapar.", "Oyun kanalı"),
    "pes_et": ("Devam eden satranç oyunundan çekilir.", "Oyun kanalı"),
    "seviye": ("Senin veya belirtilen üyenin seviyesini gösterir.", "Sohbet kanalı"),
    "feedback": ("Bot sahibine öneri veya geri bildirim gönderir.", "Sohbet kanalı"),
}


class MekanHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(
            command_attrs={
                "help": "Botun tüm komutlarını ve kullanım kanallarını gösterir.",
                "aliases": ["yardım"],
            }
        )

    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="📚 MekanBot Komut Rehberi",
            description=(
                "Komutları `!` önekiyle kullan. Komutların çalışması için önce `!kurulum` "
                "yapılmalıdır. Ticket açmak herkes için açıktır."
            ),
            color=discord.Color.blurple(),
        )
        grouped = {}
        for command in self.context.bot.commands:
            if command.hidden or command.name in {"help"}:
                continue
            cog_name = command.cog_name or "Genel"
            grouped.setdefault(cog_name, []).append(command)

        for cog_name, commands_in_cog in sorted(grouped.items()):
            lines = []
            for command in sorted(commands_in_cog, key=lambda item: item.name):
                description, restriction = COMMAND_DESCRIPTIONS.get(
                    command.name,
                    (command.help or "Komut açıklaması bulunmuyor.", "Kanal ayarına bağlı"),
                )
                usage = f"`!{command.name}"
                if command.signature:
                    usage += f" {command.signature}"
                usage += "`"
                lines.append(f"{usage} - {description} ({restriction})")
            if lines:
                embed.add_field(name=cog_name, value="\n".join(lines), inline=False)

        embed.set_footer(text="Komut hakkında ayrıntı: !help <komut> | Kısayollar da desteklenir.")
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        description, restriction = COMMAND_DESCRIPTIONS.get(
            command.name,
            (command.help or "Komut açıklaması bulunmuyor.", "Kanal ayarına bağlı"),
        )
        aliases = ", ".join(f"`!{alias}`" for alias in command.aliases) or "Yok"
        embed = discord.Embed(title=f"❓ !{command.name}", description=description, color=discord.Color.blurple())
        embed.add_field(name="Kullanım", value=f"`!{command.name} {command.signature}`".rstrip(), inline=False)
        embed.add_field(name="Erişim", value=restriction, inline=False)
        embed.add_field(name="Kısayollar", value=aliases, inline=False)
        await self.get_destination().send(embed=embed)


class MekanBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=MekanHelpCommand())
        self.db = Database()

    async def setup_hook(self):
        await self.db.connect()
        for path in sorted(Path(__file__).parent.joinpath("cogs").glob("*.py")):
            if path.name.startswith("_"):
                continue
            await self.load_extension(f"cogs.{path.stem}")

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_message(self, message):
        if not message.author.bot:
            await self.process_commands(message)

    async def on_ready(self):
        print(f"Logged in as {self.user} ({self.user.id})")


def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN .env içinde bulunamadı.")
    print(r"""
 __  __ _____ _  __          _   ____        _
|  \/  | ____| |/ /__ _ _ __ | | | __ )  ___ | |_
| |\/| |  _| | ' // _` | '_ \| | |  _ \ / _ \| __|
| |  | | |___| . \ (_| | | | | | | |_) | (_) | |_
|_|  |_|_____|_|\_\__,_|_| |_|_| |____/ \___/ \__|
""")
    bot = MekanBot()
    bot.run(token)


if __name__ == "__main__":
    main()