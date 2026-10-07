import discord
from discord.ext import commands
import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv
from utils.channels import require_channel
from utils.discord_compat import add_cog
from utils.privacy import external_ai_enabled, redact_sensitive_text

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
            return await message.reply("Lütfen bot için bir soru veya talep belirtiniz.")
        if self.ai_client is None:
            return await message.reply("AI servisi yapılandırılmamış.")
        if not external_ai_enabled():
            return await message.reply(
                "Harici yapay zekâ hizmeti bu sunucuda etkinleştirilmemiştir."
            )

        lock = self.hafiza_kilitleri.setdefault(key, asyncio.Lock())
        async with lock:
            if key not in self.kisi_hafizalari:
                self.kisi_hafizalari[key] = [{
                    "role": "system",
                    "content": (
                        "Siz bu Discord sunucusunun resmi yapay zekâ asistanısınız. "
                        "Her zaman kurumsal, ciddi, açık ve kibar bir Türkçe kullanınız. "
                        "Argo, küfür, küçümseyici ifadeler ve samimi hitaplar kullanmayınız. "
                        "Yanıtlarınızı kısa, anlaşılır ve çözüm odaklı veriniz."
                    )
                }]

            history = self.kisi_hafizalari[key]
            safe_content = redact_sensitive_text(icerik)
            history.append({"role": "user", "content": safe_content})
            history[1:] = history[1:][-self.maksimum_gecmis:]
            request_history = [
                {"role": item["role"], "content": redact_sensitive_text(item["content"])}
                for item in history
            ]

            async with message.channel.typing():
                try:
                    response = await self.ai_client.chat.completions.create(
                        model="gpt-5.4-mini",
                        messages=request_history,
                        temperature=0.8
                    )
                    ai_cevabi = response.choices[0].message.content
                    if not ai_cevabi:
                        raise RuntimeError("LLM boş yanıt döndürdü")
                    history.append({"role": "assistant", "content": ai_cevabi})
                    history[1:] = history[1:][-self.maksimum_gecmis:]
                    await message.reply(ai_cevabi, mention_author=False)
                except Exception as e:
                    if history and history[-1]["role"] == "user" and history[-1]["content"] == safe_content:
                        history.pop()
                    print(f"Chatbot patladı: {e}")
                    await message.reply("Yapay zekâ hizmeti sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyiniz.")


def setup(bot):
    return add_cog(bot, Sohbet(bot))