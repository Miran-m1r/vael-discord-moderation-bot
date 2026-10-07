import discord
from discord.ext import commands
import yt_dlp
import asyncio
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
            coroutine = ctx.send("💽 Çalma kuyruğu sona erdi. Yeni bir parça eklenmezse bağlantı sonlandırılacaktır.")
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
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Parça başlatılamadı. Ayrıntı: {str(e)[:100]}")
            self.siradaki_sarkiya_gec(ctx)  # Hata verirse sıradakine atla

    # ====================================================================
    # 3. KULLANICI KOMUTLARI
    # ====================================================================
    @commands.command(aliases=['p', 'çal', 'oynat'])
    async def play(self, ctx, *, arama_sorgusu: str):
        """Şarkı aratma ve sıraya ekleme komutu"""
        if not await require_channel(ctx, "music_channel"):
            return
        if not ctx.author.voice:
            return await ctx.send("Lütfen önce bir ses kanalına katılınız.")

        ses_kanali = ctx.voice_client

        # Bot kanalda değilse adamın yanına girsin
        if not ses_kanali:
            await ctx.author.voice.channel.connect()
            ses_kanali = ctx.voice_client
        elif ses_kanali.channel != ctx.author.voice.channel:
            return await ctx.send("Bot farklı bir ses kanalında bulunmaktadır. Lütfen aynı kanala katılınız.")

        sunucu_id = ctx.guild.id
        if sunucu_id not in self.kuyruk:
            self.kuyruk[sunucu_id] = []

        # Eğer bot o an bir şey çalıyorsa, şarkıyı sıraya (kuyruğa) ekle
        if ses_kanali.is_playing() or ses_kanali.is_paused():
            self.kuyruk[sunucu_id].append(arama_sorgusu)
            await ctx.send(
                f"🎶 Parça kuyruğa eklendi: **{arama_sorgusu}**. Kuyrukta {len(self.kuyruk[sunucu_id])} parça bulunmaktadır.")
        else:
            # Bot boş yatıyorsa direkt müziği patlat
            mesaj = await ctx.send("⏳ Parça aranıyor ve oynatma hazırlanıyor...")
            await self.sarki_oynat(ctx, arama_sorgusu)
            await mesaj.delete()

    @commands.command(aliases=['s', 'geç', 'atla'])
    async def skip(self, ctx):
        """Mevcut parçayı atlama komutu."""
        if not await require_channel(ctx, "music_channel"):
            return
        ses_kanali = ctx.voice_client
        if not ses_kanali or not ses_kanali.is_playing():
            return await ctx.send("Şu anda atlanabilecek bir parça bulunmamaktadır.")

        await ctx.send("⏭️ Mevcut parça atlanıyor; sıradaki parçaya geçiliyor.")
        ses_kanali.stop()  # Stop dediğimiz an otomatik olarak `after` callback'i çalışır ve sıradaki çalar.

    @commands.command(aliases=['q', 'sıra', 'liste'])
    async def queue(self, ctx):
        """Sıradaki parçaları gösterir"""
        if not await require_channel(ctx, "music_channel"):
            return
        sunucu_id = ctx.guild.id
        if sunucu_id not in self.kuyruk or not self.kuyruk[sunucu_id]:
            return await ctx.send("Çalma kuyruğu boş durumdadır.")

        liste = "\n".join([f"{i + 1}. {sarki}" for i, sarki in enumerate(self.kuyruk[sunucu_id][:10])])

        embed = discord.Embed(title="📜 Çalma Listesi", description=liste, color=discord.Color.dark_purple())
        if len(self.kuyruk[sunucu_id]) > 10:
            embed.set_footer(text=f"...ve {len(self.kuyruk[sunucu_id]) - 10} parça daha bulunmaktadır.")

        await ctx.send(embed=embed)

    @commands.command(aliases=['sg', 'ayrıl', 'dur'])
    async def leave(self, ctx):
        """Botu kovar ve kuyruğu temizler"""
        if not await require_channel(ctx, "music_channel"):
            return
        ses_kanali = ctx.voice_client
        if ses_kanali:
            self.kuyruk[ctx.guild.id] = []  # Kuyruğu çöpe at
            await ses_kanali.disconnect()
            await ctx.send("🔌 Ses bağlantısı sonlandırıldı.")
        else:
            await ctx.send("Bot şu anda herhangi bir ses kanalında bulunmamaktadır.")


def setup(bot):
    return add_cog(bot, Muzik(bot))