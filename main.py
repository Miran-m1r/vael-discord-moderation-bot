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
            intents=intents,
            help_command=None,
            proxy=os.getenv("DISCORD_PROXY", DEFAULT_DISCORD_PROXY),
        )
        self.db = Database()
        self._synced = False

        # Copilot'un bozduğu setup_hook yerine Pycord standart yüklemesi
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

    async def on_ready(self):
        await self.db.connect()
        if not self._synced:
            await self.sync_commands()
            self._synced = True

        print(f"Logged in as {self.user} ({self.user.id})")
        print(">>> YÜKLENEN COG'LAR:", list(self.cogs.keys()))
        print(">>> AKTİF SLASH KOMUTLAR:", [c.name for c in getattr(self, 'application_commands', [])])

    async def on_guild_join(self, guild: discord.Guild):
        try:
            owner = guild.owner
            if owner is None and guild.owner_id:
                try:
                    owner = await guild.fetch_member(guild.owner_id)
                except Exception:
                    pass

            bot_member = guild.me or (await guild.fetch_member(self.user.id) if self.user else None)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
            }
            if bot_member:
                overwrites[bot_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            channel = await guild.create_text_channel("mekan-kurulum", overwrites=overwrites)

            embed = discord.Embed(
                title="⚙️ MekanBot Kurulum Paneli",
                description=(
                    f"Hoş geldiniz {owner.mention if owner else 'Sunucu Sahibi'}!\n\n"
                    "Botun kanallarını (log, oyun, müzik, sohbet vb.) ve yetkili rollerini "
                    "(mod, admin, zindan) yapılandırmak için lütfen bu kanalda **/kurulum** "
                    "komutunu çalıştırınız.\n\n"
                    "Bu kanal yalnızca sunucu sahibine ve bota özeldir. Kurulum tamamlandıktan sonra kanalı silebilirsiniz."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="MekanBot | Otomatik Kurulum Asistanı")
            await channel.send(embed=embed)
        except Exception as e:
            print(f"on_guild_join sırasında hata oluştu ({guild.name}): {e}")


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
