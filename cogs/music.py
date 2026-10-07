import discord
from discord.ext import commands
import yt_dlp
import asyncio
from urllib.parse import urlparse
from utils.channels import require_channel
from utils.discord_compat import add_cog

# ====================================================================
# 1. YOUTUBE VE SES MOTORU AYARLARI (İnce Ayarlar)
# ====================================================================
# YouTube'un botları banlamasını engellemek ve yayını optimize etmek için
yt_dlp_ayarlari = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # IPv6 hatalarını önler
}

ffmpeg_ayarlari = {
    'options': '-vn',
    # Şarkının ortasında bağlantı koparsa botun düşmemesi için otomatik yeniden bağlanma
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ytdl = yt_dlp.YoutubeDL(yt_dlp_ayarlari)
ALLOWED_MUSIC_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def valid_music_query(query: str) -> bool:
    query = query.strip()
    if not query or len(query) > 200:
        return False
    parsed = urlparse(query)
    if not parsed.scheme and not parsed.netloc:
        return True
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return host in ALLOWED_MUSIC_HOSTS


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def url_den_yarat(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        # Veriyi indirmeden sadece yayınlamak (stream) için download=False
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            data = data['entries'][0]

        dosya = data['url']
        return cls(discord.FFmpegPCMAudio(dosya, **ffmpeg_ayarlari), data=data)


# ====================================================================
# 2. MÜZİK MODÜLÜ VE KUYRUK SİSTEMİ
# ====================================================================
class Muzik(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Her sunucu için ayrı bir şarkı sırası {sunucu_id: [sarki_url1, sarki_url2]}
        self.kuyruk = {}

    def siradaki_sarkiya_gec(self, ctx, hata=None):
        """Bir şarkı bitince kuyruktaki diğerine otomatik geçen motor"""
        if hata:
            print(f"Müzik oynatılırken hata oluştu: {hata}")

        sunucu_id = ctx.guild.id
        if sunucu_id in self.kuyruk and len(self.kuyruk[sunucu_id]) > 0:
            siradaki_link = self.kuyruk[sunucu_id].pop(0)

            # Asenkron fonksiyonu normal callback içinde çağırmak için ufak bir hile
            coroutine = self.sarki_oynat(ctx, siradaki_link)
            gelecek = asyncio.run_coroutine_threadsafe(coroutine, self.bot.loop)
            try:
                gelecek.result()
            except Exception as e:
                print(f"Sıradaki şarkıya geçerken patladık: {e}")
        else:
            # Kuyruk bittiyse botu ses kanalında boş boş bekletme
            coroutine = ctx.respond("💽 Çalma kuyruğu sona erdi. Yeni bir parça eklenmezse bağlantı sonlandırılacaktır.")
            asyncio.run_coroutine_threadsafe(coroutine, self.bot.loop)

    async def sarki_oynat(self, ctx, arama_sorgusu):
        """Asıl müziği basan fonksiyon"""
        try:
            ses_kanali = ctx.voice_client
            oynatici = await YTDLSource.url_den_yarat(arama_sorgusu, loop=self.bot.loop)

            # Şarkı bittiğinde `siradaki_sarkiya_gec` fonksiyonunu tetikliyoruz
            ses_kanali.play(oynatici, after=lambda e: self.siradaki_sarkiya_gec(ctx, e))

            embed = discord.Embed(title="🔊 Çalma Başlatıldı", description=f"**{oynatici.title}**",
                                  color=discord.Color.brand_green())
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"Parça başlatılamadı. Ayrıntı: {str(e)[:100]}")
            self.siradaki_sarkiya_gec(ctx)  # Hata verirse sıradakine atla

    # ====================================================================
    # 3. KULLANICI KOMUTLARI
    # ====================================================================
    @discord.slash_command(name="play", description="YouTube üzerinden müzik arar ve oynatır.")
    async def play(self, ctx: discord.ApplicationContext, arama_sorgusu: str):
        """Şarkı aratma ve sıraya ekleme komutu"""
        if not await require_channel(ctx, "music_channel"):
            return
        if not valid_music_query(arama_sorgusu):
            return await ctx.respond(
                "Yalnızca YouTube bağlantıları veya arama ifadeleri kullanılabilir."
            )
        if not ctx.author.voice:
            return await ctx.respond("Lütfen önce bir ses kanalına katılınız.")

        ses_kanali = ctx.voice_client

        # Bot kanalda değilse adamın yanına girsin
        if not ses_kanali:
            await ctx.author.voice.channel.connect()
            ses_kanali = ctx.voice_client
        elif ses_kanali.channel != ctx.author.voice.channel:
            return await ctx.respond("Bot farklı bir ses kanalında bulunmaktadır. Lütfen aynı kanala katılınız.")

        sunucu_id = ctx.guild.id
        if sunucu_id not in self.kuyruk:
            self.kuyruk[sunucu_id] = []

        # Eğer bot o an bir şey çalıyorsa, şarkıyı sıraya (kuyruğa) ekle
        if ses_kanali.is_playing() or ses_kanali.is_paused():
            self.kuyruk[sunucu_id].append(arama_sorgusu)
            await ctx.respond(
                f"🎶 Parça kuyruğa eklendi: **{arama_sorgusu}**. Kuyrukta {len(self.kuyruk[sunucu_id])} parça bulunmaktadır.")
        else:
            # Bot boş yatıyorsa direkt müziği patlat
            mesaj = await ctx.respond("⏳ Parça aranıyor ve oynatma hazırlanıyor...")
            await self.sarki_oynat(ctx, arama_sorgusu)
            await mesaj.delete()

    @discord.slash_command(name="skip", description="Oynatılan parçayı atlar.")
    async def skip(self, ctx: discord.ApplicationContext):
        """Mevcut parçayı atlama komutu."""
        if not await require_channel(ctx, "music_channel"):
            return
        ses_kanali = ctx.voice_client
        if not ses_kanali or not ses_kanali.is_playing():
            return await ctx.respond("Şu anda atlanabilecek bir parça bulunmamaktadır.")

        await ctx.respond("⏭️ Mevcut parça atlanıyor; sıradaki parçaya geçiliyor.")
        ses_kanali.stop()  # Stop dediğimiz an otomatik olarak `after` callback'i çalışır ve sıradaki çalar.

    @discord.slash_command(name="queue", description="Müzik kuyruğunu görüntüler.")
    async def queue(self, ctx: discord.ApplicationContext):
        """Sıradaki parçaları gösterir"""
        if not await require_channel(ctx, "music_channel"):
            return
        sunucu_id = ctx.guild.id
        if sunucu_id not in self.kuyruk or not self.kuyruk[sunucu_id]:
            return await ctx.respond("Çalma kuyruğu boş durumdadır.")

        liste = "\n".join([f"{i + 1}. {sarki}" for i, sarki in enumerate(self.kuyruk[sunucu_id][:10])])

        embed = discord.Embed(title="📜 Çalma Listesi", description=liste, color=discord.Color.dark_purple())
        if len(self.kuyruk[sunucu_id]) > 10:
            embed.set_footer(text=f"...ve {len(self.kuyruk[sunucu_id]) - 10} parça daha bulunmaktadır.")

        await ctx.respond(embed=embed)

    @discord.slash_command(name="leave", description="Botu ses kanalından çıkarır ve kuyruğu temizler.")
    async def leave(self, ctx: discord.ApplicationContext):
        """Botu kovar ve kuyruğu temizler"""
        if not await require_channel(ctx, "music_channel"):
            return
        ses_kanali = ctx.voice_client
        if ses_kanali:
            self.kuyruk[ctx.guild.id] = []  # Kuyruğu çöpe at
            await ses_kanali.disconnect()
            await ctx.respond("🔌 Ses bağlantısı sonlandırıldı.")
        else:
            await ctx.respond("Bot şu anda herhangi bir ses kanalında bulunmamaktadır.")


def setup(bot):
    return add_cog(bot, Muzik(bot))