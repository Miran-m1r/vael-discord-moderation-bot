import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import Database
from utils.discord_compat import load_extension


DEFAULT_DISCORD_PROXY = "http://127.0.0.1:8080"


class MekanBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=[],
            intents=intents,
            help_command=None,
            proxy=os.getenv("DISCORD_PROXY", DEFAULT_DISCORD_PROXY),
            # İstersen komutların 1 saat beklemeden anında gelmesi için
            # buraya debug_guilds=[SUNUCU_ID] parametresini ekleyebilirsin.
        )
        self.db = Database()
        self._synced = False

    async def setup_hook(self):
        await self.db.connect()
        for path in sorted(Path(__file__).parent.joinpath("cogs").glob("*.py")):
            if path.name.startswith("_"):
                continue
            result = load_extension(self, f"cogs.{path.stem}")
            if hasattr(result, "__await__"):
                await result

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_ready(self):
        if not self._synced:
            await self.sync_commands()
            self._synced = True
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