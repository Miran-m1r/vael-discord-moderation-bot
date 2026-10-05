import discord
from discord.ext import commands
import time
import random


class Seviye(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # RAM'deki geçici veri depomuz {kullanici_id: {"xp": 0, "level": 1, "son_mesaj": 0}}
        self.kullanicilar = {}

        # ---------------- RÜTBE (ROL) ÖDÜLLERİ ----------------
        # Hangi levelda hangi rol verilecek? (Sol taraf level, sağ taraf kendi sunucundaki Rol ID'si)
        self.odul_rolleri = {
            5: 111111111111111111,  # Örnek: Aktif Üye Rolü
            10: 222222222222222222,  # Örnek: VIP Rolü
            20: 333333333333333333  # Örnek: Mekanın Sahibi Rolü
        }

    def xp_hesapla(self, level):
        """Sonraki levele geçmek için gereken XP formülü (Örn: Lvl 1=100, Lvl 2=400, Lvl 3=900)"""
        return 100 * (level ** 2)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Botlara ve ünlemli komutlara (!yardım, !bj) XP vermiyoruz
        if message.author.bot or message.content.startswith('!'):
            return

        uid = message.author.id
        suan = time.time()

        # Adam sistemde yoksa sıfırdan dosyası açılır
        if uid not in self.kullanicilar:
            self.kullanicilar[uid] = {"xp": 0, "level": 1, "son_mesaj": 0}

        data = self.kullanicilar[uid]

        # ANTI-SPAM: 60 saniyede bir XP alınabilir (Millet spam yapıp level kasamasın diye)
        if suan - data["son_mesaj"] < 60:
            return

        # 15 ile 25 arası rastgele XP ateşle
        kazanilan_xp = random.randint(15, 25)
        data["xp"] += kazanilan_xp
        data["son_mesaj"] = suan

        # SEVİYE ATLAMA KONTROLÜ
        gereken_xp = self.xp_hesapla(data["level"])
        if data["xp"] >= gereken_xp:
            data["level"] += 1
            yeni_level = data["level"]

            await message.channel.send(
                f"🎉 Oha işsize bak amk! {message.author.mention} 7/24 chatte çene çala çala **Seviye {yeni_level}** oldu!")

            # Adam o levela gelince hak ettiği bir rol var mı bakıyoruz
            if yeni_level in self.odul_rolleri:
                rol_id = self.odul_rolleri[yeni_level]
                rol = message.guild.get_role(rol_id)
                if rol:
                    try:
                        await message.author.add_roles(rol)
                        await message.channel.send(
                            f"🎖️ {message.author.mention}, çenene sağlık. **{rol.name}** rütbesi sana hediye edildi, şeklini yap!")
                    except Exception as e:
                        print(f"Rol verme hatası: {e} (Botun rolü adamın rolünden altta kalmış olabilir amk)")

    @commands.command(aliases=['rank', 'rütbe','level', 'lvl'])
    async def seviye(self, ctx, uye: discord.Member = None):
        """Adamın kaçıncı levelda olduğunu ve XP çubuğunu gösteren fiyakalı komut"""
        uye = uye or ctx.author
        uid = uye.id

        if uid not in self.kullanicilar:
            return await ctx.send(f"{uye.mention} daha siftahı yok, 0 XP, full yıkık. Git az muhabbet et.")

        data = self.kullanicilar[uid]
        mevcut_xp = data["xp"]
        mevcut_lvl = data["level"]
        sonraki_hedef = self.xp_hesapla(mevcut_lvl)

        # Şekilli Progress Bar (İlerleme Çubuğu) hesaplaması
        yuzde = int((mevcut_xp / sonraki_hedef) * 10)
        cubuk = ("🟩" * yuzde) + ("⬛" * (10 - yuzde))

        embed = discord.Embed(title=f"📊 {uye.name} - Sicil Dosyası", color=discord.Color.purple())
        embed.set_thumbnail(url=uye.display_avatar.url)
        embed.add_field(name="Seviye (Level)", value=f"**{mevcut_lvl}**", inline=True)
        embed.add_field(name="Mevcut XP", value=f"**{mevcut_xp} / {sonraki_hedef}**", inline=True)
        embed.add_field(name="İlerleme", value=f"`{cubuk}`", inline=False)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Seviye(bot))