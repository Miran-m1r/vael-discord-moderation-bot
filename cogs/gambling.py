import discord
from discord.ext import commands
import random
import asyncio


# ====================================================================
# 1. KART DEĞERİ HESAPLAMA MANTIĞI (Amelelik kısmı)
# ====================================================================
def el_hesapla(el):
    deger = 0
    as_sayisi = 0

    for kart in el:
        if kart in ['J', 'Q', 'K']:
            deger += 10
        elif kart == 'A':
            as_sayisi += 1
            deger += 11  # Şimdilik 11 ekle, patlarsa 1'e düşüreceğiz
        else:
            deger += int(kart)

    # Eğer 21'i geçtiyse ve elinde As varsa, As'ları 1 say (10 çıkar)
    while deger > 21 and as_sayisi > 0:
        deger -= 10
        as_sayisi -= 1

    return deger


# ====================================================================
# 2. BLACKJACK BUTONLARI VE OYUN MANTIĞI (View)
# ====================================================================
class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bahis):
        super().__init__(timeout=60.0)  # 1 dakika oynamazsa butonlar ölür
        self.cog = cog
        self.ctx = ctx
        self.bahis = bahis
        self.deste = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] * 4
        random.shuffle(self.deste)

        # Kartları Dağıt (İlk iki kart)
        self.oyuncu_eli = [self.deste.pop(), self.deste.pop()]
        self.kasa_eli = [self.deste.pop(), self.deste.pop()]

    # Yabancı piçler gelip başkasının oyunundaki butona basamasın diye kalkan
    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Lan yürü git, başkasının masasına salça olma!", ephemeral=True)
            return False
        return True

    def embed_guncelle(self, durum="devam"):
        oyuncu_puan = el_hesapla(self.oyuncu_eli)
        kasa_puan = el_hesapla(self.kasa_eli)

        embed = discord.Embed(title="🎰 Mekan Blackjack", color=discord.Color.gold())
        embed.add_field(name=f"{self.ctx.author.name} (Sen) - [{oyuncu_puan}]", value=" | ".join(self.oyuncu_eli),
                        inline=False)

        # Oyun devam ediyorsa kasanın ikinci kartını gizle (Racon böyledir)
        if durum == "devam":
            embed.add_field(name="Kasa - [?]", value=f"{self.kasa_eli[0]} | ❓", inline=False)
        else:
            embed.add_field(name=f"Kasa - [{kasa_puan}]", value=" | ".join(self.kasa_eli), inline=False)

        return embed

    # --- BUTON 1: KART ÇEK (HIT) ---
    @discord.ui.button(label="Kart Çek", style=discord.ButtonStyle.primary, custom_id="bj_cek")
    async def kart_cek(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.oyuncu_eli.append(self.deste.pop())
        oyuncu_puan = el_hesapla(self.oyuncu_eli)

        # Adam patladı mı (Bust)?
        if oyuncu_puan > 21:
            for child in self.children: child.disabled = True  # Butonları kitle
            embed = self.embed_guncelle(durum="bitti")
            embed.description = f"💥 **PATLADIN AMK!** 21'i geçtin, {self.bahis} kağıt kasaya gitti."
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        else:
            # Oyuna devam
            await interaction.response.edit_message(embed=self.embed_guncelle(durum="devam"), view=self)

    # --- BUTON 2: BEKLE (STAND) - KASA OYNAR ---
    @discord.ui.button(label="Bekle", style=discord.ButtonStyle.danger, custom_id="bj_bekle")
    async def bekle(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True  # Butonları kitle, sıra kasada

        # Kasanın raconu: 17'yi bulana kadar kart çeker
        while el_hesapla(self.kasa_eli) < 17:
            self.kasa_eli.append(self.deste.pop())

        oyuncu_puan = el_hesapla(self.oyuncu_eli)
        kasa_puan = el_hesapla(self.kasa_eli)

        embed = self.embed_guncelle(durum="bitti")

        # KİM KAZANDI HESABI
        uid = self.ctx.author.id
        if kasa_puan > 21:
            embed.description = f"🎉 **KASA PATLADI!** Zengin oldun piç, {self.bahis} kağıt kazandın!"
            self.cog.bakiyeler[uid] += self.bahis * 2  # Parasını ve kazancını geri ver
        elif kasa_puan > oyuncu_puan:
            embed.description = f"💀 **KASA ALDI!** Kasa her zaman kazanır koçum, {self.bahis} kağıt uçtu."
            # Zaten başta parayı düşmüştük, bir şey yapmaya gerek yok
        elif oyuncu_puan > kasa_puan:
            embed.description = f"💵 **YENDİN!** Mekanın parasını cukkaladın, {self.bahis} kağıt kazandın!"
            self.cog.bakiyeler[uid] += self.bahis * 2
        else:
            embed.description = f"🤝 **BERABERE!** İkiniz de aynısınız amk, paran iade edildi."
            self.cog.bakiyeler[uid] += self.bahis  # Sadece yatırdığı parayı iade et

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# ====================================================================
# 3. ANA MODÜL (Ekonomi Bağlantıları)
# ====================================================================
class Ekonomi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # RAM'deki sahte veritabanımız
        self.bakiyeler = {}  # {kullanici_id: para_miktari}
        self.son_maas = {}  # {kullanici_id: son_cekim_saniyesi}

    @commands.command()
    async def maaş(self, ctx):
        """Adamın maaşını hesaplayıp ateşleyen veya fırça kayan komut"""
        import time  # Zaman hesaplaması için

        uid = ctx.author.id
        suan = time.time()
        bekleme_suresi = 6 * 3600  # 6 saat (Saniye cinsinden)

        # Adamın hiç hesabı yoksa sıfırdan açalım
        if uid not in self.bakiyeler:
            self.bakiyeler[uid] = 0

        # 1. DURUM: Adam ilk defa komutu giriyorsa (500 kağıt ateşle)
        if uid not in self.son_maas:
            self.bakiyeler[uid] += 500
            self.son_maas[uid] = suan
            await ctx.send(
                f"🎉 Ooo yeni müşteri! İlk defa maaş alıyorsun piç, ballısın. Al sana **500 kağıt** başlangıç parası. Bir sonraki 100 kağıdın 6 saat sonra! (Bakiye: {self.bakiyeler[uid]})")
            return

        # 2. DURUM: Daha önce almış, süre kontrolü yap
        gecen_sure = suan - self.son_maas[uid]

        # Eğer 6 saat geçmemişse adamı siktir et
        if gecen_sure < bekleme_suresi:
            kalan_saniye = bekleme_suresi - gecen_sure
            saat = int(kalan_saniye // 3600)
            dakika = int((kalan_saniye % 3600) // 60)
            await ctx.send(
                f"⏳ Yavaş amk ne ara paranı ezdin! Daha maaş gününe **{saat} saat {dakika} dakika** var. Çık dışarı çimlere dokun, sonra gel.")
            return

        # 3. DURUM: 6 saat geçmiş, 100 doları (pardon kağıdı) ateşle
        self.bakiyeler[uid] += 100
        self.son_maas[uid] = suan
        await ctx.send(
            f"💸 Al bakalım aslanım, 6 saatlik nöbetin doldu. **100 kağıt** yattı. Git masada katla gel! (Bakiye: {self.bakiyeler[uid]})")

    @commands.command(aliases=['cüzdan', 'para'])
    async def bakiye(self, ctx):
        """Adamın cebindeki parayı göster"""
        uid = ctx.author.id
        miktar = self.bakiyeler.get(uid, 0)
        await ctx.send(f"💳 {ctx.author.mention}, cebinde tam **{miktar}** kağıt var.")

    @commands.command(aliases=['bj'])
    async def blackjack(self, ctx, bahis: int):
        """Olayın koptuğu yer (Aynı kalıyor)"""
        uid = ctx.author.id
        mevcut_para = self.bakiyeler.get(uid, 0)

        if bahis <= 0:
            return await ctx.send("Lan süzme, sıfır veya eksi parayla kumar mı oynanır amk?")

        if mevcut_para < bahis:
            return await ctx.send(
                f"Fakir piç, cebinde {mevcut_para} kağıt var ama {bahis} basmaya çalışıyorsun. Siktir git maaşını bekle!")

        self.bakiyeler[uid] -= bahis
        view = BlackjackView(self, ctx, bahis)
        embed = view.embed_guncelle(durum="devam")
        await ctx.send(embed=embed, view=view)

    @commands.command(aliases=['slots', 'kumar'])
    async def slot(self, ctx, bahis: int):
        """Para yutma makinesi - Slot"""
        import asyncio
        import random

        uid = ctx.author.id
        mevcut_para = self.bakiyeler.get(uid, 0)

        if bahis <= 0:
            return await ctx.send("Lan süzme, sıfır parayla kol mu çekilir amk?")

        if mevcut_para < bahis:
            return await ctx.send(
                f"Fakir piç, cebinde {mevcut_para} kağıt var ama {bahis} basmaya çalışıyorsun. Siktir git maaşını bekle!")

        # Parayı direkt kasadan düşüyoruz
        self.bakiyeler[uid] -= bahis

        emojiler = ['🍒', '🍋', '🍇', '🔔', '💎', '7️⃣']

        # Animasyon niyetine ilk mesaj
        mesaj = await ctx.send("🎰 **Slot dönüyor...**\n`[ 🎰 | 🎰 | 🎰 ]`")

        # 1.5 saniye heyecan yaptır
        await asyncio.sleep(1.5)

        cark1 = random.choice(emojiler)
        cark2 = random.choice(emojiler)
        cark3 = random.choice(emojiler)

        sonuc = f"`[ {cark1} | {cark2} | {cark3} ]`"

        # KAZANÇ HESAPLARI
        if cark1 == cark2 == cark3:
            # 3'ü de aynı (Büyük Vurgun)
            kazanc = bahis * 10
            self.bakiyeler[uid] += kazanc
            await mesaj.edit(
                content=f"🎰 **JACKPOT ANASINI SATAYIM!**\n{sonuc}\n🎉 Vurgun yaptın piç, **{kazanc}** kağıt kazandın! (Bakiye: {self.bakiyeler[uid]})")

        elif cark1 == cark2 or cark2 == cark3 or cark1 == cark3:
            # 2'si aynı (Teselli ikramiyesi)
            kazanc = int(bahis * 1.5)
            self.bakiyeler[uid] += kazanc
            await mesaj.edit(
                content=f"🎰 **Yırttın!**\n{sonuc}\n💵 İkisini tutturdun, **{kazanc}** kağıt aldın. (Bakiye: {self.bakiyeler[uid]})")

        else:
            # Hepsi farklı (Kasa kazandı)
            await mesaj.edit(
                content=f"🎰 **GEÇMİŞ OLSUN!**\n{sonuc}\n💀 Kasa yuttu, **{bahis}** kağıt buhar oldu. (Bakiye: {self.bakiyeler[uid]})")


async def setup(bot):
    await bot.add_cog(Ekonomi(bot))