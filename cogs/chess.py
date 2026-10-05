import discord
from discord.ext import commands
import chess
import urllib.parse
from utils.channels import require_channel


# ====================================================================
# 1. MEYDAN OKUMA BUTONLARI (Kabul Et / Siktiri Çek)
# ====================================================================
class SatrancDavetView(discord.ui.View):
    def __init__(self, cog, ctx, rakip, bahis):
        super().__init__(timeout=60.0)
        self.cog = cog
        self.ctx = ctx
        self.rakip = rakip
        self.bahis = bahis

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.rakip:
            await interaction.response.send_message("Lan sana mı meydan okudu yarram, basma şu butona!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Kabul Et (Paranı Ezerim)", style=discord.ButtonStyle.success)
    async def kabul_et(self, interaction: discord.Interaction, button: discord.ui.Button):
        ekonomi = self.cog.bot.get_cog("Ekonomi")

        # Paraları tekrar kontrol et, belki o arada Slot'ta ezdiler amk
        if (await ekonomi.bot.db.get_economy(self.ctx.author.id))["bakiye"] < self.bahis or \
                (await ekonomi.bot.db.get_economy(self.rakip.id))["bakiye"] < self.bahis:
            await interaction.response.edit_message(content="İkinizden birinin parası suyunu çekmiş amk, oyun iptal!",
                                                    view=None)
            return

        # Bahisleri kasadan düş (Kaçana iade yok)
        if not await ekonomi.bot.db.try_withdraw(self.ctx.author.id, self.bahis) or \
                not await ekonomi.bot.db.try_withdraw(self.rakip.id, self.bahis):
            await interaction.response.edit_message(content="Para değiştiği için oyun iptal edildi.", view=None)
            return

        # Oyunu kuruyoruz
        kanal_id = interaction.channel.id
        self.cog.aktif_oyunlar[kanal_id] = {
            "tahta": chess.Board(),
            "beyaz": self.ctx.author,
            "siyah": self.rakip,
            "bahis": self.bahis,
            "sira": self.ctx.author  # İlk beyaz başlar
        }

        # Butonları yok et ve tahtayı çiz
        await interaction.response.edit_message(
            content=f"⚔️ **MASA KURULDU!**\n{self.ctx.author.mention} (Beyaz) 🆚 {self.rakip.mention} (Siyah)\nOrtadaki Para: **{self.bahis * 2}** kağıt.\n\nİlk hamle Beyazın! Komut: `!hamle e4` veya `!hamle Nf3`",
            view=None)
        await self.cog.tahtayi_ciz(interaction.channel)

    @discord.ui.button(label="Siktir Et (Tırstım)", style=discord.ButtonStyle.danger)
    async def reddet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=f"{self.rakip.mention} tırstı ve masadan kaçtı. Para cebinizde kaldı.", view=None)
        self.stop()


# ====================================================================
# 2. ANA SATRANÇ MODÜLÜ
# ====================================================================
class Satranc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Hangi kanalda hangi oyun dönüyor? {kanal_id: {oyun_verileri}}
        # Mantık: Aynı kanalda aynı anda sadece 1 maç oynanabilir. Çorba olmasın.
        self.aktif_oyunlar = {}

    async def tahtayi_ciz(self, kanal):
        """Chess.com'un dinamik API'sini kullanarak tahtayı jilet gibi renderlar"""
        oyun = self.aktif_oyunlar.get(kanal.id)
        if not oyun: return

        tahta = oyun["tahta"]
        # FEN kodunu internete uyumlu hale getiriyoruz (boşlukları %20 yapar falan)
        fen_kodu = urllib.parse.quote(tahta.fen())

        # Jilet gibi Chess.com API'si (Siyahın sırasıysa tahtayı çevirme parametresi de eklenebilir ama standart iyidir)
        resim_url = f"https://www.chess.com/dynboard?fen={fen_kodu}&board=green&piece=neo&size=3"

        embed = discord.Embed(color=discord.Color.dark_theme())
        embed.set_image(url=resim_url)
        embed.set_footer(text=f"Sıra: {oyun['sira'].name} | Hamleni !hamle e4 şeklinde yaz")

        await kanal.send(embed=embed)

    async def oyun_bitir(self, kanal, kazanan, sebep):
        oyun = self.aktif_oyunlar.get(kanal.id)
        ekonomi = self.bot.get_cog("Ekonomi")

        if kazanan == "berabere":
            await ekonomi.bot.db.add_balance(oyun["beyaz"].id, oyun["bahis"])
            await ekonomi.bot.db.add_balance(oyun["siyah"].id, oyun["bahis"])
            await kanal.send(f"🤝 **MAÇ BERABERE BİTTİ!** ({sebep})\nParalar iade edildi amk, ikiniz de aynısınız.")
        else:
            toplam_para = oyun["bahis"] * 2
            await ekonomi.bot.db.add_balance(kazanan.id, toplam_para)
            await kanal.send(
                f"🏆 **ŞAH MAT ANASINI SATAYIM!**\n**{kazanan.mention}** rakibini maymun etti ve masadaki **{toplam_para}** kağıdı cukkaladı! ({sebep})")

        # Oyunu bellekten sil
        del self.aktif_oyunlar[kanal.id]

    @commands.command()
    async def satranç(self, ctx, rakip: discord.Member, bahis: int):
        """Meydan okuma komutu"""
        if not await require_channel(ctx, "game_channel"):
            return
        if ctx.channel.id in self.aktif_oyunlar:
            return await ctx.send("Lan bu kanalda zaten dönen bir maç var, bitmesini bekle ya da başka odaya git!")

        if rakip == ctx.author or rakip.bot:
            return await ctx.send("Kendi kendine veya botla parasına mı oynayacaksın yıkık piç?")

        if bahis <= 0:
            return await ctx.send("Beleşe oyun yok, ortaya para koy!")

        ekonomi = self.bot.get_cog("Ekonomi")
        if not ekonomi:
            return await ctx.send("Ulan Ekonomi modülü çökmüş, para yok oyun da yok!")

        # Para kontrolleri
        if (await ekonomi.bot.db.get_economy(ctx.author.id))["bakiye"] < bahis:
            return await ctx.send(f"Fakir piç, cebinde {bahis} kağıt yok, kime şekil yapıyorsun!")
        if (await ekonomi.bot.db.get_economy(rakip.id))["bakiye"] < bahis:
            return await ctx.send(f"Meydan okuduğun adam fakir amk, cebinde {bahis} kağıdı yok!")

        # Davet mesajı
        embed = discord.Embed(title="♟️ BİRİ SANA RACON KESTİ!",
                              description=f"{ctx.author.mention}, {rakip.mention} kişisine **{bahis}** kağıdına satranç meydan okuması yolladı!",
                              color=discord.Color.red())
        view = SatrancDavetView(self, ctx, rakip, bahis)
        await ctx.send(content=rakip.mention, embed=embed, view=view)

    @commands.command()
    async def hamle(self, ctx, *, hamle_adi: str):
        """Oyunu oynatan ana komut"""
        kanal_id = ctx.channel.id
        oyun = self.aktif_oyunlar.get(kanal_id)

        if not oyun:
            return await ctx.send("Bu kanalda oynanan bir maç yok amk, hayaletlerle mi oynuyorsun?")

        if ctx.author != oyun["sira"]:
            return await ctx.send("Lan bekle, sıra sende değil!")

        tahta = oyun["tahta"]

        # Adamın hamlesini deniyoruz
        try:
            # push_san, "e4", "Nf3", "O-O" gibi normal insan dilini anlar
            tahta.push_san(hamle_adi)
        except ValueError:
            return await ctx.send(
                f"Lan yarram '{hamle_adi}' diye hamle mi var? Ya yanlış yazdın ya da kural dışı (Şah altındasın belki). Düzgün oyna!")

        # Sırayı diğerine geçir
        oyun["sira"] = oyun["siyah"] if ctx.author == oyun["beyaz"] else oyun["beyaz"]

        # Mat veya Beraberlik kontrolü
        if tahta.is_checkmate():
            await self.tahtayi_ciz(ctx.channel)
            await self.oyun_bitir(ctx.channel, kazanan=ctx.author, sebep="Mat ettin.")
            return

        if tahta.is_stalemate():
            await self.tahtayi_ciz(ctx.channel)
            await self.oyun_bitir(ctx.channel, kazanan="berabere", sebep="Pat (Hamle kalmadı)")
            return

        if tahta.is_insufficient_material():
            await self.tahtayi_ciz(ctx.channel)
            await self.oyun_bitir(ctx.channel, kazanan="berabere", sebep="İkinizin de taşı bitti amk.")
            return

        # Oyun bitmediyse yeni tahtayı çiz
        await self.tahtayi_ciz(ctx.channel)

    @commands.command()
    async def pes_et(self, ctx):
        """Götü yemeyenler için kaçış butonu"""
        kanal_id = ctx.channel.id
        oyun = self.aktif_oyunlar.get(kanal_id)

        if not oyun: return

        if ctx.author not in [oyun["beyaz"], oyun["siyah"]]:
            return await ctx.send("Lan sen oynamıyorsun ki neye pes ediyorsun yancı!")

        kazanan = oyun["siyah"] if ctx.author == oyun["beyaz"] else oyun["beyaz"]
        await self.oyun_bitir(ctx.channel, kazanan=kazanan, sebep="Rakip ağlayarak masadan kaçtı.")


async def setup(bot):
    await bot.add_cog(Satranc(bot))