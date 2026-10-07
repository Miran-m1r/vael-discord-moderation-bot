import asyncio
import random
import time

import discord
from discord.ext import commands

from utils.channels import require_channel
from utils.discord_compat import add_cog


class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bet):
        super().__init__(timeout=60)
        self.cog, self.ctx, self.bet = cog, ctx, bet
        self.state_lock = asyncio.Lock()
        self.finished = False
        self.deck = list("23456789") * 4 + ["10", "J", "Q", "K", "A"] * 4
        random.shuffle(self.deck)
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]

    async def interaction_check(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Bu oyun yalnızca ilgili kullanıcı tarafından kullanılabilir.", ephemeral=True)
            return False
        return True

    @staticmethod
    def score(hand):
        score = sum(10 if card in "JQK" else 11 if card == "A" else int(card) for card in hand)
        for _ in range(hand.count("A")):
            if score <= 21:
                break
            score -= 10
        return score

    def embed(self, finished=False):
        result = discord.Embed(title="🎰 Blackjack Oyunu", color=discord.Color.gold())
        result.add_field(name=f"{self.ctx.author.name} [{self.score(self.player)}]", value=" | ".join(self.player))
        dealer = " | ".join(self.dealer) if finished else f"{self.dealer[0]} | ❓"
        result.add_field(name=f"Kasa [{self.score(self.dealer) if finished else '?'}]", value=dealer)
        return result

    @discord.ui.button(label="Kart Çek", style=discord.ButtonStyle.primary)
    async def hit(self, interaction, button):
        async with self.state_lock:
            if self.finished:
                return
            self.player.append(self.deck.pop())
            if self.score(self.player) > 21:
                self.finished = True
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(content="El değeriniz 21'i aştı. Bahsiniz kaybedildi.", embed=self.embed(True), view=self)
                self.stop()
            else:
                await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Bekle", style=discord.ButtonStyle.danger)
    async def stand(self, interaction, button):
        async with self.state_lock:
            if self.finished:
                return
            self.finished = True
            for child in self.children:
                child.disabled = True
            while self.score(self.dealer) < 17:
                self.dealer.append(self.deck.pop())
            player, dealer = self.score(self.player), self.score(self.dealer)
            if dealer > 21 or player > dealer:
                await self.cog.bot.db.add_balance(self.ctx.author.id, self.bet * 2)
                text = f"Tebrikler, oyunu kazandınız. Güncel bakiyeniz: {(await self.cog.bot.db.get_economy(self.ctx.author.id))['bakiye']} kredi."
            elif player == dealer:
                await self.cog.bot.db.add_balance(self.ctx.author.id, self.bet)
                text = "Oyun berabere tamamlandı. Bahsiniz iade edildi."
            else:
                text = "Oyun sonucunda kasa kazandı."
            await interaction.response.edit_message(content=text, embed=self.embed(True), view=self)
            self.stop()

    async def on_timeout(self):
        async with self.state_lock:
            if self.finished:
                return
            self.finished = True
            await self.cog.bot.db.add_balance(self.ctx.author.id, self.bet)


class Ekonomi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def balance(self, user_id):
        return int((await self.bot.db.get_economy(user_id))["bakiye"])

    @commands.command()
    async def maaş(self, ctx):
        if not await require_channel(ctx, "game_channel"):
            return
        ok, balance, last = await self.bot.db.claim_salary(ctx.author.id, time.time())
        if not ok:
            remaining = max(0, int(6 * 3600 - (time.time() - last)))
            return await ctx.send(f"Maaş ödemesi için {remaining // 3600} saat {(remaining % 3600) // 60} dakika beklemeniz gerekmektedir.")
        await ctx.send(f"Maaş ödemesi hesabınıza yatırıldı. Güncel bakiyeniz: **{balance} kredi**.")

    @commands.command(aliases=["cüzdan", "para"])
    async def bakiye(self, ctx):
        if await require_channel(ctx, "game_channel"):
            await ctx.send(f"💳 Güncel bakiyeniz: **{await self.balance(ctx.author.id)} kredi**.")

    @commands.command(aliases=["bj"])
    async def blackjack(self, ctx, bahis: int):
        if not await require_channel(ctx, "game_channel") or bahis <= 0:
            return
        if not await self.bot.db.try_withdraw(ctx.author.id, bahis):
            return await ctx.send("Bu bahis için yeterli bakiyeniz bulunmamaktadır.")
        view = BlackjackView(self, ctx, bahis)
        await ctx.send(embed=view.embed(), view=view)

    @commands.command(aliases=["slots", "kumar"])
    async def slot(self, ctx, bahis: int):
        if not await require_channel(ctx, "game_channel") or bahis <= 0:
            return
        if not await self.bot.db.try_withdraw(ctx.author.id, bahis):
            return await ctx.send("Bu bahis için yeterli bakiyeniz bulunmamaktadır.")
        await asyncio.sleep(1)
        reels = [random.choice(["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]) for _ in range(3)]
        multiplier = 10 if len(set(reels)) == 1 else 1.5 if len(set(reels)) == 2 else 0
        winnings = int(bahis * multiplier)
        if winnings:
            await self.bot.db.add_balance(ctx.author.id, winnings)
        await ctx.send(f"🎰 `[ {' | '.join(reels)} ]` Ödülünüz: **{winnings} kredi**.")


def setup(bot):
    return add_cog(bot, Ekonomi(bot))
