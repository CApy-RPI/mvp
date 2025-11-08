# ruff: noqa
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
promotion_type = "X"
q_castling = False
k_castling = False
en_passant = False
rank8 = 0
rank7 = 1
rank6 = 2
rank5 = 3
rank4 = 4
rank3 = 5
rank2 = 6
rank1 = 7
column1 = 0
column2 = 1
column3 = 2
column4 = 3
column5 = 4
column6 = 5
column7 = 6
column8 = 7
num_ranks = 8
ranks = [-1, rank1, rank2, rank3, rank4, rank5, rank6, rank7, rank8]
columns = [
    -1,
    column1,
    column2,
    column3,
    column4,
    column5,
    column6,
    column7,
    column8,
]
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


# returns the piece at the given (x,y) location of the board
def get_piece_at(board, location):
    if location[0] < 0 or location[0] > num_ranks - 1:
        return "X"
    if location[1] < 0 or location[1] > num_ranks - 1:
        return "X"
    return board[location[1], location[0]]


# returns opposite color of given color
def opponent_color(color):
    return "black" if color == "white" else "white"


# returns the piece associated with the letter representing the piece
def letter_to_piece(letter, color):
    symbols_black: dict[str, str] = {}
    symbols_black["Q"] = "♕"
    symbols_black["R"] = "♖"
    symbols_black["B"] = "♗"
    symbols_black["N"] = "♘"
    symbols_black["K"] = "♔"
    symbols_black["pawn"] = "♙"
    symbols_white: dict[str, str] = {}
    symbols_white["Q"] = "♛"
    symbols_white["R"] = "♜"
    symbols_white["B"] = "♝"
    symbols_white["N"] = "♞"
    symbols_black["K"] = "♚"
    symbols_black["pawn"] = "♟"
    return symbols_black.get(letter) if color == "black" else symbols_white.get(letter)


# make the move specified by the user
# assumes the move given is valid
# returns NONE
def make_move(board, color, turn, piece, start, end):
    # check for promotion
    if promotion_type != "X":
        promotion_piece = letter_to_piece(promotion_type, color)
        board[end[0]][end[1]] = promotion_piece
        board[start[0]][start[1]] = ""
        moves[turn] = ("promotion", tuple(start), tuple(end))

    # check for castling
    elif q_castling and color == "black":
        # a8 rook moves
        board[rank8][column1] = ""
        board[rank8][column4] = "♖"
        # king moves
        board[rank8][column5] = ""
        board[rank8][column3] = "♔"
        moves[turn] = ("q_castling", tuple(start), tuple(end))
    elif q_castling and color == "white":
        # a1 rook moves
        board[rank1][column1] = ""
        board[rank1][column4] = "♜"
        # king moves
        board[rank1][column5] = ""
        board[rank1][column3] = "♚"
        moves[turn] = ("q_castling", tuple(start), tuple(end))
    elif k_castling and color == "black":
        # h8 rook moves
        board[rank8][column8] = ""
        board[rank8][column6] = "♖"
        # king moves
        board[rank8][column5] = ""
        board[rank8][column7] = "♔"
        moves[turn] = ("k_castling", tuple(start), tuple(end))
    elif k_castling and color == "black":
        # h1 rook moves
        board[rank1][column8] = ""
        board[rank1][column6] = "♜"
        # king moves
        board[rank1][column5] = ""
        board[rank1][column7] = "♚"
        moves[turn] = ("k_castling", tuple(start), tuple(end))

    # check for en passant
    elif en_passant:
        board[start[0]][start[1]] = ""
        board[end[0]][end[1]] = piece
        # pawn taken in en passant removed
        if color == "black":
            board[end[0] - 1][end[1]] = ""
        if color == "white":
            board[end[0] + 1][end[1]] = ""
        moves[turn] = ("en passant", tuple(start), tuple(end))

    else:
        board[start[0]][start[1]] = ""
        board[end[0]][end[1]] = piece
        moves[turn] = (piece, tuple(start), tuple(end))


# returns true if position pos is on board, else false
def on_board(pos):
    r, c = pos
    return rank8 <= r <= rank1 and column1 <= c <= column8


# returns the number associated with the letter of a column
def col_to_num(letter):
    cols: dict[str, int] = {}
    cols["a"] = 0
    cols["b"] = 1
    cols["c"] = 2
    cols["d"] = 3
    cols["e"] = 4
    cols["f"] = 5
    cols["g"] = 6
    cols["h"] = 7
    return cols.get(letter)


# returns piece, start, end if notation valid
# else returns False, False, False
def knight_parser(board, msg, turn, color, start, end):
    # most cases
    if msg.size() == 3:
        end = [col_to_num(msg[1]), ranks[int(msg[2])]]
        for i in [1, 2, -1, -2]:
            for j in [1, 2, -1, -2]:
                if (
                    get_piece_at(board, [end[0] + i, end[1] + j]) == "♞" and same_color("♞", color) and abs(i) != abs(j)
                ) or (
                    get_piece_at(board, [end[0] + i, end[1] + j]) == "♘" and same_color("♘", color) and abs(i) != abs(j)
                ):
                    start = [end[0] + i, end[1] + j]
    # case: knights on same rank or column reachable to end
    # Example: Nfd2 or N3d2
    if msg.size() == 4 and "x" not in msg:
        end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        if msg[1].isdigit():
            # there is a knight on same column that can reach end
            knight_row = ranks[msg[1]]
            for i in [1, 2, -1, -2]:
                for j in [1, 2, -1, -2]:
                    if (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♞"
                        and same_color("♞", color)
                        and knight_row == end[0] + i
                        and abs(i) != abs(j)
                    ) or (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♘"
                        and same_color("♘", color)
                        and knight_row == end[0] + i
                        and abs(i) != abs(j)
                    ):
                        start = [end[0] + i, end[1] + j]
        if msg[1].isalpha():
            # there is a knight on same rank that can reach end
            knight_col = columns[msg[1]]
            for i in [1, 2, -1, -2]:
                for j in [1, 2, -1, -2]:
                    if (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♞"
                        and same_color("♞", color)
                        and knight_col == end[1] + j
                        and abs(i) != abs(j)
                    ) or (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♘"
                        and same_color("♘", color)
                        and knight_col == end[1] + j
                        and abs(i) != abs(j)
                    ):
                        start = [end[0] + i, end[1] + j]
    # rare case: knights on same rank AND same column reachable to end
    # Example: Nf3d2
    if msg.size() == 5 and "x" not in msg:
        knight_row = ranks[msg[2]]
        knight_col = col_to_num(msg[1])
        start = [knight_row, knight_col]
    # case: knight takes
    # Example: Nxd2
    if msg.size() == 4:
        end = [col_to_num(msg[1]), ranks[int(msg[2])]]
        for i in [1, 2, -1, -2]:
            for j in [1, 2, -1, -2]:
                if (
                    get_piece_at(board, [end[0] + i, end[1] + j]) == "♞" and same_color("♞", color) and abs(i) != abs(j)
                ) or (
                    get_piece_at(board, [end[0] + i, end[1] + j]) == "♘" and same_color("♘", color) and abs(i) != abs(j)
                ):
                    start = [end[0] + i, end[1] + j]
        end = [col_to_num(msg[2]), ranks[int(msg[3])]]
    # case: knight takes and (knights on same rank or column reachable to end)
    # Example: Nfxd2 or N3xd2
    if msg.size() == 5:
        end = [col_to_num(msg[3]), ranks[int(msg[4])]]
        if msg[1].isdigit():
            # there is a knight on same column that can reach end
            knight_row = ranks[msg[1]]
            for i in [1, 2, -1, -2]:
                for j in [1, 2, -1, -2]:
                    if (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♞"
                        and same_color("♞", color)
                        and knight_row == end[0] + i
                        and abs(i) != abs(j)
                    ) or (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♘"
                        and same_color("♘", color)
                        and knight_row == end[0] + i
                        and abs(i) != abs(j)
                    ):
                        start = [end[0] + i, end[1] + j]
        if msg[1].isalpha():
            # there is a knight on same rank that can reach end
            knight_col = columns[msg[1]]
            for i in [1, 2, -1, -2]:
                for j in [1, 2, -1, -2]:
                    if (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♞"
                        and same_color("♞", color)
                        and knight_col == end[1] + j
                        and abs(i) != abs(j)
                    ) or (
                        get_piece_at(board, [end[0] + i, end[1] + j]) == "♘"
                        and same_color("♘", color)
                        and knight_col == end[1] + j
                        and abs(i) != abs(j)
                    ):
                        start = [end[0] + i, end[1] + j]
    # rare case: knight takes and (knights on same rank AND same column reachable to end)
    # Example: Nf3xd2
    if msg.size() == 6:
        end = [col_to_num(msg[4]), int(msg[5])]
        knight_row = ranks[msg[2]]
        knight_col = col_to_num(msg[1])
        start = [knight_row, knight_col]

    # return info
    if start[0] == -1 or end[0] == -1:
        return False, False, False
    return (
        "♘" if color == "black" else "♞",
        start,
        end,
    )


# returns piece, start, end if notation valid
# else returns False, False, False
def king_parser(board, msg, turn, color, start, end):
    # case: King move
    # Example: Ke2
    if "x" not in msg and msg.size() == 3:
        end = [col_to_num(msg[1]), ranks[int(msg[2])]]
    # case: King takes
    # Example: Kxe2
    if "x" in msg and msg.size() == 4:
        end = [col_to_num(msg[2]), ranks[int(msg[3])]]

    # find start
    for i in [1, 0, -1]:
        for j in [1, 0, -1]:
            if (
                get_piece_at(board, [end[0] + i, end[1] + j]) == "♚"
                and same_color("♚", color)
                and not (i == 0 and j == 0)
            ) or (
                get_piece_at(board, [end[0] + i, end[1] + j]) == "♔"
                and same_color("♔", color)
                and not (i == 0 and j == 0)
            ):
                start = [end[0] + i, end[1] + j]
    # return info
    if start[0] == -1 or end[0] == -1:
        return False, False, False
    return ("♔" if color == "black" else "♚", [start[1], start[0]], [end[1], end[0]])


# returns piece, start, end if notation valid
# else returns False, False, False
def queen_parser(board, msg, turn, color, start, end):
    start = [-1, -1]
    end = [-1, -1]
    directions = [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
        [1, 1],
        [1, -1],
        [-1, 1],
        [-1, -1],
    ]
    # case: Queen move
    # Example: Qe2
    # case: Queen takes
    # Example: Qxe2
    if ("x" in msg and msg.size() == 4) or ("x" not in msg and msg.size() == 3):
        if "x" in msg and msg.size() == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        if "x" not in msg and msg.size() == 3:
            end = [col_to_num(msg[1]), ranks[int(msg[2])]]
        # find all squares queen can reach from end
        reachable = []
        for dx, dy in directions:
            cx, cy = end[0] + dx, end[1] + dy
            while 0 <= cx < num_ranks and 0 <= cy < num_ranks:
                reachable.append([cx, cy])
                cx += dx
                cy += dy
        for square in reachable:
            if (get_piece_at(board, [square[0], square[1]]) == "♛" and same_color("♛", color)) or (
                get_piece_at(board, [square[0], square[1]]) == "♕" and same_color("♕", color)
            ):
                start = square

    # rare case: Queen moves (multiple queens can access end)
    # Example: Qce4 or Q4e4
    # rare case: Queen takes (multiple queens can access end)
    # Example: Qcxe4 or Q4xe4
    if ("x" in msg and msg.size() == 5) or ("x" not in msg and msg.size() == 4):
        if "x" in msg and msg.size() == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]
        if "x" not in msg and msg.size() == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        # find all squares queen can reach from end
        reachable = []
        for dx, dy in directions:
            cx, cy = end[0] + dx, end[1] + dy
            while 0 <= cx < num_ranks and 0 <= cy < num_ranks:
                reachable.append([cx, cy])
                cx += dx
                cy += dy
        if msg[1].isalpha():
            start[0] = col_to_num(msg[1])
            for square in reachable:
                if square[0] == start[0] and (
                    (get_piece_at(board, [square[0], square[1]]) == "♛" and same_color("♛", color))
                    or (get_piece_at(board, [square[0], square[1]]) == "♕" and same_color("♕", color))
                ):
                    start[1] = square[1]
        if msg[1].isdigit():
            start[1] = ranks[msg[1]]
            for square in reachable:
                if square[1] == start[1] and (
                    (get_piece_at(board, [square[0], square[1]]) == "♛" and same_color("♛", color))
                    or (get_piece_at(board, [square[0], square[1]]) == "♕" and same_color("♕", color))
                ):
                    start[0] = square[0]
    # rare case: Queen takes (Queens on same rank and column reachable to end)
    # Example: Qg4xe2
    # rare case: Queen moves (Queens on same rank and column reachable to end)
    # Example: Qg4e2
    if ("x" in msg and msg.size() == 6) or ("x" not in msg and msg.size() == 5):
        start = [col_to_num(msg[1]), ranks[int(msg[2])]]
        if "x" in msg and msg.size() == 6:
            end = [col_to_num(msg[4]), ranks[int(msg[5])]]
        if "x" not in msg and msg.size() == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]

    # return
    if start[0] == -1 or end[0] == -1:
        return False, False, False

    return ("♕" if color == "black" else "♛", [start[1], start[0]], [end[1], end[0]])


# returns piece, start, end if notation valid
# else returns False, False, False
def bishop_parser(board, msg, turn, color, start, end):
    start = [-1, -1]
    end = [-1, -1]
    directions = [[1, 1], [1, -1], [-1, 1], [-1, -1]]
    # case: Bishop moves
    # Example: Be4
    # case: Bishop takes
    # Example: Bxe4
    if ("x" in msg and msg.size() == 4) or ("x" not in msg and msg.size() == 3):
        if "x" in msg and msg.size() == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        if "x" not in msg and msg.size() == 3:
            end = [col_to_num(msg[1]), ranks[int(msg[2])]]
        # find all squares bishop can reach from end
        reachable = []
        for dx, dy in directions:
            cx, cy = end[0] + dx, end[1] + dy
            while 0 <= cx < num_ranks and 0 <= cy < num_ranks:
                reachable.append([cx, cy])
                cx += dx
                cy += dy
        # find the start square
        for square in reachable:
            if (get_piece_at(board, [square[0], square[1]]) == "♝" and same_color("♝", color)) or (
                get_piece_at(board, [square[0], square[1]]) == "♗" and same_color("♗", color)
            ):
                start = square

    # rare case: Bishop moves (multiple bishops can access end)
    # Example: Bce4 or B6e4
    # rare case: Bishop takes (multiple bishops can access end)
    # Example: Bcxe4 or B6xe4
    if ("x" in msg and msg.size() == 5) or ("x" not in msg and msg.size() == 4):
        if "x" in msg and msg.size() == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]
        if "x" not in msg and msg.size() == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        # find all squares bishop can reach from end
        reachable = []
        for dx, dy in directions:
            cx, cy = end[0] + dx, end[1] + dy
            while 0 <= cx < num_ranks and 0 <= cy < num_ranks:
                reachable.append([cx, cy])
                cx += dx
                cy += dy
        # find the start square
        if msg[1].isalpha():
            start[0] = col_to_num(msg[1])
            for square in reachable:
                if square[0] == start[0] and (
                    (get_piece_at(board, [square[0], square[1]]) == "♝" and same_color("♝", color))
                    or (get_piece_at(board, [square[0], square[1]]) == "♗" and same_color("♗", color))
                ):
                    start[1] = square[1]
        if msg[1].isdigit():
            start[1] = ranks[msg[1]]
            for square in reachable:
                if square[1] == start[1] and (
                    (get_piece_at(board, [square[0], square[1]]) == "♝" and same_color("♝", color))
                    or (get_piece_at(board, [square[0], square[1]]) == "♗" and same_color("♗", color))
                ):
                    start[0] = square[0]

    # rare case: Bishop moves (multiple bishops can access end)
    # Example: Bc6e4
    # rare case: Bishop takes (multiple bishops can access end)
    # Example: Bc6xe4
    if ("x" in msg and msg.size() == 6) or ("x" not in msg and msg.size() == 5):
        start = [col_to_num(msg[1]), ranks[int(msg[2])]]
        if "x" in msg and msg.size() == 6:
            end = [col_to_num(msg[4]), ranks[int(msg[5])]]
        if "x" not in msg and msg.size() == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]

    # return
    if start[0] == -1 or end[0] == -1:
        return False, False, False

    return ("♗" if color == "black" else "♝", [start[1], start[0]], [end[1], end[0]])


# returns piece, start, end if notation valid
# else returns False, False, False
def rook_parser(board, msg, turn, color, start, end):
    start = [-1, -1]
    end = [-1, -1]
    directions = [[1, 0], [-1, 0], [0, 1], [0, -1]]

    # case: Rook moves
    # Example: Re4
    # case: Rook takes
    # Example: Rxe4
    if ("x" in msg and msg.size() == 4) or ("x" not in msg and msg.size() == 3):
        if "x" in msg and msg.size() == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        if "x" not in msg and msg.size() == 3:
            end = [col_to_num(msg[1]), ranks[int(msg[2])]]
        # find all squares rook can reach from end
        reachable = []
        for dx, dy in directions:
            cx, cy = end[0] + dx, end[1] + dy
            while 0 <= cx < num_ranks and 0 <= cy < num_ranks:
                reachable.append([cx, cy])
                cx += dx
                cy += dy
        # find the start square
        for square in reachable:
            if (get_piece_at(board, [square[0], square[1]]) == "♜" and same_color("♜", color)) or (
                get_piece_at(board, [square[0], square[1]]) == "♖" and same_color("♖", color)
            ):
                start = square
    # case: Rook moves (multiple rooks can access end)
    # Example: Rce4 or R2e4
    # case: Rook takes (multiple rooks can access end)
    # Example: Rcxe4 or R2xe4
    if ("x" in msg and msg.size() == 5) or ("x" not in msg and msg.size() == 4):
        if "x" in msg and msg.size() == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]
        if "x" not in msg and msg.size() == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        # find all squares rook can reach from end
        reachable = []
        for dx, dy in directions:
            cx, cy = end[0] + dx, end[1] + dy
            while 0 <= cx < num_ranks and 0 <= cy < num_ranks:
                reachable.append([cx, cy])
                cx += dx
                cy += dy
        # find the start square
        if msg[1].isalpha():
            start[0] = col_to_num(msg[1])
            for square in reachable:
                if square[0] == start[0] and (
                    (get_piece_at(board, [square[0], square[1]]) == "♝" and same_color("♝", color))
                    or (get_piece_at(board, [square[0], square[1]]) == "♗" and same_color("♗", color))
                ):
                    start[1] = square[1]
        if msg[1].isdigit():
            start[1] = ranks[msg[1]]
            for square in reachable:
                if square[1] == start[1] and (
                    (get_piece_at(board, [square[0], square[1]]) == "♝" and same_color("♝", color))
                    or (get_piece_at(board, [square[0], square[1]]) == "♗" and same_color("♗", color))
                ):
                    start[0] = square[0]

    # return
    if start[0] == -1 or end[0] == -1:
        return False, False, False

    return ("♖" if color == "black" else "♜", [start[1], start[0]], [end[1], end[0]])


# returns piece, start, end if notation valid
# else returns False, False, False
def pawn_parser(board, msg, turn, color, start, end):
    start = [-1, -1]
    end = [-1, -1]
    # case: pawn move
    # Example: e4
    if msg.size() == 2:
        end = [col_to_num(msg[0]), ranks[int(msg[1])]]
        # black single move
        if color == "black" and get_piece_at(board, [end[0], end[1] - 1]) == "♙":
            start = [end[0], end[1] - 1]
        # white single move
        elif color == "white" and get_piece_at(board, [end[0], end[1] + 1]) == "♟":
            start = [end[0], end[1] + 1]
        else:
            # black double move
            if color == "black" and get_piece_at(board, [end[0], end[1] - 2]) == "♙":
                start = [end[0], end[1] - 2]
            # white double move
            if color == "white" and get_piece_at(board, [end[0], end[1] + 2]) == "♟":
                start = [end[0], end[1] + 2]

    # case: pawn takes
    # Example: dxe4
    if msg.size() == 4 and msg[1] == "x":
        end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        start = [col_to_num(msg[0]), -1]

        # black takes
        if color == "black" and get_piece_at(board, [start[0], end[1] - 1]) == "♙":
            start = [start[0], end[1] - 1]
        # white takes
        if color == "white" and get_piece_at(board, [start[0], end[1] + 1]) == "♟":
            start = [start[0], end[1] + 1]

    # case: pawn promotes
    # Example: e8=Q
    if msg.size() == 4 and msg[1] == "=":
        end = [col_to_num(msg[0]), ranks[int(msg[1])]]
        # black promotes
        if color == "black" and get_piece_at(board, [end[0], end[1] - 1]) == "♙":
            start = [end[0], end[1] - 1]
        # white promotes
        if color == "white" and get_piece_at(board, [end[0], end[1] + 1]) == "♟":
            start = [end[0], end[1] + 1]
        promotion_type = msg[3]

    # return
    if start[0] == -1 or end[0] == -1:
        return False, False, False

    return ("♙" if color == "black" else "♟", [start[1], start[0]], [end[1], end[0]])


# parse the chess notation to obtain piece, start location, end location
# returns (False, False, False) if given string is NOT in valid notation form,
# otherwise returns piece, start location, end location
def parse_notation(board, msg, turn):
    color = "white" if turn % 2 == 0 else "black"
    piece, start, end = False, False, False
    # castling
    if msg == "O-O":
        k_castling = True
        return (
            "♔",
            [rank8, column5],
            [rank8, column7] if color == "black" else "♚",
            [rank1, column5],
            [rank1, column7],
        )
    elif msg == "O-O-O":
        q_castling = False
        return (
            "♔",
            [rank8, column5],
            [rank8, column3] if color == "black" else "♚",
            [rank1, column5],
            [rank1, column3],
        )
    # Knight
    elif msg[0] == "N":
        piece, start, end = knight_parser(board, msg, turn, color, start, end)

    # King
    elif msg[0] == "K":
        piece, start, end = king_parser(board, msg, turn, color, start, end)

    # Queen
    elif msg[0] == "Q":
        piece, start, end = queen_parser(board, msg, turn, color, start, end)

    # Bishop
    elif msg[0] == "B":
        piece, start, end = bishop_parser(board, msg, turn, color, start, end)

    # Rook
    elif msg[0] == "R":
        piece, start, end = rook_parser(board, msg, turn, color, start, end)

    # pawn
    elif msg[0] in ["a", "b", "c", "d", "e", "f", "g", "h"]:
        piece, start, end = pawn_parser(board, msg, turn, color, start, end)

    else:
        return False, False, False

    return piece, start, end


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


# TODO: finish function
# returns true if move legal, else false
def is_move_legal(board, turn, piece, color, start, end):
    # check to be sure piece, start, end are not false
    if not piece:
        return False, False, False

    # check bounds
    if on_board(end):
        pass
    else:
        return False, False, False

    """
    # check if this move will result in us being in check
    board_post_move = board
    make_move(board_post_move, color, turn, piece, start, end)
    if is_in_check(board_post_move, color):
        return False, False, False
    """

    # declaring variables
    endx = end[1]
    endy = end[0]
    startx = start[1]
    starty = start[0]
    dx = endx - startx
    dy = endy - starty
    target_piece = board[endx][endy]

    # can never take your own piece
    if same_color(target_piece, color):
        return False, False, False

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
        if ((dy < 0 and color == "white") or (dy > 0 and color == "black")) and (
            (dx == 0 and abs(dy) == 1 and target_piece == "")
            or (
                dx == 0
                and abs(dy) == pawn_double_step
                and target_piece == ""
                and path_clear(board, start, end)
                and ((starty == rank7 and color == "black") or (starty == rank2 and color == "white"))
            )
            or (abs(dx) == 1 and abs(dy) == 1 and not same_color(target_piece, color))
        ):
            # check for pawn promotion
            if promotion_type != "X":
                # must be moving to rank1 as black or rank8 as white, must promote to valid piece
                if promotion_type in ["Q", "R", "B", "N"] and (
                    (starty == rank7 and color == "white" and endy == rank8)
                    or (starty == rank2 and color == "black" and endy == rank1)
                ):
                    return True
                else:
                    return False
            else:
                return True
        elif (  # en passant
            ((dy > 0 and color == "white") or (dy < 0 and color == "black"))
            and abs(dx) == 1
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
        ):
            en_passant = True
            return True

        else:
            return False

    # the check for how pieces move covered in parse_notation()

    # just check that piece is indeed at start location

    # bishop, rook, queen
    # check you aren't moving thru another piece

    # king
    if piece in ["♔", "♚"]:
        # if the king is indeed found at start
        if get_piece_at(board, start) == piece:
            return True
        else:
            return False

    # knight

    # TODO: check for castling
    # castling rules
    # castling out of check
    # castling thru check
    # has king or rook moved? check globals

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
            parsed = parse_notation(board, msg.content, turn)
            msg_options = ["draw?", "accept", "decline", "resign"]
            color = "white" if turn % 2 == 0 else "black"
            return (
                # checking to make sure the message is valid
                msg.author == players[turn % 2]  # correct player sent the msg
                and msg.channel == interaction.channel  # channel is correct
                and (  # if notation, check notation validity
                    msg.content in msg_options or parsed[0] is not False
                )
                and is_move_legal(board, turn, parsed[0], color, parsed[1], parsed[2])  # move must be legal
            )

        while True:
            try:
                move_msg = await self.bot.wait_for("message", check=check, timeout=100.0)

                # print out rules
                if turn == 0:
                    await interaction.followup.send(
                        f'Welcome to CAPY Chess! To make a move, type your move in chess notation. Do not include symbols for check or checkmate.\n\nTo propose a draw, send "draw?". To resign, send "resign".\n\nHave fun!'
                    )

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

                # TODO: actually make the move specified by user
                # uses piece, start, end from parsed
                # check for globals like q_castling, k_castling, en_passant, promotion_type AND :
                """
                # update tracking of whether pieces have moved (for castling)
                a1_rook_moved = False
                h1_rook_moved = False
                a8_rook_moved = False
                h8_rook_moved = False
                black_king_moved = False
                white_king_moved = False
                """

                # reset necessary globals
                q_castling = False
                k_castling = False
                en_passant = False
                promotion_type = "X"

                turn += 1
                await interaction.followup.send(f"{print_board(board)}\n{players[turn % 2].mention}, it's your turn!")
            except TimeoutError:
                await interaction.followup.send("⌛ Game timed out!")
                return


async def setup(bot: commands.Bot):
    await bot.add_cog(MultiChess(bot))
