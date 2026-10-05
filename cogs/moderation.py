import discord
from discord.ext import commands
import re
import datetime
import time
import os
from dotenv import load_dotenv, find_dotenv
from openai import AsyncOpenAI
from utils.channels import admin_role_only, require_channel


load_dotenv(find_dotenv())


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # KÜFÜR VE REKLAM FİLTRELERİ (Regex - Anında silinenler)
        self.banned_words_regex = re.compile(r"(oç|orospu|siktir|piç)", re.IGNORECASE)
        self.ads_regex = re.compile(r"(discord\.gg/|http[s]?://)", re.IGNORECASE)

        # AI TETİKLEYİCİLERİ
        self.supheli_kelimeler = ["lan", "mal", "aptal", "salak", "kes", "sus", "ezik", "velet", "sg", "sana ne"]


        self.zindan_rol_id = int(os.getenv("ZINDAN_ROL_ID", 0))

        api_key = os.getenv("OPEN_AI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.ai_client = AsyncOpenAI(api_key=api_key) if api_key else None



        self.trust_scores = {}
        self.clean_messages = {}
        self.nuke_tracker = {}

    async def log_channel(self, guild):
        settings = await self.bot.db.get_settings(guild.id)
        return guild.get_channel(settings["log_channel"]) if settings and settings["log_channel"] else None



    async def ai_niyet_okuyucu(self, text):
        """AsyncOpenAI ile temiz entegrasyon"""
        if self.ai_client is None:
            return False
        try:
            response = await self.ai_client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Sen  bir Discord moderatörüsün. Sadece 'EVET' veya 'HAYIR' cevabı vereceksin. Kullanıcının mesajında pasif-agresiflik, dolaylı hakaret, aşağılama veya laf sokma varsa 'EVET' de. Eğer normal bir muhabbet, arkadaşça argo veya şakaysa 'HAYIR' de."
                    },
                    {"role": "user", "content": text}
                ],
                temperature=0.1
            )
            cevap = response.choices[0].message.content.strip().upper()
            return "EVET" in cevap

        except Exception as e:
            print(f"LLM API Patladı amk: {e}")
            return False

    async def guven_puani_kes(self, member, miktar, sebep):
        uid = member.id
        if uid not in self.trust_scores:
            self.trust_scores[uid] = 100

        self.trust_scores[uid] -= miktar
        guncel_puan = self.trust_scores[uid]

        settings = await self.bot.db.get_settings(member.guild.id)
        log_kanali = member.guild.get_channel(settings["log_channel"]) if settings and settings["log_channel"] else None
        if log_kanali:
            embed = discord.Embed(title="📉 Sosyal Kredi Düştü!", color=discord.Color.orange())
            embed.description = f"**{member.name}** kişisinin puanı **{guncel_puan}**'a düştü.\n**Sebep:** {sebep}"
            await log_kanali.send(embed=embed)

        if guncel_puan <= 10:
            zindan_rolu = member.guild.get_role(self.zindan_rol_id)
            if zindan_rolu:
                eski_roller = [r for r in member.roles if r.name != "@everyone"]
                await member.remove_roles(*eski_roller)
                await member.add_roles(zindan_rolu)
                await log_kanali.send(f"⛓️ **{member.name}** kredisini tüketti ve Zindana atıldı!")

        elif guncel_puan <= 30:
            sure = datetime.timedelta(hours=2)
            try:
                await member.timeout(sure, reason="Sosyal kredi 30'un altına düştü.")
                await log_kanali.send(
                    f"🔇 **{member.name}** kredisini ({guncel_puan}) çok düşürdüğü için 2 saat susturuldu.")
            except:
                pass



    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.author.guild_permissions.administrator:
            return

        icerik = message.content
        icerik_lower = icerik.lower()
        bosluksuz = icerik_lower.replace(" ", "")

        if self.banned_words_regex.search(bosluksuz) or self.ads_regex.search(bosluksuz):
            await message.delete()
            await message.channel.send(f"{message.author.mention} Mekanda düzgün konuş, kredi puanını yakma!")
            await self.guven_puani_kes(message.author, 5, "Açıkça küfür veya reklam/link paylaştı.")
            return

        if any(kelime in icerik_lower for kelime in self.supheli_kelimeler):
            is_toxic = await self.ai_niyet_okuyucu(icerik)
            if is_toxic:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} Kelime oyunu yapma lan, o dolaylı laf sokmaları yapay zeka yemez!")
                await self.guven_puani_kes(message.author, 10,
                                           "AI tarafından pasif-agresif / gizli toksiklik algılandı.")
                return

        uid = message.author.id
        if uid not in self.trust_scores:
            self.trust_scores[uid] = 100

        if self.trust_scores[uid] < 150:
            self.clean_messages[uid] = self.clean_messages.get(uid, 0) + 1
            if self.clean_messages[uid] >= 15:
                self.trust_scores[uid] = min(100, self.trust_scores[uid] + 5)
                self.clean_messages[uid] = 0



    @commands.hybrid_command()
    async def kredi(self, ctx):
        uid = ctx.author.id
        puan = self.trust_scores.get(uid, 100)

        if puan >= 90:
            durum = "Tertemiz adamsın, mekanın krallarındansın."
        elif puan >= 60:
            durum = "Ufaktan vukuatların var ama toparlarsın, dikkat et."
        elif puan >= 30:
            durum = "İnce buzdasıın kardeşim, bir hatanda ağzını bantlarlar."
        else:
            durum = "Tek ayağın çukurda, ha siktir edildin ha edileceksin!"

        embed = discord.Embed(title="💳 Sosyal Kredi Skoru", color=discord.Color.blurple())
        embed.add_field(name="Mevcut Puanın:", value=f"**{puan} / 100**", inline=False)
        embed.add_field(name="Durum Özeti:", value=durum, inline=False)
        embed.set_footer(text="Düzgün muhabbet ettikçe puanın yavaş yavaş yükselir.")
        await ctx.send(embed=embed)

    # ====================================================================
    # 4. HAYALET ETİKET (Ghost-Ping) & DÜZENLEME AVCISI
    # ====================================================================
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return

        if message.mentions:
            await message.channel.send(
                f"👻 **{message.author.name}** birilerini etiketleyip sildi! Yemedi mi lan?\nSildiği mesaj: `{message.content}`")
            await self.guven_puani_kes(message.author, 5, "Ghost-Ping (Hayalet Etiket) attı.")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return

        log_kanali = await self.log_channel(before.guild)
        if log_kanali:
            embed = discord.Embed(title="✍️ Şark Kurnazı Mesaj Düzenledi!", color=discord.Color.light_grey())
            embed.add_field(name="Kişi:", value=before.author.name, inline=False)
            embed.add_field(name="Önceki Hali:", value=before.content or "Boş", inline=False)
            embed.add_field(name="Sonraki Hali:", value=after.content or "Boş", inline=False)
            await log_kanali.send(embed=embed)

    # ====================================================================
    # 5. ANTI-NUKE (Darbe ve Hacking Koruması)
    # ====================================================================
    async def check_nuke_attempt(self, admin_user, guild):
        uid = admin_user.id
        suan = time.time()

        if uid not in self.nuke_tracker:
            self.nuke_tracker[uid] = []

        self.nuke_tracker[uid] = [t for t in self.nuke_tracker[uid] if suan - t < 3]
        self.nuke_tracker[uid].append(suan)

        if len(self.nuke_tracker[uid]) >= 3:
            log_kanali = await self.log_channel(guild)
            try:
                eski_roller = [r for r in admin_user.roles if r.name != "@everyone"]
                await admin_user.remove_roles(*eski_roller)
                if log_kanali:
                    await log_kanali.send(
                        f"🚨 **DARBE GİRİŞİMİ ENGELLENDİ!** 🚨\n{admin_user.name} çıldırdı, bot otomatik olarak tüm yetkilerini elinden aldı!")
            except:
                if log_kanali:
                    await log_kanali.send(
                        f"🚨 **DARBE VAR AMA GÜCÜM YETMEDİ!** 🚨\n{admin_user.name} sunucuyu patlatıyor, rolü benden yüksek olduğu için alamadım. ÇABUK GEL AMK!")
            self.nuke_tracker[uid] = []

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                await self.check_nuke_attempt(entry.user, guild)
                break

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if entry.target.id == channel.id:
                await self.check_nuke_attempt(entry.user, channel.guild)
                break

        log_kanali = await self.log_channel(channel.guild)
        if log_kanali:
            embed = discord.Embed(title="🗑️ Oda Silindi!", color=discord.Color.dark_red())
            embed.add_field(name="Giden Kanal:", value=channel.name, inline=True)
            embed.add_field(name="Silen Yetkili:", value=entry.user.name, inline=True)
            await log_kanali.send(embed=embed)

    # ====================================================================
    # 6. MANUEL KOMUTLAR (Temizle, Mute, Zindan, Ban)
    # ====================================================================

    @commands.hybrid_command(aliases=['temizle', 'sil'])
    @admin_role_only()
    async def purge(self, ctx, miktar: int):
        if not await require_channel(ctx, "admin_channel"): return
        if miktar > 100: return await ctx.send("Yavaş amk, tek seferde max 100.")
        silinen = await ctx.channel.purge(limit=miktar + 1)
        msg = await ctx.send(f"🧹 {len(silinen) - 1} mesaj buharlaştırıldı.")
        await msg.delete(delay=3)

    @commands.hybrid_command()
    @admin_role_only()
    async def mute(self, ctx, uye: discord.Member, dakika: int, *, sebep="Çok konuştu"):
        if not await require_channel(ctx, "admin_channel"): return
        sure = datetime.timedelta(minutes=dakika)
        await uye.timeout(sure, reason=sebep)
        await ctx.send(f"🔇 **{uye.name}** {dakika} dakika boyunca susturuldu. Sebep: {sebep}")

        log_kanali = await self.log_channel(ctx.guild)
        if log_kanali:
            embed = discord.Embed(title="🔇 Biri Susturuldu!", color=discord.Color.dark_red())
            embed.add_field(name="Susturan Mod:", value=ctx.author.name, inline=True)
            embed.add_field(name="Bantlanan:", value=uye.name, inline=True)
            embed.add_field(name="Süre/Sebep:", value=f"{dakika} Dk - {sebep}", inline=False)
            await log_kanali.send(embed=embed)

    @commands.hybrid_command()
    @admin_role_only()
    async def zindan(self, ctx, uye: discord.Member):
        if not await require_channel(ctx, "admin_channel"): return
        zindan_rolu = ctx.guild.get_role(self.zindan_rol_id)
        if not zindan_rolu: return await ctx.send("Zindan rolü bulunamadı amk.")
        eski_roller = [r for r in uye.roles if r.name != "@everyone"]
        await uye.remove_roles(*eski_roller)
        await uye.add_roles(zindan_rolu)
        await ctx.send(f"⛓️ {uye.mention} paketlendi! Zindanda çürüyecek.")

    @commands.hybrid_command()
    @admin_role_only()
    async def ban(self, ctx, uye: discord.Member, *, sebep="Mekanın sahibi öyle istedi"):
        if not await require_channel(ctx, "admin_channel"): return
        await uye.ban(reason=sebep)
        await ctx.send(f"🔨 {uye.name} sunucudan siktir edildi! Sebep: {sebep}")



    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        log_kanali = await self.log_channel(channel.guild)
        if not log_kanali: return
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
            yapan = entry.user
            break
        embed = discord.Embed(title="📁 Yeni Oda Açıldı!", color=discord.Color.green())
        embed.add_field(name="Kanal:", value=channel.name, inline=True)
        embed.add_field(name="Açan:", value=yapan.name, inline=True)
        await log_kanali.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        log_kanali = await self.log_channel(after.guild)
        if not log_kanali: return

        if len(before.roles) < len(after.roles):
            eklenen = next(role for role in after.roles if role not in before.roles)
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                yapan = entry.user
                break
            await log_kanali.send(embed=discord.Embed(title="🏷️ Rol Verildi",
                                                      description=f"**{yapan.name}**, **{after.name}** kişisine **{eklenen.name}** rolünü bastı.",
                                                      color=discord.Color.blue()))

        elif len(before.roles) > len(after.roles):
            alinan = next(role for role in before.roles if role not in after.roles)
            async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                yapan = entry.user
                break
            await log_kanali.send(embed=discord.Embed(title="📉 Rütbe Söküldü",
                                                      description=f"**{yapan.name}**, **{after.name}** kişisinin **{alinan.name}** rolünü kesti.",
                                                      color=discord.Color.orange()))


async def setup(bot):
    await bot.add_cog(Moderation(bot))