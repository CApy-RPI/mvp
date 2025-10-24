import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import settings

# TODO:
"""
# tracking if pieces moved (for castling)
a1_rook_moved = False
h1_rook_moved = False
a8_rook_moved = False
h8_rook_moved = False
black_king_moved = False
white_king_moved = False
"""
rank8 = 0
rank7 = 1
# rank6 = 2
rank5 = 3
rank4 = 4
# rank3 = 5
rank2 = 6
rank1 = 7
column1 = 0
# column2 = 1
# column3 = 2
# column4 = 3
# column5 = 4
# column6 = 5
# column7 = 6
column8 = 7
# dictionary to track move history
Move = tuple[str, tuple[int, int], tuple[int, int]]
moves: dict[int, Move] = {}
# example format
moves[-1] = ("", (0, 0), (0, 0))


# for sliding pieces: return True if all squares between start and end are empty
def path_clear(board, start, end):
    sr, sc = start
    er, ec = end
    dr = er - sr
    dc = ec - sc
    step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
    step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
    # ensure movement is straight line or diagonal
    if (step_r != 0 and step_c != 0) and (abs(dr) != abs(dc)):
        return False
    r, c = sr + step_r, sc + step_c
    while (r, c) != (er, ec):
        if board[r][c] != "":
            return False
        r += step_r
        c += step_c
    return True


# returns opposite color of given color
def opponent_color(color):
    return "black" if color == "white" else "white"


# make the move specified by the user
# assumes the move given is valid
# returns NONE
def make_move(board, turn, piece, start, end):
    board[start[0]][start[1]] = ""
    board[end[0]][end[1]] = piece
    moves[turn] = (piece, tuple(start), tuple(end))


# returns true if position pos is on board, else false
def on_board(pos):
    r, c = pos
    return rank8 <= r <= rank1 and column1 <= c <= column8


# TODO:
# parse the chess notation to obtain piece, start location, end location
# returns (False, False, False) if given string is NOT in valid notation form,
# otherwise returns piece, start location, end location
def parse_notation(msg):
    # if notation is valid

    # subtract 1 from location(s)
    # since in CS we count from 0
    return msg


# TODO:
# returns true if given king color is in check, false otherwise
"""
def is_in_check(board, color):
    # loop thru board looking for opponent's pieces, see what squares they attack
    return
"""


# returns true if color given is same color as piece p
def same_color(p, color):
    if p == "" or p is False or p is None:
        return False
    white = {"♙", "♖", "♘", "♗", "♕", "♔"}
    black = {"♟", "♜", "♞", "♝", "♛", "♚"}
    return (p in white and color == "white") or (p in black and color == "black")


# returns a string of the board
def print_board(board):
    strbldr = ""
    strbldr += "+---+---+---+---+---+---+---+---+"
    for i in range(len(board)):
        strbldr += "|"
        for j in range(len(board[i])):
            strbldr += board[i][j]
            strbldr += "\t|"
        strbldr += "\n"
        strbldr += "+---+---+---+---+---+---+---+---+"
    return strbldr


# returns true if move legal, else false
def is_move_legal(board, turn, piece, color, start, end):
    # check to be sure piece, start, end are not false
    if not piece:
        return False

    # check bounds
    if on_board(end):
        pass
    else:
        return False

    """
    # check if this move will result in us being in check
    board_post_move = board
    make_move(board_post_move, turn, piece, start, end)
    if is_in_check(board_post_move, color):
        return False
    """

    # declaring variables
    endx = end[0]
    endy = end[1]
    startx = start[0]
    starty = start[1]
    dx = endx - startx
    dy = endy - starty
    target_piece = board[endx][endy]

    # check if piece can move this way
    if piece in ["♙", "♟"]:
        # info needed for en passant check
        last_move: Move | None = moves.get(turn - 1)
        if last_move is None:
            last_piece = None
            last_startx = last_starty = last_endx = last_endy = None
            last_dy = last_dx = 0
        else:
            # unpack the tuple (now mypy knows last_move is a Move)
            last_piece, (last_startx, last_starty), (last_endx, last_endy) = last_move
            last_dy = abs(last_endy - last_starty)
            last_dx = abs(last_endx - last_startx)
        # pawns move forward only
        pawn_double_step = 2
        if (
            (dy > 0 and color == "white")
            or (dy < 0 and color == "black")
            or (dx == 0 and abs(dy) == 1 and target_piece == "")
            or (
                dx == 0
                and abs(dy) == pawn_double_step
                and target_piece == ""
                and path_clear(board, start, end)
                and ((starty == rank7 and color == "black") or (starty == rank2 and color == "white"))
            )
            or (abs(dx) == 1 and abs(dy) == 1 and not same_color(target_piece, color))
            or (  # en passant
                abs(dx) == 1
                and abs(dy) == 1
                and ((starty == rank4 and color == "black") or (starty == rank5 and color == "white"))
                and target_piece == ""
                and last_piece in ["♙", "♟"]
                and last_dy == pawn_double_step
                and last_dx == 0
                and endx == last_endx  # end on the same column
                and (
                    last_endx - 1 == startx or last_endx + 1 == startx
                )  # end of last move is next to start of current piece
            )
        ):
            pass

        else:
            return False

    # check if square is unoccupied

    # check you aren't moving thru another piece

    # check for being in check after move
    # should cover pins too

    # castling rules
    # castling out of check
    # castling thru check
    # has king or rook moved?

    return


# TODO:
# check for checkmate
# returns true if checkmate has been played, false otherwise
"""
def check_win(board):
    return
"""

# TODO:
# check for stalemate or repetition
# returns true if stalemate or repetition found, false otherwise
"""
def check_draw(board):
    return
"""


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
        """
        Chess game between two players.
        """
        if opponent == interaction.user:
            await interaction.response.send_message("❌ You cannot play against yourself!", ephemeral=True)
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
        draw_proposed = False
        # turn tracker
        turn = 0

        await interaction.response.send_message(
            f"🎮 Chess between {players[0].mention} (❌) and {players[1].mention} (⭕).\n"
            f"{players[turn % 2].mention}, it's your turn!\n{print_board(board)}"
        )

        def check(msg: discord.Message):
            parsed = parse_notation(msg.content)
            msg_options = ["draw?", "accept", "decline", "resign"]
            color = "white" if turn % 2 == 0 else "black"
            return (
                # checking to make sure the message is valid
                msg.author == players[turn % 2]  # correct player sent the msg
                and msg.channel == interaction.channel  # channel is correct
                and (  # if notation, check notation validity
                    msg.content in msg_options or parse_notation(msg.content)[0]
                )
                and is_move_legal(board, turn, parsed[0], color, parsed[1], parsed[2])  # move must be legal
            )

        while True:
            try:
                move_msg = await self.bot.wait_for("message", check=check, timeout=60.0)

                # check for draw offer
                if move_msg.content == "draw?":
                    draw_proposed = True
                    draw_msg = 'proposes a draw! Type "accept" to accept the draw or "decline" to decline it'
                    await interaction.followup.send(f"{print_board(board)}\n{players[turn % 2].mention} {draw_msg}.")
                    return
                # check for draw decline
                if move_msg.content == "decline" and draw_proposed:
                    draw_proposed = False
                    draw_msg = "declines to draw"
                    await interaction.followup.send(f"{print_board(board)}\n{players[turn % 2].mention} {draw_msg}.")
                    return

                """
                # check for checkmates or resignations
                if check_win(board) or move_msg.content == "resign":
                    await interaction.followup.send(f"{print_board(board)}\n✅ {players[turn % 2].mention} wins! 🎉")
                    return

                # check for draw
                if check_draw(board) or (draw_proposed and move_msg.content == "accept"):
                    await interaction.followup.send(f"{print_board(board)}\nIt's a draw!")
                    return
                """

                turn += 1
                await interaction.followup.send(f"{print_board(board)}\n{players[turn % 2].mention}, it's your turn!")
            except TimeoutError:
                await interaction.followup.send("⌛ Game timed out!")
                return


async def setup(bot: commands.Bot):
    await bot.add_cog(MultiChess(bot))
