import discord
from discord.ext import commands, tasks
from utils.channels import admin_role_only
import json
import os
import datetime
import asyncio


class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    def cog_unload(self):
        self.gece_yarisi_yedek.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.gece_yarisi_yedek.is_running():
            self.gece_yarisi_yedek.start()

    # ====================================================================
    # 1. HER GECE 12:00'DA OTOMATİK ÇALIŞAN İŞÇİ
    # ====================================================================
    # Türkiye saatiyle (UTC+3) tam gece 00:00'da çalışır
    tz = datetime.timezone(datetime.timedelta(hours=3))

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=tz))
    async def gece_yarisi_yedek(self):
        for guild in self.bot.guilds:
            await self.yedek_olustur(guild)
        print(f"[{datetime.datetime.now().strftime('%H:%M')}] Gece vardiyası tamamlandı: Sunucu yedekleri alındı!")

    # ====================================================================
    # 2. YEDEK ALMA MOTORU (İskeleti Çıkartır)
    # ====================================================================
    async def yedek_olustur(self, guild):
        yedek = {
            "roller": [],
            "kategoriler": [],
            "kanallar": []
        }

        # Rolleri kopyala
        for rol in guild.roles:
            if rol.name != "@everyone" and not rol.managed:  # Botların kendi rollerini elleme
                yedek["roller"].append({
                    "isim": rol.name,
                    "renk": rol.color.value,
                    "ayri_goster": rol.hoist,  # Sağda ayrı mı duryor?
                    "izinler": rol.permissions.value
                })

        # Kategorileri kopyala
        for kategori in guild.categories:
            yedek["kategoriler"].append({
                "isim": kategori.name,
                "pozisyon": kategori.position
            })

        # Kanalları kopyala (Yazı ve Ses)
        for kanal in guild.channels:
            if isinstance(kanal, discord.TextChannel) or isinstance(kanal, discord.VoiceChannel):
                yedek["kanallar"].append({
                    "tip": "yazi" if isinstance(kanal, discord.TextChannel) else "ses",
                    "isim": kanal.name,
                    "kategori": kanal.category.name if kanal.category else None,
                    "pozisyon": kanal.position
                })

        # Json dosyasına zımbala (Cloud mantığı, klasörde tutuyoruz)
        with open("sunucu_backup.json", "w", encoding="utf-8") as f:
            json.dump(yedek, f, indent=4, ensure_ascii=False)

    # ====================================================================
    # 3. MANUEL YEDEK ALMA (Ne olur ne olmaz komutu)
    # ====================================================================
    @commands.command()
    @admin_role_only()
    async def backup_al(self, ctx):
        settings = await self.bot.db.get_settings(ctx.guild.id)
        if not settings or settings.get("admin_channel") != ctx.channel.id:
            return await ctx.send("Bu komut yalnızca kurulumdaki admin kanalında kullanılabilir.")
        mesaj = await ctx.send("⏳ Sunucunun röntgeni çekiliyor, bekle amk...")
        await self.yedek_olustur(ctx.guild)
        await mesaj.edit(content="✅ **Mekanın iskeleti kaydedildi.** `sunucu_backup.json` dosyası zımba gibi hazır.")

    # ====================================================================
    # 4. KIYAMET PROTOKOLÜ (Nuke yiyen sunucuyu baştan inşa etme)
    # ====================================================================
    @commands.command()
    @admin_role_only()
    async def backup_yukle(self, ctx):
        settings = await self.bot.db.get_settings(ctx.guild.id)
        if not settings or settings.get("admin_channel") != ctx.channel.id:
            return await ctx.send("Bu komut yalnızca kurulumdaki admin kanalında kullanılabilir.")
        if not os.path.exists("sunucu_backup.json"):
            return await ctx.send("Lan ortada yedek dosyası yok, neyi yükleyeceğim amk?")

        onay_mesaji = await ctx.send(
            "⚠️ **UYARI!** Bu komut mevcut TÜM kanalları ve rolleri SİLİP dünkü yedeği kuracak. Emin misin lan? (Evet yaz)")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "evet"

        try:
            await self.bot.wait_for('message', timeout=15.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("Zamanında cevap vermedin, iptal ettim. Altıma sıçtım korkudan de geç.")

        await ctx.send("☢️ **KIYAMET PROTOKOLÜ BAŞLADI! MEVCUT HER ŞEY YIKILIYOR!** ☢️")

        # Dosyayı oku
        with open("sunucu_backup.json", "r", encoding="utf-8") as f:
            yedek = json.load(f)

        # 1. YIKIM AŞAMASI (Her şeyi sil)
        for kanal in ctx.guild.channels:
            try:
                await kanal.delete()
            except:
                pass

        for rol in ctx.guild.roles:
            if rol.name != "@everyone" and not rol.managed:
                try:
                    await rol.delete()
                except:
                    pass

        # Geri bildirim için tek bir acil durum kanalı açalım
        acil_kanal = await ctx.guild.create_text_channel("insaat-alani")
        await acil_kanal.send(
            "🏗️ Yıkım bitti, sunucu dünkü yedeğe göre yeniden inşa ediliyor. Discord API limitlerine takılmamak için biraz sürecek, dokunma bekle...")

        # 2. İNŞAAT AŞAMASI (Roller)
        for r in yedek["roller"]:
            try:
                await ctx.guild.create_role(
                    name=r["isim"],
                    color=discord.Color(r["renk"]),
                    hoist=r["ayri_goster"],
                    permissions=discord.Permissions(r["izinler"])
                )
            except:
                pass

        # 3. İNŞAAT AŞAMASI (Kategoriler ve Kanallar)
        kategori_objeleri = {}
        for kat in yedek["kategoriler"]:
            yeni_kat = await ctx.guild.create_category(name=kat["isim"])
            kategori_objeleri[kat["isim"]] = yeni_kat

        for k in yedek["kanallar"]:
            kat_objesi = kategori_objeleri.get(k["kategori"])
            if k["tip"] == "yazi":
                await ctx.guild.create_text_channel(name=k["isim"], category=kat_objesi)
            else:
                await ctx.guild.create_voice_channel(name=k["isim"], category=kat_objesi)
            await asyncio.sleep(1)  # Discord Rate Limit (Ban) yememek için 1 saniye bekleme

        await acil_kanal.send("✅ **OPERASYON TAMAM!** Sunucu dünkü haline getirildi. Mekan senin, patron!")


async def setup(bot):
    await bot.add_cog(Backup(bot))