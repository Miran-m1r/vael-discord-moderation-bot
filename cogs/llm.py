import discord
from discord.ext import commands
import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv
from utils.channels import require_channel

load_dotenv()


class Sohbet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("OPENAI_API_KEY")
        self.ai_client = AsyncOpenAI(api_key=api_key) if api_key else None

        # Guild ve kullanıcı bazlı hafıza: {(guild_id, user_id): [...]}
        self.kisi_hafizalari = {}
        self.hafiza_kilitleri = {}
        # Her kullanıcı için tutulacak maksimum mesaj çifti (Soru + Cevap)
        # 5 mesaj dendiği için son 5 girdiyi tutacağız
        self.maksimum_gecmis = 10  # 5 user + 5 assistant mesajı yapar

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        settings = await self.bot.db.get_settings(message.guild.id) if message.guild else None
        if not settings or settings.get("chat_channel") != message.channel.id:
            return

        bota_yanit_mi = message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user
        bot_etiketlendi_mi = self.bot.user in message.mentions

        if not (bota_yanit_mi or bot_etiketlendi_mi):
            return

        key = (message.guild.id, message.author.id)
        icerik = message.clean_content.replace(f"@{self.bot.user.name}", "").strip()

        if not icerik:
            return await message.reply("Eee? Ne diyorsun amk boş boş etiketleyip durma.")
        if self.ai_client is None:
            return await message.reply("AI servisi yapılandırılmamış.")

        lock = self.hafiza_kilitleri.setdefault(key, asyncio.Lock())
        async with lock:
            if key not in self.kisi_hafizalari:
                self.kisi_hafizalari[key] = [{
                    "role": "system",
                    "content": (
                        "Sen bu Discord sunucusunun belkemiği, mekanın yapay zeka assistanısın. "
                        "Sokak ağzıyla, samimi, gerektiğinde sert ve argolu konuşuyorsun. "
                        "Karşındaki insanlara 'kanka', 'aslanım', 'piç', 'amk', 'lan' falan diyebilirsin. "
                        "Kısa, net, zekice ve iğneleyici cevaplar ver. Kimseye boyun eğme, mekanın sahibi sensin."
                    )
                }]

            history = self.kisi_hafizalari[key]
            history.append({"role": "user", "content": icerik})
            history[1:] = history[1:][-self.maksimum_gecmis:]

            async with message.channel.typing():
                try:
                    response = await self.ai_client.chat.completions.create(
                        model="gpt-5.4-mini",
                        messages=history,
                        temperature=0.8
                    )
                    ai_cevabi = response.choices[0].message.content
                    if not ai_cevabi:
                        raise RuntimeError("LLM boş yanıt döndürdü")
                    history.append({"role": "assistant", "content": ai_cevabi})
                    history[1:] = history[1:][-self.maksimum_gecmis:]
                    await message.reply(ai_cevabi, mention_author=False)
                except Exception as e:
                    if history and history[-1]["role"] == "user" and history[-1]["content"] == icerik:
                        history.pop()
                    print(f"Chatbot patladı: {e}")
                    await message.reply("Kafam yandı amk, API'de bir bokluk var az bekle sonra tekrar yaz.")


async def setup(bot):
    await bot.add_cog(Sohbet(bot))