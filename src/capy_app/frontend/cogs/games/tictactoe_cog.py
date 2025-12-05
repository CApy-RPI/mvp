import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import settings


class TicTacToeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"discord.cog.{self.__class__.__name__.lower()}")

    @app_commands.guilds(discord.Object(id=settings.DEBUG_GUILD_ID))
    @app_commands.command(
        name="tictactoe",
        description="Play Tic Tac Toe against another user",
    )
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.User):
        """Tic Tac Toe game between two players."""
        if opponent == interaction.user:
            await interaction.response.send_message("❌ You cannot play against yourself!", ephemeral=True)
            return

        board = [" " for _ in range(9)]
        players = [interaction.user, opponent]
        symbols = ["❌", "⭕"]
        turn = 0

        def num_to_emoji(i):
            return board[i] if board[i] != " " else f"{i + 1}\N{COMBINING ENCLOSING KEYCAP}"

        def render_board():
            return (
                f"\n{num_to_emoji(0)} | {num_to_emoji(1)} | {num_to_emoji(2)}\n"
                f"----+---+----\n"
                f"{num_to_emoji(3)} | {num_to_emoji(4)} | {num_to_emoji(5)}\n"
                f"----+---+----\n"
                f"{num_to_emoji(6)} | {num_to_emoji(7)} | {num_to_emoji(8)}\n"
            )

        def check_win(symbol):
            wins = [
                [0, 1, 2],
                [3, 4, 5],
                [6, 7, 8],  # rows
                [0, 3, 6],
                [1, 4, 7],
                [2, 5, 8],  # cols
                [0, 4, 8],
                [2, 4, 6],  # diagonals
            ]
            return any(all(board[i] == symbol for i in combo) for combo in wins)

        await interaction.response.send_message(
            f"🎮 Tic Tac Toe between {players[0].mention} (❌) and {players[1].mention} (⭕).\n"
            f"{players[turn].mention}, it's your turn!\n{render_board()}"
        )

        def check(msg: discord.Message):
            max_input = 9
            min_input = 1
            return (
                msg.author == players[turn]
                and msg.channel == interaction.channel
                and msg.content.isdigit()
                and min_input <= int(msg.content) <= max_input
                and board[int(msg.content) - 1] == " "
            )

        # main code loop
        for _ in range(9):
            try:
                move_msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                move = int(move_msg.content) - 1
                board[move] = symbols[turn]

                if check_win(symbols[turn]):
                    await interaction.followup.send(f"{render_board()}\n✅ {players[turn].mention} wins! 🎉")
                    return

                turn = 1 - turn
                await interaction.followup.send(f"{render_board()}\n{players[turn].mention}, it's your turn!")
            except TimeoutError:
                await interaction.followup.send("⌛ Game timed out!")
                return

        await interaction.followup.send(f"{render_board()}\n🤝 It's a draw!")


async def setup(bot: commands.Bot):
    await bot.add_cog(TicTacToeCog(bot))
