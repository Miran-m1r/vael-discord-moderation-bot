import discord
from discord.ext import commands, tasks
from utils.channels import admin_role_only
import json
import os
import datetime
import asyncio
from utils.discord_compat import add_cog


class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def backup_path(guild_id: int) -> str:
        os.makedirs("data/backups", exist_ok=True)
        return os.path.join("data", "backups", f"{guild_id}.json")
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
            "guild_id": guild.id,
            "guild_name": guild.name,
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
        with open(self.backup_path(guild.id), "w", encoding="utf-8") as f:
            json.dump(yedek, f, indent=4, ensure_ascii=False)

    # ====================================================================
    # 3. MANUEL YEDEK ALMA (Ne olur ne olmaz komutu)
    # ====================================================================
    @discord.slash_command(name="backup_al", description="Sunucu yapısının yedeğini oluşturur.")
    @commands.has_permissions(administrator=True)
    @admin_role_only()
    async def backup_al(self, ctx: discord.ApplicationContext):
        settings = await self.bot.db.get_settings(ctx.guild.id)
        if not settings or settings.get("admin_channel") != ctx.channel.id:
            return await ctx.send("Bu komut yalnızca kurulumdaki admin kanalında kullanılabilir.")
        mesaj = await ctx.send("⏳ Sunucu yedeği oluşturuluyor. Lütfen bekleyiniz...")
        await self.yedek_olustur(ctx.guild)
        await mesaj.edit(content="✅ **Sunucu yedeği oluşturuldu.** Sunucuya özel yedek dosyası hazır.")

    # ====================================================================
    # 4. KIYAMET PROTOKOLÜ (Nuke yiyen sunucuyu baştan inşa etme)
    # ====================================================================
    @discord.slash_command(name="backup_yukle", description="Sunucu yapısını yedekten geri yükler.")
    @commands.has_permissions(administrator=True)
    @admin_role_only()
    async def backup_yukle(self, ctx: discord.ApplicationContext):
        settings = await self.bot.db.get_settings(ctx.guild.id)
        if not settings or settings.get("admin_channel") != ctx.channel.id:
            return await ctx.send("Bu komut yalnızca kurulumdaki admin kanalında kullanılabilir.")
        backup_path = self.backup_path(ctx.guild.id)
        if not os.path.exists(backup_path):
            return await ctx.send("Yüklenecek bir yedek dosyası bulunamadı.")

        onay_mesaji = await ctx.send(
            f"⚠️ **UYARI!** Bu işlem {ctx.guild.name} sunucusundaki mevcut kanalları ve rolleri silerek "
            "sunucuya ait yedekteki yapıyı geri yükleyecektir. "
            "Devam etmek için `Evet` yazınız.")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "evet"

        try:
            await self.bot.wait_for('message', timeout=15.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("Onay süresi doldu. Geri yükleme işlemi iptal edildi.")

        await ctx.send("☢️ **Geri yükleme işlemi başlatıldı. Mevcut sunucu yapısı yeniden oluşturulacaktır.** ☢️")

        # Dosyayı oku
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                yedek = json.load(f)
        except (OSError, json.JSONDecodeError):
            return await ctx.send("Yedek dosyası okunamadı; geri yükleme işlemi başlatılmadı.")
        if yedek.get("guild_id") != ctx.guild.id:
            return await ctx.send("Yedek dosyası bu sunucuya ait değildir; işlem iptal edildi.")

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


def setup(bot):
    return add_cog(bot, Backup(bot))