import asyncio
import io
import os
import random
from typing import Any

# Ensure Homebrew and standard library paths are available for Cairo on macOS/Linux
for _p in ("/opt/homebrew/lib", "/usr/local/lib", "/usr/lib"):
    if os.path.exists(_p) and _p not in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", ""):
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = _p + ":" + os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")

import cairosvg
import chess
import chess.svg
import discord
from discord.ext import commands

from utils.channels import require_channel
from utils.discord_compat import add_cog

PIECE_NAMES_TR = {
    chess.PAWN: "Piyon",
    chess.KNIGHT: "At",
    chess.BISHOP: "Fil",
    chess.ROOK: "Kale",
    chess.QUEEN: "Vezir",
    chess.KING: "Şah",
}

PIECE_SYMBOLS = {
    (chess.PAWN, chess.WHITE): "♙",
    (chess.KNIGHT, chess.WHITE): "♘",
    (chess.BISHOP, chess.WHITE): "♗",
    (chess.ROOK, chess.WHITE): "♖",
    (chess.QUEEN, chess.WHITE): "♕",
    (chess.KING, chess.WHITE): "♔",
    (chess.PAWN, chess.BLACK): "♟",
    (chess.KNIGHT, chess.BLACK): "♞",
    (chess.BISHOP, chess.BLACK): "♝",
    (chess.ROOK, chess.BLACK): "♜",
    (chess.QUEEN, chess.BLACK): "♛",
    (chess.KING, chess.BLACK): "♚",
}


def render_board_file(board: chess.Board) -> discord.File:
    lastmove = board.peek() if board.move_stack else None
    check = board.king(board.turn) if board.is_check() else None
    svg_data = chess.svg.board(
        board=board,
        lastmove=lastmove,
        check=check,
        size=520,
        colors={
            "square light": "#f0d9b5",
            "square dark": "#b58863",
            "margin": "#262421",
            "coord": "#c4a482",
        },
    )
    png_bytes = cairosvg.svg2png(bytestring=svg_data.encode("utf-8"))
    return discord.File(io.BytesIO(png_bytes), filename="board.png")


class PieceSelect(discord.ui.Select):
    def __init__(self, chess_view: "ChessView", options: list[discord.SelectOption]):
        super().__init__(
            placeholder="♟️ Oynamak istediğiniz taşı seçin...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )
        self.chess_view = chess_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.chess_view.on_piece_selected(interaction, int(self.values[0]))


class DestinationSelect(discord.ui.Select):
    def __init__(self, chess_view: "ChessView", options: list[discord.SelectOption]):
        super().__init__(
            placeholder="🎯 Hedef kareyi seçin...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )
        self.chess_view = chess_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.chess_view.on_destination_selected(interaction, int(self.values[0]))


class ChessView(discord.ui.View):
    def __init__(self, cog: "Satranc", channel: discord.abc.Messageable, game: dict[str, Any]):
        super().__init__(timeout=1800)
        self.cog = cog
        self.channel = channel
        self.game = game
        self.lock = asyncio.Lock()
        self.finished = False
        self.selected_from_square: int | None = None
        self.rebuild_components()

    def rebuild_components(self) -> None:
        self.clear_items()
        if self.finished:
            return

        board: chess.Board = self.game["board"]
        legal_froms = sorted(list({move.from_square for move in board.legal_moves}))
        if not legal_froms:
            return

        piece_options: list[discord.SelectOption] = []
        for sq in legal_froms:
            piece = board.piece_at(sq)
            if not piece:
                continue
            sq_name = chess.square_name(sq)
            piece_name = PIECE_NAMES_TR.get(piece.piece_type, "Taş")
            symbol = PIECE_SYMBOLS.get((piece.piece_type, piece.color), "♟")
            is_default = (sq == self.selected_from_square)
            piece_options.append(
                discord.SelectOption(
                    label=f"{symbol} {piece_name} ({sq_name})",
                    value=str(sq),
                    default=is_default,
                    description=f"{sq_name.upper()} karesindeki {piece_name}",
                )
            )

        if piece_options:
            self.add_item(PieceSelect(self, piece_options[:25]))

        if self.selected_from_square is not None:
            dest_moves = [m for m in board.legal_moves if m.from_square == self.selected_from_square]
            dest_options: list[discord.SelectOption] = []
            for m in dest_moves:
                to_sq = m.to_square
                to_name = chess.square_name(to_sq)
                is_capture = board.is_capture(m)
                is_check = board.gives_check(m)
                emoji = "⚔️" if is_capture else "🎯"
                desc_parts = []
                if is_capture:
                    desc_parts.append("Taş Alma")
                if is_check:
                    desc_parts.append("Şah!")
                if m.promotion:
                    desc_parts.append("Vezir Terfisi")
                desc = ", ".join(desc_parts) if desc_parts else "Güvenli Hamle"
                dest_options.append(
                    discord.SelectOption(
                        label=f"{to_name.upper()} ({to_name})",
                        value=str(to_sq),
                        emoji=emoji,
                        description=desc[:50],
                    )
                )

            if dest_options:
                self.add_item(DestinationSelect(self, dest_options[:25]))

            cancel_btn = discord.ui.Button(
                label="Seçimi İptal Et",
                style=discord.ButtonStyle.secondary,
                emoji="✖️",
                row=2,
            )
            cancel_btn.callback = self.on_cancel_selected
            self.add_item(cancel_btn)

        resign_btn = discord.ui.Button(
            label="Oyundan Ayrıl",
            style=discord.ButtonStyle.danger,
            emoji="🏳️",
            row=2,
        )
        resign_btn.callback = self.on_resign_clicked
        self.add_item(resign_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user not in self.game["players"]:
            await interaction.response.send_message(
                "Bu satranç oyunu yalnızca oyundaki oyuncular tarafından kontrol edilebilir.",
                ephemeral=True,
            )
            return False

        # Allow resign button click even if not your turn
        custom_id = getattr(interaction.data, "get", lambda _: "")("custom_id")
        if interaction.user != self.game["turn"]:
            # Check if this interaction is resign
            if interaction.data and interaction.data.get("component_type") == 2:
                # Button click
                return True
            await interaction.response.send_message("Şu anda hamle sırası sizde değildir.", ephemeral=True)
            return False
        return True

    async def on_piece_selected(self, interaction: discord.Interaction, from_sq: int) -> None:
        async with self.lock:
            if self.finished:
                await interaction.response.send_message("Bu oyun sona ermiştir.", ephemeral=True)
                return
            self.selected_from_square = from_sq
            self.rebuild_components()
            await interaction.response.edit_message(view=self)

    async def on_cancel_selected(self, interaction: discord.Interaction) -> None:
        async with self.lock:
            if self.finished:
                return
            self.selected_from_square = None
            self.rebuild_components()
            await interaction.response.edit_message(view=self)

    async def on_resign_clicked(self, interaction: discord.Interaction) -> None:
        if interaction.user not in self.game["players"]:
            await interaction.response.send_message("Bu oyunun oyuncusu değilsiniz.", ephemeral=True)
            return
        winner = next(p for p in self.game["players"] if p != interaction.user)
        self.finished = True
        self.clear_items()
        await interaction.response.defer()
        await self.cog.finish_game(self.channel, winner, f"{interaction.user.display_name} oyundan çekildi.")

    async def on_destination_selected(self, interaction: discord.Interaction, to_sq: int) -> None:
        async with self.lock:
            if self.finished or self.selected_from_square is None:
                await interaction.response.send_message("Lütfen tekrar bir taş seçiniz.", ephemeral=True)
                return

            board: chess.Board = self.game["board"]
            move = chess.Move(self.selected_from_square, to_sq)
            if chess.Move(self.selected_from_square, to_sq, promotion=chess.QUEEN) in board.legal_moves:
                move = chess.Move(self.selected_from_square, to_sq, promotion=chess.QUEEN)

            if move not in board.legal_moves:
                await interaction.response.send_message("Geçersiz hamle! Lütfen tekrar deneyiniz.", ephemeral=True)
                return

            san_str = board.san(move)
            board.push(move)
            self.game["last_move_text"] = f"{interaction.user.display_name}: {san_str}"
            self.selected_from_square = None

            # Switch turn
            self.game["turn"] = (
                self.game["players"][1]
                if self.game["turn"] == self.game["players"][0]
                else self.game["players"][0]
            )

            # Check game termination
            if board.is_game_over():
                self.finished = True
                self.clear_items()
                outcome = board.outcome()
                winner = None
                if outcome and outcome.winner is not None:
                    winner = (
                        self.game["players"][0]
                        if outcome.winner == chess.WHITE
                        else self.game["players"][1]
                    )
                await interaction.response.defer()
                await self.cog.finish_game(self.channel, winner, "Oyun kurallara göre tamamlandı.")
                return

            # Bot mode logic
            if self.game.get("bot_mode") and self.game["turn"] == self.cog.bot.user:
                bot_moves = list(board.legal_moves)
                if bot_moves:
                    bot_move = random.choice(bot_moves)
                    bot_san = board.san(bot_move)
                    board.push(bot_move)
                    self.game["last_move_text"] = f"Bot: {bot_san}"
                    self.game["turn"] = self.game["players"][0]
                    if board.is_game_over():
                        self.finished = True
                        self.clear_items()
                        outcome = board.outcome()
                        winner = None
                        if outcome and outcome.winner is not None:
                            winner = (
                                self.game["players"][0]
                                if outcome.winner == chess.WHITE
                                else self.game["players"][1]
                            )
                        await interaction.response.defer()
                        await self.cog.finish_game(self.channel, winner, "Bot hamlesi sonrası oyun bitti.")
                        return

            self.rebuild_components()
            file = render_board_file(board)
            embed = self.cog.build_game_embed(self.game)
            await interaction.response.edit_message(embed=embed, file=file, view=self)

    async def on_timeout(self) -> None:
        if not self.finished:
            self.finished = True
            await self.cog.finish_game(self.channel, None, "Oyun zaman aşımı nedeniyle sona erdi.")


class ChessInviteView(discord.ui.View):
    def __init__(self, cog: "Satranc", ctx: discord.ApplicationContext, opponent: discord.Member, bet: int):
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

    @discord.ui.button(label="Kabul Et", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if self.resolved:
            return
        self.resolved = True
        if self.cog.active_games.get(interaction.channel.id):
            await interaction.response.edit_message(
                content="Bu kanalda zaten devam eden bir satranç oyunu bulunmaktadır.", view=None
            )
            return

        guild_id = interaction.guild.id if interaction.guild else self.ctx.guild.id
        if self.bet and (
            not await self.cog.bot.db.try_withdraw_pair(
                guild_id, self.ctx.author.id, self.opponent.id, self.bet
            )
        ):
            await interaction.response.edit_message(
                content="Oyunculardan birinin bakiyesi belirtilen bahis için yeterli değildir.", view=None
            )
            return

        game = {
            "board": chess.Board(),
            "players": [self.ctx.author, self.opponent],
            "turn": self.ctx.author,
            "bet": self.bet,
            "bot_mode": False,
            "last_move_text": "Oyun başladı",
        }
        self.cog.active_games[interaction.channel.id] = game
        await interaction.response.edit_message(content="🎮 Satranç maçı başlatıldı!", view=None)

        view = ChessView(self.cog, interaction.channel, game)
        file = render_board_file(game["board"])
        embed = self.cog.build_game_embed(game)
        await interaction.channel.send(embed=embed, file=file, view=view)

    @discord.ui.button(label="Reddet", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self.resolved = True
        await interaction.response.edit_message(content="Satranç daveti reddedildi.", view=None)
        self.stop()


class Satranc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games: dict[int, dict[str, Any]] = {}

    def build_game_embed(self, game: dict[str, Any]) -> discord.Embed:
        board: chess.Board = game["board"]
        p1 = game["players"][0]
        p2 = game["players"][1]
        p2_mention = p2.mention if hasattr(p2, "mention") else "🤖 MekanBot"

        turn_user = game["turn"]
        turn_str = turn_user.mention if hasattr(turn_user, "mention") else "🤖 MekanBot"

        if board.is_checkmate():
            status_text = "💥 **ŞAH-MAT!** Oyun tamamlandı."
            color = discord.Color.red()
        elif board.is_check():
            status_text = "⚠️ **DİKKAT: ŞAH ÇEKİLDİ!**"
            color = discord.Color.orange()
        elif board.is_stalemate() or board.is_insufficient_material():
            status_text = "🤝 **PAT / YETERSİZ MATERYAL (Berabere)**"
            color = discord.Color.greyple()
        else:
            status_text = "🟢 **Oyun Devam Ediyor**"
            color = discord.Color.gold() if game["bet"] > 0 else discord.Color.blurple()

        embed = discord.Embed(title="♟️ Satranç Karşılaşması", color=color)
        embed.description = (
            f"⚪ **Beyaz:** {p1.mention}\n"
            f"⚫ **Siyah:** {p2_mention}\n"
            f"💰 **Bahis:** `{game['bet']} Kredi`\n"
            f"🎯 **Sıra:** {turn_str}\n"
            f"📌 **Durum:** {status_text}\n"
            f"📝 **Son Hamle:** `{game.get('last_move_text', 'Başlangıç')}`"
        )
        embed.set_image(url="attachment://board.png")
        embed.set_footer(text="Aşağıdaki menülerden önce taşınızı, ardından hedef kareyi seçiniz.")
        return embed

    async def finish_game(self, channel, winner, reason: str) -> None:
        game = self.active_games.pop(channel.id, None)
        if not game:
            return
        guild_id = channel.guild.id
        if winner is None and game["bet"]:
            await self.bot.db.add_balance(guild_id, game["players"][0].id, game["bet"])
            if not game["bot_mode"]:
                await self.bot.db.add_balance(guild_id, game["players"][1].id, game["bet"])
            result = "Oyun berabere tamamlandı; bahis tutarları iade edildi."
        elif winner is None:
            result = "Oyun berabere tamamlandı."
        elif game["bet"]:
            await self.bot.db.add_balance(guild_id, winner.id, game["bet"] * 2)
            result = f"{winner.mention} oyunu kazandı! Ödül: **{game['bet'] * 2} kredi**."
        else:
            result = f"{winner.mention} oyunu kazandı!"

        file = render_board_file(game["board"])
        embed = discord.Embed(
            title="🏁 Satranç Karşılaşması Sona Erdi",
            description=f"**Sonuç:** {result}\n**Detay:** {reason}",
            color=discord.Color.green() if winner else discord.Color.greyple(),
        )
        embed.set_image(url="attachment://board.png")
        await channel.send(embed=embed, file=file)

    @discord.slash_command(
        name="chess",
        description="Bota veya başka bir kullanıcıya karşı satranç oyunu başlatır.",
    )
    async def chess(
        self,
        ctx: discord.ApplicationContext,
        rakip: discord.Member | None = None,
        bahis: int = 0,
    ):
        if not await require_channel(ctx, "game_channel"):
            return
        if ctx.channel.id in self.active_games:
            await ctx.respond("Bu kanalda hâlihazırda devam eden bir satranç oyunu bulunmaktadır.")
            return
        if bahis < 0:
            await ctx.respond("Bahis tutarı sıfır veya daha büyük olmalıdır.")
            return

        if rakip is None:
            if bahis and not await self.bot.db.try_withdraw(ctx.guild.id, ctx.author.id, bahis):
                await ctx.respond("Bakiyeniz belirtilen bahis için yeterli değildir.")
                return
            game = {
                "board": chess.Board(),
                "players": [ctx.author, self.bot.user],
                "turn": ctx.author,
                "bet": bahis,
                "bot_mode": True,
                "last_move_text": "Bota karşı oyun başlatıldı",
            }
            self.active_games[ctx.channel.id] = game
            file = render_board_file(game["board"])
            embed = self.build_game_embed(game)
            view = ChessView(self, ctx.channel, game)
            await ctx.respond("Bota karşı satranç karşılaşması oluşturuldu.")
            await ctx.channel.send(embed=embed, file=file, view=view)
            return

        if rakip == ctx.author or rakip.bot:
            await ctx.respond("Geçerli bir rakip kullanıcı belirtiniz.")
            return
        if bahis and (await self.bot.db.get_economy(ctx.guild.id, ctx.author.id))["bakiye"] < bahis:
            await ctx.respond("Bakiyeniz belirtilen bahis için yeterli değildir.")
            return

        embed = discord.Embed(
            title="♟️ Satranç Düellosu Daveti",
            description=(
                f"{ctx.author.mention}, {rakip.mention} kullanıcısını satranç oynamaya davet etti!\n\n"
                f"💰 **Bahis:** `{bahis} Kredi`\n"
                f"Daveti kabul etmek için 2 dakikanız bulunmaktadır."
            ),
            color=discord.Color.gold() if bahis > 0 else discord.Color.blurple(),
        )
        await ctx.respond(content=rakip.mention, embed=embed, view=ChessInviteView(self, ctx, rakip, bahis))

    @discord.slash_command(name="pes", description="Devam eden satranç oyunundan ayrılır.")
    async def resign(self, ctx: discord.ApplicationContext):
        game = self.active_games.get(ctx.channel.id)
        if not game:
            await ctx.respond("Bu kanalda devam eden bir satranç oyunu bulunmamaktadır.")
            return
        if ctx.author not in game["players"]:
            await ctx.respond("Bu oyunun oyuncusu değilsiniz.")
            return
        winner = next(player for player in game["players"] if player != ctx.author)
        await self.finish_game(ctx.channel, winner, f"{ctx.author.display_name} `/pes` komutu ile oyundan ayrıldı.")


def setup(bot):
    return add_cog(bot, Satranc(bot))
