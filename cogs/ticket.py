import discord
from discord.ext import commands
import io
import os
from dotenv import load_dotenv,find_dotenv
from openai import AsyncOpenAI

load_dotenv(find_dotenv())


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
        await interaction.response.send_message("🧠 *Ajan konuşmaları okuyor ve çözüm üretiyor, bekle amk...*",
                                                ephemeral=False)

        # Kanaldaki son 20 mesajı al (LLM'e bağlam sunmak için)
        mesajlar = [m async for m in interaction.channel.history(limit=20, oldest_first=True)]
        sohbet_gecmisi = "\n".join([f"{m.author.name}: {m.clean_content}" for m in mesajlar if not m.author.bot])

        if not sohbet_gecmisi.strip():
            return await interaction.channel.send(
                "Ulan derdini yazmamışsın ki yapay zeka neye cevap versin? Önce sorununu yaz!")

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
            await interaction.channel.send("Yapay zeka motoru şu an patlak, yetkili bekleyeceksin aslanım.")
            print(f"LLM Hatası: {e}")

    # --- TİCKET KAPATMA VE AI ÖZETLEME ---
    @discord.ui.button(label="🔒 Talebi Kapat", style=discord.ButtonStyle.danger, custom_id="ticket_kapat_buton")
    async def kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏳ Kanal 10 saniye içinde buharlaşıyor, AI log özetini çıkarıyor...",
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
        mod_rol = guild.get_role(self.cog.mod_rol_id)

        suanki_sayi = self.cog.ticket_sayaci
        kanal_adi = f"ticket-{suanki_sayi}"
        self.cog.ticket_sayaci += 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        }
        if mod_rol:
            overwrites[mod_rol] = discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                              manage_messages=True)

        yeni_kanal = await guild.create_text_channel(kanal_adi, overwrites=overwrites,
                                                     category=interaction.channel.category)

        await interaction.response.send_message(f"✅ Talebin oluşturuldu aslanım: {yeni_kanal.mention}", ephemeral=True)

        embed = discord.Embed(
            title="Destek Talebi",
            description=f"Hoş geldin {interaction.user.mention}. Derdini yaz. Yetkili beklemek istemiyorsan aşağıdaki **🤖 Yapay Zekaya Sor** butonuna basarak anında destek alabilirsin.",
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

        self.mod_rol_id = int(os.getenv("MOD_ROL_ID", 0))


        api_key = os.getenv("OPENAI_API_KEY")
        self.ai_client = AsyncOpenAI(api_key=api_key) if api_key else None

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(TicketAcView(self))
        self.bot.add_view(TicketİciView(self))
        print("LLM Destekli Ticket modülü fişek gibi yüklendi.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ticket_kur(self, ctx):
        settings = await self.bot.db.get_settings(ctx.guild.id)
        if not settings or settings.get("admin_channel") != ctx.channel.id:
            return await ctx.send("Bu komut yalnızca kurulumdaki admin kanalında kullanılabilir.")
        embed = discord.Embed(
            title="🎫 Mekan Destek Merkezi",
            description="Bir derdin varsa aşağıdaki butona tıkla. Yapay zeka ajanımız ve yetkililerimiz sana yardımcı olacak.",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed, view=TicketAcView(self))


async def setup(bot):
    await bot.add_cog(Ticket(bot))