import discord
from discord.ext import commands
import io
import os
import asyncio
from dotenv import load_dotenv,find_dotenv
from openai import AsyncOpenAI
from utils.channels import require_channel
from utils.discord_compat import add_cog

load_dotenv(find_dotenv())


def _env_role_id(*names: str) -> int:
    for name in names:
        try:
            value = int(os.getenv(name, "0") or 0)
        except ValueError:
            continue
        if value > 0:
            return value
    return 0


# ====================================================================
# 1. TİCKET İÇİ KONTROL PANELİ (Kapatma ve AI Destek)
# ====================================================================
class TicketİciView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    # --- TIER-1 AI DESTEK AJANI ---
    @discord.ui.button(label="🤖 Yapay Zekaya Sor", style=discord.ButtonStyle.success, custom_id="ai_destek_buton")
    async def ai_destek(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🧠 *Görüşme geçmişi inceleniyor ve çözüm hazırlanıyor. Lütfen bekleyiniz...*",
                                                ephemeral=False)

        # Kanaldaki son 20 mesajı al (LLM'e bağlam sunmak için)
        mesajlar = [m async for m in interaction.channel.history(limit=20, oldest_first=True)]
        sohbet_gecmisi = "\n".join([f"{m.author.name}: {m.clean_content}" for m in mesajlar if not m.author.bot])

        if not sohbet_gecmisi.strip():
            return await interaction.channel.send(
                "Çözüm oluşturulabilmesi için lütfen önce talebinizi açıklayınız.")

        # LLM'e Prompt Çakıyoruz
        try:
            response = await self.cog.ai_client.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {"role": "system",
                     "content": "Sen bu Discord sunucusunun 'Seviye 1 Teknik Destek Ajanısın'. Aşağıdaki kullanıcı mesajlarını oku ve sorunu çözmeye çalış. Samimi ama profesyonel ol. Çözemeyeceğin yetkisel bir şeyse 'Yetkili ekibimiz birazdan ilgilenecek' de. Kısa ve öz ol."},
                    {"role": "user", "content": sohbet_gecmisi}
                ],
                temperature=0.5
            )
            ai_cevabi = response.choices[0].message.content

            embed = discord.Embed(title="🤖 AI Destek Temsilcisi", description=ai_cevabi,
                                  color=discord.Color.brand_green())
            await interaction.channel.send(embed=embed)
        except Exception as e:
            await interaction.channel.send("Yapay zekâ hizmeti şu anda kullanılamıyor. Lütfen destek ekibinin yanıtını bekleyiniz.")
            print(f"LLM Hatası: {e}")

    # --- TİCKET KAPATMA VE AI ÖZETLEME ---
    @discord.ui.button(label="🔒 Talebi Kapat", style=discord.ButtonStyle.danger, custom_id="ticket_kapat_buton")
    async def kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message(
                "Bu işlem yalnızca sunucu içinde yapılabilir.", ephemeral=True
            )
        is_staff = any(
            interaction.user.get_role(role_id)
            for role_id in (self.cog.mod_rol_id, self.cog.admin_rol_id)
            if role_id
        )
        owner_id = interaction.channel.topic.removeprefix("ticket_owner:") if interaction.channel.topic else ""
        if not is_staff and owner_id != str(interaction.user.id):
            return await interaction.response.send_message(
                "Bu ticket'ı yalnızca ticket sahibi veya yetkili ekip kapatabilir.", ephemeral=True
            )
        await interaction.response.send_message("⏳ Kanal 10 saniye içinde arşivlenecek. Görüşme özeti hazırlanıyor...",
                                                ephemeral=True)

        mesajlar = [m async for m in interaction.channel.history(limit=None, oldest_first=True)]

        transcript = f"--- {interaction.channel.name} LOG KAYITLARI ---\n"
        for m in mesajlar:
            zaman = m.created_at.strftime("%H:%M:%S")
            transcript += f"[{zaman}] {m.author.name}: {m.content}\n"

        # AI'a "Bunu Özetle" Diyoruz
        ai_ozet = "Özet çıkarılamadı."
        try:
            response = await self.cog.ai_client.chat.completions.create(
                model="gpt-5.4",
                messages=[
                    {"role": "system",
                     "content": "Sen bir yönetici asistanısın. Aşağıdaki ticket konuşma geçmişini oku ve YALNIZCA 2-3 cümle ile kullanıcının sorununun ne olduğunu ve nasıl çözüldüğünü (veya çözülemediğini) özetle."},
                    {"role": "user", "content": transcript}
                ],
                temperature=0.3
            )
            ai_ozet = response.choices[0].message.content
        except:
            pass

        dosya_byte = io.BytesIO(transcript.encode('utf-8'))
        discord_dosya = discord.File(fp=dosya_byte, filename=f"{interaction.channel.name}-log.txt")

        # Şekilli Log ve AI Özeti
        settings = await self.cog.bot.db.get_settings(interaction.guild.id)
        log_kanali = interaction.guild.get_channel(settings["log_channel"]) if settings and settings["log_channel"] else None
        if log_kanali:
            embed = discord.Embed(title="📁 Ticket Arşivlendi", color=discord.Color.red())
            embed.add_field(name="Kapanan Kanal:", value=interaction.channel.name, inline=True)
            embed.add_field(name="Kapatan Yetkili:", value=interaction.user.name, inline=True)
            embed.add_field(name="🤖 AI Özeti:", value=f"*{ai_ozet}*", inline=False)  # KRİTİK NOKTA BURASI
            await log_kanali.send(embed=embed, file=discord_dosya)

        await interaction.channel.delete()


# ====================================================================
# 2. TİCKET AÇMA BUTONU (ANA PANEL)
# ====================================================================
class TicketAcView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🎫 Destek Talebi Aç", style=discord.ButtonStyle.primary, custom_id="ticket_ac_buton")
    async def ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "Ticket yalnızca sunucularda açılabilir.", ephemeral=True
            )
        async with self.cog.ticket_lock:
            existing = next(
                (
                    channel for channel in guild.text_channels
                    if channel.name.startswith("ticket-")
                    and channel.topic == f"ticket_owner:{interaction.user.id}"
                ),
                None,
            )
            if existing:
                return await interaction.response.send_message(
                    f"Zaten açık bir ticket'ınız bulunmaktadır: {existing.mention}", ephemeral=True
                )
            suanki_sayi = self.cog.ticket_sayaci
            kanal_adi = f"ticket-{suanki_sayi}"
            while discord.utils.get(guild.text_channels, name=kanal_adi):
                suanki_sayi += 1
                kanal_adi = f"ticket-{suanki_sayi}"
            self.cog.ticket_sayaci = suanki_sayi + 1

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, attach_files=True
                ),
            }
            for role_id in (self.cog.mod_rol_id, self.cog.admin_rol_id):
                role = guild.get_role(role_id) if role_id else None
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True, manage_messages=True
                    )
            settings = await self.cog.bot.db.get_settings(guild.id)
            ticket_channel_id = settings.get("ticket_channel") if settings else None
            ticket_channel = guild.get_channel(ticket_channel_id) if ticket_channel_id else None
            category = ticket_channel.category if isinstance(ticket_channel, discord.TextChannel) else interaction.channel.category
            yeni_kanal = await guild.create_text_channel(
                kanal_adi, overwrites=overwrites, category=category,
                topic=f"ticket_owner:{interaction.user.id}",
            )

        await interaction.response.send_message(f"✅ Destek talebiniz oluşturuldu: {yeni_kanal.mention}", ephemeral=True)

        embed = discord.Embed(
            title="Destek Talebi",
            description=f"Merhaba {interaction.user.mention}. Talebinizi bu kanala yazabilirsiniz. Destek almak için aşağıdaki **🤖 Yapay Zekaya Sor** düğmesini kullanabilirsiniz.",
            color=discord.Color.green()
        )
        # Bütün butonları (AI ve Kapatma) içeren View'i gönderiyoruz
        await yeni_kanal.send(content=f"{interaction.user.mention}", embed=embed, view=TicketİciView(self.cog))


# ====================================================================
# 3. ANA COG (Modül) BAĞLANTISI
# ====================================================================
class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_sayaci = 0
        self.mod_rol_id = _env_role_id("MOD_ROLE_ID", "MOD_ROL_ID")
        self.admin_rol_id = _env_role_id("ADMIN_ROLE_ID")
        self.ticket_lock = asyncio.Lock()


        api_key = os.getenv("OPENAI_API_KEY")
        self.ai_client = AsyncOpenAI(api_key=api_key) if api_key else None

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TicketAcView(self))
        self.bot.add_view(TicketİciView(self))
        print("LLM destekli ticket modülü başarıyla yüklendi.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ticket_kur(self, ctx):
        if not await require_channel(ctx, "admin_channel"):
            return
        settings = await self.bot.db.get_settings(ctx.guild.id)
        ticket_channel_id = settings.get("ticket_channel") if settings else None
        ticket_channel = ctx.guild.get_channel(ticket_channel_id) if ticket_channel_id else None
        if not isinstance(ticket_channel, discord.TextChannel):
            return await ctx.send("Önce `!kurulum` ile geçerli bir ticket paneli kanalı seçilmelidir.")
        embed = discord.Embed(
            title="🎫 Mekan Destek Merkezi",
            description="Destek talebi oluşturmak için aşağıdaki düğmeyi kullanınız. Destek ekibimiz ve yapay zekâ asistanımız size yardımcı olacaktır.",
            color=discord.Color.blurple()
        )
        await ticket_channel.send(embed=embed, view=TicketAcView(self))
        await ctx.send(f"✅ Ticket paneli {ticket_channel.mention} kanalına gönderildi.")


def setup(bot):
    return add_cog(bot, Ticket(bot))