import asyncio
import io
import random
import time
from typing import Any

import discord
from discord.ext import commands
from PIL import Image, ImageDraw

from utils.channels import require_channel
from utils.discord_compat import add_cog

SUITS = ["♠️", "♥️", "♣️", "♦️"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def build_deck() -> list[tuple[str, str]]:
    deck = [(rank, suit) for rank in RANKS for suit in SUITS] * 2
    random.shuffle(deck)
    return deck


def format_card(card: tuple[str, str]) -> str:
    return f"`[{card[0]} {card[1]}]`"


def format_hand(hand: list[tuple[str, str]], hide_second: bool = False) -> str:
    if hide_second and len(hand) > 1:
        return f"{format_card(hand[0])} `[? 🎴]`"
    return " ".join(format_card(c) for c in hand)


def score_hand(hand: list[tuple[str, str]]) -> int:
    score = 0
    aces = 0
    for rank, _ in hand:
        if rank in ("J", "Q", "K"):
            score += 10
        elif rank == "A":
            score += 11
            aces += 1
        else:
            score += int(rank)
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score


def render_blackjack_table(
    dealer_hand: list[tuple[str, str]],
    player_hand: list[tuple[str, str]],
    hide_second: bool = False,
    player_name: str = "Oyuncu",
    status: str = "Hamlenizi seçiniz...",
    bet: int = 100,
    is_win: bool | None = None,
    filename: str = "blackjack.png",
) -> discord.File:
    """Renders an authentic, high-resolution casino blackjack green felt table image."""
    W, H = 760, 440
    im = Image.new("RGB", (W, H), (12, 48, 26))
    draw = ImageDraw.Draw(im)

    # Table felt outer border & arc
    draw.rounded_rectangle([12, 12, W - 12, H - 12], radius=20, outline=(197, 160, 89), width=3)
    draw.arc([40, -180, W - 40, 420], start=0, end=180, fill=(160, 130, 70), width=2)
    draw.text((W // 2 - 175, 200), "BLACKJACK PAYS 3 TO 2 • DEALER STANDS ON 17", fill=(140, 115, 60))

    # Helper: draw single card
    def draw_card(x: int, y: int, card: tuple[str, str], is_hidden: bool = False):
        cw, ch = 80, 115
        # Drop shadow
        draw.rounded_rectangle([x + 3, y + 4, x + cw + 3, y + ch + 4], radius=6, fill=(8, 28, 16))
        if is_hidden:
            draw.rounded_rectangle([x, y, x + cw, y + ch], radius=6, fill=(160, 20, 30), outline=(230, 230, 230), width=2)
            draw.rounded_rectangle([x + 5, y + 5, x + cw - 5, y + ch - 5], radius=4, outline=(220, 180, 50), width=1)
            for dx in range(10, cw - 10, 10):
                draw.line([(x + dx, y + 8), (x + dx, y + ch - 8)], fill=(125, 15, 20))
            return
        draw.rounded_rectangle([x, y, x + cw, y + ch], radius=6, fill=(255, 255, 255), outline=(30, 30, 30), width=1)
        rank, suit = card
        is_red = suit in ("♥️", "♦️")
        color = (200, 20, 30) if is_red else (20, 20, 25)
        draw.text((x + 6, y + 4), rank, fill=color)
        draw.text((x + cw // 2 - 8, y + ch // 2 - 12), suit, fill=color)
        draw.text((x + cw - 18, y + ch - 18), rank, fill=color)

    # Dealer section (Top)
    d_score = "?" if hide_second else str(score_hand(dealer_hand))
    draw.rounded_rectangle([W // 2 - 145, 24, W // 2 + 145, 52], radius=6, fill=(20, 24, 28), outline=(197, 160, 89))
    draw.text((W // 2 - 115, 30), f"DEALER (KRUPİYE) [SKOR: {d_score}]", fill=(255, 215, 0))
    d_total_w = len(dealer_hand) * 92 - 12
    dx_start = (W - d_total_w) // 2
    for idx, card in enumerate(dealer_hand):
        draw_card(dx_start + idx * 92, 64, card, is_hidden=(hide_second and idx > 0))

    # Player section (Bottom)
    p_score = str(score_hand(player_hand))
    clean_pname = player_name[:16]
    draw.rounded_rectangle([W // 2 - 165, 230, W // 2 + 165, 258], radius=6, fill=(20, 24, 28), outline=(197, 160, 89))
    draw.text((W // 2 - 135, 236), f"{clean_pname.upper()} [SKOR: {p_score}]", fill=(255, 215, 0))
    p_total_w = len(player_hand) * 92 - 12
    px_start = (W - p_total_w) // 2
    for idx, card in enumerate(player_hand):
        draw_card(px_start + idx * 92, 270, card)

    # Bottom status banner
    status_bg = (20, 80, 40) if is_win is True else ((100, 20, 20) if is_win is False else (25, 30, 35))
    draw.rounded_rectangle([30, H - 42, W - 30, H - 14], radius=6, fill=status_bg, outline=(197, 160, 89))
    draw.text((45, H - 36), f"BAHİS: {bet} KREDİ  |  {status[:65]}", fill=(255, 255, 255))

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=filename)


def render_slot_machine(
    reels: list[str],
    status: str = "Makaralar Dönüyor...",
    bet: int = 50,
    win: int = 0,
    is_win: bool | None = None,
    frame: int = 1,
) -> discord.File:
    """Renders a metallic/gold casino slot machine visual with vector symbols."""
    W, H = 560, 360
    im = Image.new("RGB", (W, H), (16, 18, 24))
    draw = ImageDraw.Draw(im)

    # Outer cabinet
    draw.rounded_rectangle([12, 10, W - 12, H - 10], radius=18, fill=(38, 16, 22), outline=(212, 175, 55), width=4)
    # Marquee Header
    draw.rounded_rectangle([30, 20, W - 30, 68], radius=8, fill=(170, 18, 28), outline=(255, 215, 0), width=2)
    draw.text((W // 2 - 80, 34), "★ VEGAS CASINO SLOTS ★", fill=(255, 255, 255))

    # Reel window housing
    rx0, ry0, rx1, ry1 = 45, 85, W - 45, 245
    draw.rounded_rectangle([rx0, ry0, rx1, ry1], radius=10, fill=(14, 14, 18), outline=(130, 130, 140), width=3)

    rw = (rx1 - rx0 - 24) // 3
    for i, sym in enumerate(reels):
        x = rx0 + 8 + i * (rw + 4)
        draw.rounded_rectangle([x, ry0 + 8, x + rw, ry1 - 8], radius=6, fill=(246, 246, 248), outline=(200, 200, 210))
        cx = x + rw // 2
        cy = (ry0 + ry1) // 2

        if sym in ("7", "7️⃣"):
            draw.polygon(
                [(cx - 18, cy - 26), (cx + 20, cy - 26), (cx + 20, cy - 16), (cx - 2, cy + 26), (cx - 14, cy + 26), (cx + 5, cy - 16), (cx - 18, cy - 16)],
                fill=(220, 20, 20),
                outline=(255, 215, 0),
                width=2,
            )
        elif sym in ("diamond", "💎"):
            draw.polygon([(cx, cy - 26), (cx + 24, cy - 8), (cx + 14, cy + 24), (cx - 14, cy + 24), (cx - 24, cy - 8)], fill=(0, 210, 255), outline=(255, 255, 255), width=2)
            draw.line([(cx - 14, cy - 8), (cx + 14, cy - 8)], fill=(255, 255, 255))
        elif sym in ("bell", "🔔"):
            draw.polygon([(cx - 20, cy + 16), (cx + 20, cy + 16), (cx + 15, cy - 8), (cx + 6, cy - 20), (cx - 6, cy - 20), (cx - 15, cy - 8)], fill=(255, 190, 0), outline=(200, 140, 0), width=2)
            draw.ellipse([cx - 5, cy + 16, cx + 5, cy + 24], fill=(200, 140, 0))
        elif sym in ("cherry", "🍒"):
            draw.ellipse([cx - 18, cy + 2, cx - 2, cy + 20], fill=(210, 20, 30))
            draw.ellipse([cx + 2, cy + 6, cx + 18, cy + 24], fill=(210, 20, 30))
            draw.line([(cx - 10, cy + 2), (cx, cy - 16)], fill=(40, 160, 40), width=3)
            draw.line([(cx + 10, cy + 6), (cx, cy - 16)], fill=(40, 160, 40), width=3)
        elif sym in ("lemon", "🍋"):
            draw.ellipse([cx - 22, cy - 16, cx + 22, cy + 16], fill=(255, 225, 20), outline=(210, 170, 0), width=2)
            draw.ellipse([cx + 14, cy - 20, cx + 22, cy - 14], fill=(40, 160, 40))
        elif sym in ("watermelon", "🍉"):
            draw.chord([cx - 22, cy - 16, cx + 22, cy + 22], start=0, end=180, fill=(230, 40, 60), outline=(40, 160, 50), width=4)
        else:
            # Question mark for rolling reels
            draw.ellipse([cx - 14, cy - 22, cx + 14, cy - 2], outline=(255, 215, 0), width=3)
            draw.line([(cx + 8, cy - 10), (cx, cy + 8)], fill=(255, 215, 0), width=3)
            draw.ellipse([cx - 3, cy + 16, cx + 3, cy + 22], fill=(255, 215, 0))

    # Payline across center
    draw.line([(rx0, (ry0 + ry1) // 2), (rx1, (ry0 + ry1) // 2)], fill=(255, 40, 40, 140), width=2)

    # Bottom Dashboard
    meter_bg = (15, 55, 30) if is_win is True else ((55, 15, 20) if is_win is False else (12, 14, 18))
    draw.rounded_rectangle([30, 260, W - 30, 335], radius=8, fill=meter_bg, outline=(212, 175, 55), width=2)
    draw.text((45, 275), f"BAHİS: {bet} KREDİ  |  KAZANÇ: {win} KREDİ", fill=(255, 215, 0))
    draw.text((45, 302), status[:55], fill=(255, 255, 255))

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=f"slot_{frame}.png")


class BlackjackView(discord.ui.View):
    def __init__(self, cog: "Ekonomi", ctx: discord.ApplicationContext, bet: int):
        super().__init__(timeout=90)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.state_lock = asyncio.Lock()
        self.finished = False
        self.render_count = 0

        self.deck = build_deck()
        self.player_hand: list[tuple[str, str]] = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand: list[tuple[str, str]] = [self.deck.pop(), self.deck.pop()]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "Bu masa yalnızca oyunu başlatan kullanıcıya aittir.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(
        self,
        finished: bool = False,
        status_message: str = "Hamlenizi seçiniz...",
        color: discord.Color | None = None,
        is_win: bool | None = None,
    ) -> tuple[discord.Embed, discord.File]:
        player_score = score_hand(self.player_hand)
        dealer_score = score_hand(self.dealer_hand) if finished else score_hand([self.dealer_hand[0]])
        dealer_display_score = f"{dealer_score}" if finished else f"{dealer_score} + ?"

        if color is None:
            color = discord.Color.from_rgb(0, 100, 0)  # Casino Green

        self.render_count += 1
        filename = f"table_{self.render_count}_{int(time.time())}.png"
        file = render_blackjack_table(
            self.dealer_hand,
            self.player_hand,
            hide_second=not finished,
            player_name=self.ctx.author.display_name,
            status=status_message,
            bet=self.bet,
            is_win=is_win,
            filename=filename,
        )

        embed = discord.Embed(
            title="♠️ Casino Blackjack Masası ♦️",
            color=color,
        )
        embed.set_image(url=f"attachment://{filename}")

        embed.add_field(
            name=f"🤵 Kasa (Krupiye) [Skor: {dealer_display_score}]",
            value=f"{format_hand(self.dealer_hand, hide_second=not finished)}",
            inline=False,
        )
        embed.add_field(
            name=f"👤 {self.ctx.author.display_name} [Skor: {player_score}]",
            value=f"{format_hand(self.player_hand)}",
            inline=False,
        )
        embed.add_field(
            name="💰 Masa Bahsi",
            value=f"`{self.bet} Kredi` *(Kazanç: {self.bet * 2} Kredi)*",
            inline=True,
        )
        embed.add_field(
            name="📌 Durum",
            value=f"*{status_message}*",
            inline=True,
        )

        footer_text = (
            "Kart çekmek için '🃏 Kart Çek', elinizi korumak için '🛑 Bekle' butonuna tıklayınız."
            if not finished
            else "Oyun tamamlandı."
        )
        embed.set_footer(text=footer_text)
        return embed, file

    @discord.ui.button(label="Kart Çek", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        async with self.state_lock:
            if self.finished:
                return

            self.player_hand.append(self.deck.pop())
            player_score = score_hand(self.player_hand)

            if player_score > 21:
                self.finished = True
                for child in self.children:
                    child.disabled = True

                embed, file = self.build_embed(
                    finished=True,
                    status_message="💥 Eliniz 21'i aştı! Bahis kasaya kaldı.",
                    color=discord.Color.from_rgb(139, 0, 0),
                    is_win=False,
                )
                await interaction.response.edit_message(embed=embed, file=file, view=self)
                self.stop()
            elif player_score == 21:
                await self.execute_stand(interaction)
            else:
                embed, file = self.build_embed(
                    finished=False,
                    status_message=f"Kart çekildi ({self.player_hand[-1][0]} {self.player_hand[-1][1]}). Sıra sizde!",
                )
                await interaction.response.edit_message(embed=embed, file=file, view=self)

    @discord.ui.button(label="Bekle", style=discord.ButtonStyle.danger, emoji="🛑")
    async def stand(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        async with self.state_lock:
            if self.finished:
                return
            await self.execute_stand(interaction)

    async def execute_stand(self, interaction: discord.Interaction) -> None:
        self.finished = True
        for child in self.children:
            child.disabled = True

        while score_hand(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        player_score = score_hand(self.player_hand)
        dealer_score = score_hand(self.dealer_hand)

        if dealer_score > 21:
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet * 2)
            eco = await self.cog.bot.db.get_economy(self.ctx.guild.id, self.ctx.author.id)
            status = f"🎉 Kasa 21'i aştı ({dealer_score})! Kazandınız: +{self.bet * 2} Kredi (Bakiye: {eco['bakiye']})"
            color = discord.Color.from_rgb(212, 175, 55)
            is_win = True
        elif player_score > dealer_score:
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet * 2)
            eco = await self.cog.bot.db.get_economy(self.ctx.guild.id, self.ctx.author.id)
            status = f"🎉 Tebrikler! Kasayı yendiniz! Kazandınız: +{self.bet * 2} Kredi (Bakiye: {eco['bakiye']})"
            color = discord.Color.from_rgb(212, 175, 55)
            is_win = True
        elif player_score == dealer_score:
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet)
            status = f"🤝 Berabere (Push)! Bahsiniz ({self.bet} Kredi) iade edildi."
            color = discord.Color.from_rgb(160, 160, 160)
            is_win = None
        else:
            status = f"😞 Kasa kazandı ({dealer_score} vs {player_score}). Bahis kaybedildi."
            color = discord.Color.from_rgb(139, 0, 0)
            is_win = False

        embed, file = self.build_embed(finished=True, status_message=status, color=color, is_win=is_win)
        await interaction.response.edit_message(embed=embed, file=file, view=self)
        self.stop()

    async def on_timeout(self) -> None:
        async with self.state_lock:
            if self.finished:
                return
            self.finished = True
            for child in self.children:
                child.disabled = True
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet)
            embed, file = self.build_embed(finished=True, status_message="⏳ Zaman aşımı! Bahis iade edildi.", is_win=None)
            await self.ctx.interaction.edit_original_response(embed=embed, file=file, view=self)


class Ekonomi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def balance(self, guild_id: int, user_id: int) -> int:
        return int((await self.bot.db.get_economy(guild_id, user_id))["bakiye"])

    @discord.slash_command(name="maas", description="Periyodik maaş ödemenizi almanızı sağlar.")
    async def maaş(self, ctx: discord.ApplicationContext):
        if not await require_channel(ctx, "game_channel"):
            return
        ok, balance, last = await self.bot.db.claim_salary(ctx.guild.id, ctx.author.id, time.time())
        if not ok:
            remaining = max(0, int(6 * 3600 - (time.time() - last)))
            return await ctx.respond(
                f"⏳ Maaş ödemesi için {remaining // 3600} saat {(remaining % 3600) // 60} dakika beklemeniz gerekmektedir."
            )
        await ctx.respond(f"💵 Maaş ödemesi hesabınıza yatırıldı! Güncel bakiyeniz: **{balance} kredi**.")

    @discord.slash_command(name="bakiye", description="Güncel kredi bakiyenizi görüntüler.")
    async def bakiye(self, ctx: discord.ApplicationContext):
        if await require_channel(ctx, "game_channel"):
            bal = await self.balance(ctx.guild.id, ctx.author.id)
            embed = discord.Embed(
                title="💳 Cüzdan Bakiyesi",
                description=f"Sayın {ctx.author.mention},\nMevcut bakiyeniz: **{bal} Kredi**",
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Maaş almak için: /maas • Kasa açmak için: /buycase")
            await ctx.respond(embed=embed)

    @discord.slash_command(name="blackjack", description="Casino atmosferinde gerçekçi blackjack (21) oynar.")
    async def blackjack(self, ctx: discord.ApplicationContext, bahis: int):
        if not await require_channel(ctx, "game_channel"):
            return
        if bahis <= 0:
            return await ctx.respond("❌ Bahis tutarı en az 1 kredi olmalıdır.", ephemeral=True)

        if not await self.bot.db.try_withdraw(ctx.guild.id, ctx.author.id, bahis):
            return await ctx.respond("❌ Bu bahis için yeterli bakiyeniz bulunmamaktadır.", ephemeral=True)

        view = BlackjackView(self, ctx, bahis)
        embed, file = view.build_embed(finished=False, status_message="Oyun başladı! Hamlenizi seçiniz.")
        await ctx.respond(embed=embed, file=file, view=view)

    @discord.slash_command(name="slot", description="Gerçekçi ve heyecanlı animasyonlu slot makinesi oynar.")
    async def slot(self, ctx: discord.ApplicationContext, bahis: int):
        if not await require_channel(ctx, "game_channel"):
            return
        if bahis <= 0:
            return await ctx.respond("❌ Bahis tutarı en az 1 kredi olmalıdır.", ephemeral=True)

        if not await self.bot.db.try_withdraw(ctx.guild.id, ctx.author.id, bahis):
            return await ctx.respond("❌ Bu bahis için yeterli bakiyeniz bulunmamaktadır.", ephemeral=True)

        symbols = ["🍒", "🍋", "🍉", "🔔", "💎", "7️⃣"]
        weights = [35, 25, 20, 10, 7, 3]

        final_reels = random.choices(symbols, weights=weights, k=3)

        # Frame 1: All spinning
        file1 = render_slot_machine(["?", "?", "?"], status="Makaralar Hızla Dönüyor...", bet=bahis, win=0, frame=1)
        embed = discord.Embed(
            title="🎰 Vegas Slot Makinesi",
            description=(
                f"### `[ ❓ | ❓ | ❓ ]`\n"
                f"*Makaralar hızla dönüyor...*\n"
                f"💰 **Bahis:** `{bahis} Kredi`"
            ),
            color=discord.Color.gold(),
        )
        embed.set_image(url="attachment://slot_1.png")
        embed.set_footer(text="Şansınız bol olsun!")
        await ctx.respond(embed=embed, file=file1)

        await asyncio.sleep(0.7)

        # Frame 2: First reel stops
        file2 = render_slot_machine([final_reels[0], "?", "?"], status="1. Makara Durdu!", bet=bahis, win=0, frame=2)
        embed.description = (
            f"### `[ {final_reels[0]} | ❓ | ❓ ]`\n"
            f"*Birinci makara durdu!*\n"
            f"💰 **Bahis:** `{bahis} Kredi`"
        )
        embed.set_image(url="attachment://slot_2.png")
        await ctx.interaction.edit_original_response(embed=embed, file=file2)

        await asyncio.sleep(0.7)

        # Frame 3: Second reel stops
        file3 = render_slot_machine([final_reels[0], final_reels[1], "?"], status="2. Makara Durdu!", bet=bahis, win=0, frame=3)
        embed.description = (
            f"### `[ {final_reels[0]} | {final_reels[1]} | ❓ ]`\n"
            f"*İkinci makara durdu!*\n"
            f"💰 **Bahis:** `{bahis} Kredi`"
        )
        embed.set_image(url="attachment://slot_3.png")
        await ctx.interaction.edit_original_response(embed=embed, file=file3)

        await asyncio.sleep(0.7)

        # Frame 4: Final result
        r1, r2, r3 = final_reels
        if r1 == r2 == r3:
            if r1 == "7️⃣":
                multiplier = 25
                title = "🚨 BÜYÜK JACKPOT: ÜÇLÜ YEDİ! 🚨"
                color = discord.Color.from_rgb(255, 215, 0)
            elif r1 == "💎":
                multiplier = 15
                title = "💎 ELMAS PATLAMASI: SÜPER KAZANÇ! 💎"
                color = discord.Color.from_rgb(0, 255, 255)
            elif r1 == "🔔":
                multiplier = 10
                title = "🔔 ALTIN ÇANLAR: BÜYÜK KAZANÇ! 🔔"
                color = discord.Color.gold()
            else:
                multiplier = 8
                title = f"🎉 MEYVE ŞÖLENİ ({r1}): KAZANDINIZ! 🎉"
                color = discord.Color.green()
        elif len(set(final_reels)) == 2:
            multiplier = 2
            title = "✨ İKİLİ EŞLEŞME: KAZANDINIZ! ✨"
            color = discord.Color.brand_green()
        else:
            multiplier = 0
            title = "💔 ŞANSINIZI TEKRAR DENEYİN"
            color = discord.Color.dark_red()

        winnings = int(bahis * multiplier)
        if winnings > 0:
            await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, winnings)

        eco = await self.bot.db.get_economy(ctx.guild.id, ctx.author.id)

        result_text = (
            f"### `[ {r1} | {r2} | {r3} ]`\n"
            f"{'🎉 **Tebrikler!**' if winnings > 0 else '😢 **Bu sefer kazanamadınız.**'}\n\n"
            f"💵 **Ödül:** `+{winnings} Kredi` *(x{multiplier})*\n"
            f"💳 **Güncel Bakiye:** `{eco['bakiye']} Kredi`"
        )
        embed.title = f"🎰 {title}"
        embed.description = result_text
        embed.color = color
        embed.set_footer(text="Tekrar oynamak için: /slot <bahis>")

        file4 = render_slot_machine(
            final_reels,
            status=f"{'KAZANDINIZ! +' + str(winnings) if winnings > 0 else 'KAYBETTINIZ.'}",
            bet=bahis,
            win=winnings,
            is_win=(winnings > 0),
            frame=4,
        )
        embed.set_image(url="attachment://slot_4.png")
        await ctx.interaction.edit_original_response(embed=embed, file=file4)


def setup(bot):
    return add_cog(bot, Ekonomi(bot))
