from __future__ import annotations

import random
from typing import Any

import chess
import discord
from discord.ext import commands

from utils.channels import require_channel
from utils.discord_compat import add_cog


PIECES = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}


def render_board(board: chess.Board) -> str:
    rows = []
    for rank in range(7, -1, -1):
        cells = []
        for file in range(8):
            piece = board.piece_at(chess.square(file, rank))
            cells.append(PIECES[piece.symbol()] if piece else ("▫️" if (file + rank) % 2 else "▪️"))
        rows.append(f"{rank + 1} " + " ".join(cells))
    return "```\n" + "\n".join(rows) + "\n  a b c d e f g h\n```"


class MoveModal(discord.ui.Modal):
    def __init__(self, view: "ChessView"):
        super().__init__(title="Hamle Girişi")
        self.view = view
        self.move = discord.ui.InputText(
            label="Hamle",
            placeholder="Örneğin: e4, Nf3 veya e2e4",
            min_length=2,
            max_length=10,
        )
        self.add_item(self.move)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.view.play_move(interaction, str(self.move.value))


class ChessView(discord.ui.View):
    def __init__(self, cog: "Satranc", channel: discord.abc.Messageable, game: dict[str, Any]):
        super().__init__(timeout=1800)
        self.cog = cog
        self.channel = channel
        self.game = game
        self.lock = __import__("asyncio").Lock()
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user not in self.game["players"]:
            await interaction.response.send_message(
                "Bu satranç oyunu yalnızca oyunun oyuncuları tarafından kullanılabilir.",
                ephemeral=True,
            )
            return False
        if interaction.user != self.game["turn"]:
            await interaction.response.send_message("Şu anda hamle sırası sizde değildir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Hamle Yap", style=discord.ButtonStyle.primary, emoji="♟️")
    async def move_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(MoveModal(self))

    @discord.ui.button(label="Oyundan Ayrıl", style=discord.ButtonStyle.danger, emoji="🏳️")
    async def resign_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        winner = next(player for player in self.game["players"] if player != interaction.user)
        await interaction.response.defer()
        await self.cog.finish_game(self.channel, winner, "Oyunculardan biri oyundan ayrıldı.")

    async def play_move(self, interaction: discord.Interaction, notation: str) -> None:
        bot_turn = False
        async with self.lock:
            if self.finished:
                await interaction.response.send_message("Bu oyun zaten sona ermiştir.", ephemeral=True)
                return
            board: chess.Board = self.game["board"]
            try:
                move = chess.Move.from_uci(notation.strip())
                if move not in board.legal_moves:
                    move = board.parse_san(notation.strip())
            except (ValueError, chess.InvalidMoveError):
                await interaction.response.send_message(
                    "Geçersiz bir hamle girdiniz. SAN veya UCI formatında yasal bir hamle belirtiniz.",
                    ephemeral=True,
                )
                return
            board.push(move)
            self.game["turn"] = self.game["players"][1] if self.game["turn"] == self.game["players"][0] else self.game["players"][0]
            await interaction.response.defer()
            if board.is_game_over():
                winner = None if board.outcome().winner is None else (
                    self.game["players"][0] if board.outcome().winner == chess.WHITE else self.game["players"][1]
                )
                await self.cog.finish_game(self.channel, winner, "Oyun kurallara göre sona erdi.")
                return
            await self.cog.update_game_message(self.channel, self)
            bot_turn = self.game.get("bot_mode") and self.game["turn"] == self.cog.bot.user
        if bot_turn:
            await self.cog.bot_move(self)

    async def on_timeout(self) -> None:
        if not self.finished:
            await self.cog.finish_game(self.channel, None, "Oyun zaman aşımı nedeniyle sona erdi.")


class ChessInviteView(discord.ui.View):
    def __init__(self, cog: "Satranc", ctx: commands.Context, opponent: discord.Member, bet: int):
        super().__init__(timeout=120)
        self.cog, self.ctx, self.opponent, self.bet = cog, ctx, opponent, bet
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.opponent:
            await interaction.response.send_message(
                "Bu davet yalnızca davet edilen kullanıcı tarafından yanıtlanabilir.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Kabul Et", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.resolved:
            return
        self.resolved = True
        if self.cog.active_games.get(interaction.channel.id):
            await interaction.response.edit_message(content="Bu kanalda zaten devam eden bir oyun bulunmaktadır.", view=None)
            return
        if self.bet and (
            not await self.cog.bot.db.try_withdraw_pair(self.ctx.author.id, self.opponent.id, self.bet)
        ):
            await interaction.response.edit_message(content="Oyunculardan birinin bakiyesi bahis için yeterli değildir.", view=None)
            return
        game = {
            "board": chess.Board(),
            "players": [self.ctx.author, self.opponent],
            "turn": self.ctx.author,
            "bet": self.bet,
            "bot_mode": False,
        }
        self.cog.active_games[interaction.channel.id] = game
        await interaction.response.edit_message(content="Satranç oyunu başlatıldı.", view=None)
        await self.cog.update_game_message(interaction.channel, ChessView(self.cog, interaction.channel, game))

    @discord.ui.button(label="Reddet", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.resolved = True
        await interaction.response.edit_message(content="Satranç daveti reddedildi.", view=None)
        self.stop()


class Satranc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games: dict[int, dict[str, Any]] = {}

    async def update_game_message(self, channel, view: ChessView) -> None:
        game = view.game
        description = render_board(game["board"])
        description += f"\nSıra: {game['turn'].mention if hasattr(game['turn'], 'mention') else 'Bot'}"
        await channel.send(embed=discord.Embed(title="Satranç Oyunu", description=description), view=view)

    async def bot_move(self, view: ChessView) -> None:
        async with view.lock:
            if view.finished:
                return
            board: chess.Board = view.game["board"]
            legal_moves = list(board.legal_moves)
            if not legal_moves:
                return
            board.push(random.choice(legal_moves))
            view.game["turn"] = view.game["players"][0]
            await self.update_game_message(view.channel, view)

    async def finish_game(self, channel, winner, reason: str) -> None:
        game = self.active_games.pop(channel.id, None)
        if not game:
            return
        if winner is None and game["bet"]:
            await self.bot.db.add_balance(game["players"][0].id, game["bet"])
            if not game["bot_mode"]:
                await self.bot.db.add_balance(game["players"][1].id, game["bet"])
            result = "Oyun berabere tamamlandı; bahisler iade edildi."
        elif winner is None:
            result = "Oyun berabere tamamlandı."
        elif game["bet"]:
            await self.bot.db.add_balance(winner.id, game["bet"] * 2)
            result = f"{winner.mention} oyunu kazandı. Toplam ödül: {game['bet'] * 2} kredi."
        else:
            result = f"{winner.mention} oyunu kazandı."
        await channel.send(f"**Satranç sonucu:** {result}\n**Açıklama:** {reason}")

    @commands.slash_command(name="chess")
    async def chess(self, ctx: commands.Context, rakip: discord.Member | None = None, bahis: int = 0):
        if not await require_channel(ctx, "game_channel"):
            return
        if ctx.channel.id in self.active_games:
            await ctx.send("Bu kanalda hâlihazırda devam eden bir satranç oyunu bulunmaktadır.")
            return
        if bahis < 0:
            await ctx.send("Bahis tutarı sıfır veya daha büyük olmalıdır.")
            return
        if rakip is None:
            if bahis and not await self.bot.db.try_withdraw(ctx.author.id, bahis):
                await ctx.send("Bakiyeniz belirtilen bahis için yeterli değildir.")
                return
            game = {
                "board": chess.Board(), "players": [ctx.author, self.bot.user],
                "turn": ctx.author, "bet": bahis, "bot_mode": True,
            }
            self.active_games[ctx.channel.id] = game
            await ctx.send("Bota karşı satranç oyunu başlatıldı.")
            await self.update_game_message(ctx.channel, ChessView(self, ctx.channel, game))
            return
        if rakip == ctx.author or rakip.bot:
            await ctx.send("Geçerli bir rakip kullanıcı belirtiniz.")
            return
        if bahis and (await self.bot.db.get_economy(ctx.author.id))["bakiye"] < bahis:
            await ctx.send("Bakiyeniz belirtilen bahis için yeterli değildir.")
            return
        embed = discord.Embed(
            title="Satranç Daveti",
            description=f"{ctx.author.mention}, {rakip.mention} kullanıcısını {bahis} kredi bahisli bir oyuna davet etti.",
        )
        await ctx.send(content=rakip.mention, embed=embed, view=ChessInviteView(self, ctx, rakip, bahis))

    @commands.slash_command(name="pes")
    async def resign(self, ctx: commands.Context):
        game = self.active_games.get(ctx.channel.id)
        if not game:
            await ctx.send("Bu kanalda devam eden bir satranç oyunu bulunmamaktadır.")
            return
        if ctx.author not in game["players"]:
            await ctx.send("Bu oyunun oyuncusu değilsiniz.")
            return
        winner = next(player for player in game["players"] if player != ctx.author)
        await self.finish_game(ctx.channel, winner, "Oyunculardan biri oyundan ayrıldı.")


def setup(bot):
    return add_cog(bot, Satranc(bot))
