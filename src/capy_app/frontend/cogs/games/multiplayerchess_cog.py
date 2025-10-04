import discord
import logging
from discord.ext import commands
from discord import app_commands

from config import settings
import asyncio


class MultiChess(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(
        name="multiplayer_chess",
        description="Play Chess against another user",
    )
    async def multichess(self, interaction: discord.Interaction, opponent: discord.User):
        """Chess game between two players."""
        if opponent == interaction.user:
            await interaction.response.send_message(
                "❌ You cannot play against yourself!", ephemeral=True
            )
            return

        # intial state of board
        board = [
            ["♖", "♘", "♗", "♕", "♔", "♗", "♘", "♖"],
            ["♙", "♙", "♙", "♙", "♙", "♙", "♙", "♙"],
            ["", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["♟", "♟", "♟", "♟", "♟", "♟", "♟", "♟"],
            ["♜", "♞", "♝", "♛", "♚", "♝", "♞", "♜"],
        ]
        players = [interaction.user, opponent]
        symbols = ["♔", "♕", "♖", "♗", "♘", "♙", "♚", "♛", "♜", "♝", "♞", "♟"]
        turn = 0

        # print out the board
        def print_board(board):
            print("+---+---+---+---+---+---+---+---+")
            for i in range(len(board)):
                print("|", end="")
                for j in range(len(board[i])):
                    print(board[i][j], end="\t|")
                print()
                print("+---+---+---+---+---+---+---+---+")

        # make the move specified by the user
        def make_move(board, piece, start, end):
            return

        # parse the chess notation to obtain piece, start location, end location
        def parse_notation(notation):
            return

        # returns true if move legal, else false
        def is_move_legal(piece, start, end):
            # check bounds

            # check if piece can move this way

            # check if square is unoccupied

            # check for being in check after move
            # should cover pins too

            return

        # check for checkmate
        def check_win(board):
            return

        # check for stalemate or repetition
        def check_draw(board):
            return

        await interaction.response.send_message(
            f"🎮 Chess between {players[0].mention} (❌) and {players[1].mention} (⭕).\n"
            f"{players[turn].mention}, it's your turn!\n{print_board()}"
        )

        def check(msg: discord.Message):
            return (
                msg.author == players[turn]
                and msg.channel == interaction.channel
                and msg.content.isdigit()
                # check notation validity
                and 1 <= int(msg.content) <= 9
                and board[int(msg.content) - 1] == " "
            )

        while True:
            try:
                move_msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                move = int(move_msg.content) - 1

                if check_win(board):
                    await interaction.followup.send(
                        f"{print_board()}\n✅ {players[turn].mention} wins! 🎉"
                    )
                    return

                turn += 1
                await interaction.followup.send(
                    f"{print_board()}\n{players[turn].mention}, it's your turn!"
                )
            except asyncio.TimeoutError:
                await interaction.followup.send("⌛ Game timed out!")
                return


async def setup(bot: commands.Bot):
    await bot.add_cog(MultiChess(bot))
