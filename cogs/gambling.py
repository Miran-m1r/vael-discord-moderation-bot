from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import discord
from discord.ext import commands

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


class BlackjackView(discord.ui.View):
    def __init__(self, cog: "Ekonomi", ctx: discord.ApplicationContext, bet: int):
        super().__init__(timeout=90)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.state_lock = asyncio.Lock()
        self.finished = False

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
    ) -> discord.Embed:
        player_score = score_hand(self.player_hand)
        dealer_score = score_hand(self.dealer_hand) if finished else score_hand([self.dealer_hand[0]])
        dealer_display_score = f"{dealer_score}" if finished else f"{dealer_score} + ?"

        if color is None:
            color = discord.Color.from_rgb(0, 100, 0)  # Casino Green

        embed = discord.Embed(
            title="♠️ Casino Blackjack Masası ♦️",
            color=color,
        )
        embed.set_thumbnail(url="https://media.giphy.com/media/3o7TKtnuHOHHUjR38Y/giphy.gif")

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
        return embed

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

                embed = self.build_embed(
                    finished=True,
                    status_message="💥 Eliniz 21'i aştı! Bahis kasaya kaldı.",
                    color=discord.Color.from_rgb(139, 0, 0),  # Dark Red
                )
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
            elif player_score == 21:
                # Automatic stand on 21
                await self.execute_stand(interaction)
            else:
                embed = self.build_embed(
                    finished=False,
                    status_message=f"Kart çekildi ({self.player_hand[-1][0]} {self.player_hand[-1][1]}). Sıra sizde!",
                )
                await interaction.response.edit_message(embed=embed, view=self)

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

        # Dealer draws until at least 17
        while score_hand(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        player_score = score_hand(self.player_hand)
        dealer_score = score_hand(self.dealer_hand)

        if dealer_score > 21:
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet * 2)
            eco = await self.cog.bot.db.get_economy(self.ctx.guild.id, self.ctx.author.id)
            status = f"🎉 Kasa 21'i aştı ({dealer_score})! Kazandınız: +{self.bet * 2} Kredi (Bakiye: {eco['bakiye']})"
            color = discord.Color.from_rgb(212, 175, 55)  # Gold
        elif player_score > dealer_score:
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet * 2)
            eco = await self.cog.bot.db.get_economy(self.ctx.guild.id, self.ctx.author.id)
            status = f"🎉 Tebrikler! Kasayı yendiniz! Kazandınız: +{self.bet * 2} Kredi (Bakiye: {eco['bakiye']})"
            color = discord.Color.from_rgb(212, 175, 55)  # Gold
        elif player_score == dealer_score:
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet)
            status = f"🤝 Berabere (Push)! Bahsiniz ({self.bet} Kredi) iade edildi."
            color = discord.Color.from_rgb(160, 160, 160)  # Silver/Grey
        else:
            status = f"😞 Kasa kazandı ({dealer_score} vs {player_score}). Bahis kaybedildi."
            color = discord.Color.from_rgb(139, 0, 0)  # Dark Red

        embed = self.build_embed(finished=True, status_message=status, color=color)
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self) -> None:
        async with self.state_lock:
            if self.finished:
                return
            self.finished = True
            for child in self.children:
                child.disabled = True
            await self.cog.bot.db.add_balance(self.ctx.guild.id, self.ctx.author.id, self.bet)


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
        embed = view.build_embed(finished=False, status_message="Oyun başladı! Hamlenizi seçiniz.")
        await ctx.respond(embed=embed, view=view)

    @discord.slash_command(name="slot", description="Gerçekçi ve heyecanlı animasyonlu slot makinesi oynar.")
    async def slot(self, ctx: discord.ApplicationContext, bahis: int):
        if not await require_channel(ctx, "game_channel"):
            return
        if bahis <= 0:
            return await ctx.respond("❌ Bahis tutarı en az 1 kredi olmalıdır.", ephemeral=True)

        if not await self.bot.db.try_withdraw(ctx.guild.id, ctx.author.id, bahis):
            return await ctx.respond("❌ Bu bahis için yeterli bakiyeniz bulunmamaktadır.", ephemeral=True)

        symbols = ["🍒", "🍋", "🍉", "🔔", "💎", "7️⃣"]
        weights = [35, 25, 20, 10, 7, 3]  # Authentic slot probability weighting

        final_reels = random.choices(symbols, weights=weights, k=3)

        # Frame 1: All spinning
        embed = discord.Embed(
            title="🎰 Vegas Slot Makinesi",
            description=(
                f"### `[ ❓ | ❓ | ❓ ]`\n"
                f"*Makaralar hızla dönüyor...*\n"
                f"💰 **Bahis:** `{bahis} Kredi`"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Şansınız bol olsun!")
        await ctx.respond(embed=embed)

        await asyncio.sleep(0.7)

        # Frame 2: First reel stops
        embed.description = (
            f"### `[ {final_reels[0]} | ❓ | ❓ ]`\n"
            f"*Birinci makara durdu!*\n"
            f"💰 **Bahis:** `{bahis} Kredi`"
        )
        await ctx.interaction.edit_original_response(embed=embed)

        await asyncio.sleep(0.7)

        # Frame 3: Second reel stops
        embed.description = (
            f"### `[ {final_reels[0]} | {final_reels[1]} | ❓ ]`\n"
            f"*İkinci makara durdu!*\n"
            f"💰 **Bahis:** `{bahis} Kredi`"
        )
        await ctx.interaction.edit_original_response(embed=embed)

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
        await ctx.interaction.edit_original_response(embed=embed)


def setup(bot):
    return add_cog(bot, Ekonomi(bot))
