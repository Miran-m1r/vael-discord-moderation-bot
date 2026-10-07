import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import Database

DEFAULT_DISCORD_PROXY = "http://127.0.0.1:8080"


class MekanBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            proxy=os.getenv("DISCORD_PROXY", DEFAULT_DISCORD_PROXY),
            # İstersen komutların 1 saat beklemeden anında gelmesi için
            # buraya debug_guilds=[SUNUCU_ID] parametresini ekleyebilirsin.
        )
        self.db = Database()
        self._synced = False

        # Pycord setup_hook kullanmadığı için cog'ları başlatılırken direkt yüklüyoruz
        for path in sorted(Path(__file__).parent.joinpath("cogs").glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                self.load_extension(f"cogs.{path.stem}")
            except Exception as e:
                print(f"HATA - Cog yüklenemedi: {path.stem} -> {e}")

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_message(self, message):
        if not message.author.bot:
            await self.process_commands(message)

    async def on_ready(self):
        # Veritabanı asenkron olduğu için bot bağlanınca aktif ediyoruz
        await self.db.connect()
        if not self._synced:
            await self.sync_commands()
            self._synced = True

        print(f"Logged in as {self.user} ({self.user.id})")
        print(">>> YÜKLENEN COG'LAR:", list(self.cogs.keys()))
        print(">>> AKTİF SLASH KOMUTLAR:", [c.name for c in getattr(self, 'application_commands', [])])


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