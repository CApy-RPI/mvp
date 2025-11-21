# ruff: noqa
import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from typing import List, Tuple

# for 50 move rule
num_moves_since_takes = 0
num_moves_since_pawn_moved = 0
# tracking if pieces moved (for castling)
in_check = False
a1_rook_moved = False
h1_rook_moved = False
a8_rook_moved = False
h8_rook_moved = False
black_king_moved = False
white_king_moved = False
# globals for special case moves
promotion_type = "X"
q_castling = False
k_castling = False
en_passant = False
# rank and column access values
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

# tracks repeated positions for draw by repetition
positions: dict[str, int] = {}
# hash string : number of occurrences of position
positions["example_hash_string"] = 1


# returns True if positions [string] > 2 AKA draw by repetition found else False
# records the position in the hash table for the purpose of tracking draw by repetition
def log_position(board):
    string = ""
    for i in range(8):
        for j in range(8):
            if board[i][j] != "":
                string += board[i][j]
            else:
                string += "_"
    positions[string] = positions.get(string, 0) + 1
    if positions[string] > 2:
        return True
    else:
        return False


# for sliding pieces: return True if all squares between start and end are empty
def path_clear(board, start, end):
    sc, sr = start
    ec, er = end
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
def make_move(board, color, turn, piece, start, end, change_globals):
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
        if change_globals:
            black_king_moved = True
    elif q_castling and color == "white":
        # a1 rook moves
        board[rank1][column1] = ""
        board[rank1][column4] = "♜"

        # king moves
        board[rank1][column5] = ""
        board[rank1][column3] = "♚"
        moves[turn] = ("q_castling", tuple(start), tuple(end))
        if change_globals:
            white_king_moved = True
    elif k_castling and color == "white":
        # h8 rook moves
        board[rank8][column8] = ""
        board[rank8][column6] = "♖"
        # king moves
        board[rank8][column5] = ""
        board[rank8][column7] = "♔"
        moves[turn] = ("k_castling", tuple(start), tuple(end))
        if change_globals:
            white_king_moved = True
    elif k_castling and color == "black":
        # h1 rook moves
        board[rank1][column8] = ""
        board[rank1][column6] = "♜"
        # king moves
        board[rank1][column5] = ""
        board[rank1][column7] = "♚"
        moves[turn] = ("k_castling", tuple(start), tuple(end))
        if change_globals:
            black_king_moved = True
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
        if change_globals:
            num_moves_since_takes = 0

    else:
        # alter globals if specified
        if change_globals:
            if piece == "♚":
                white_king_moved = True
            if piece == "♔":
                black_king_moved = True
            if piece == "♜" and start[0] == column1 and start[1] == rank1:
                a1_rook_moved = True
            if piece == "♜" and start[0] == column8 and start[1] == rank1:
                h1_rook_moved = True
            if piece == "♖" and start[0] == column1 and start[1] == rank8:
                a8_rook_moved = True
            if piece == "♖" and start[0] == column8 and start[1] == rank8:
                h8_rook_moved = True
            if board[end[0]][end[1]] is not "":
                num_moves_since_takes = 0
            if piece in ["♙", "♟"]:
                num_moves_since_pawn_moved = 0
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
    if len(msg) == 3:
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
    if len(msg) == 4 and "x" not in msg:
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
    if len(msg) == 5 and "x" not in msg:
        knight_row = ranks[msg[2]]
        knight_col = col_to_num(msg[1])
        start = [knight_row, knight_col]
    # case: knight takes
    # Example: Nxd2
    if len(msg) == 4:
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
    if len(msg) == 5:
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
    if len(msg) == 6:
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
    if "x" not in msg and len(msg) == 3:
        end = [col_to_num(msg[1]), ranks[int(msg[2])]]
    # case: King takes
    # Example: Kxe2
    if "x" in msg and len(msg) == 4:
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
    if ("x" in msg and len(msg) == 4) or ("x" not in msg and len(msg) == 3):
        if "x" in msg and len(msg) == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        if "x" not in msg and len(msg) == 3:
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
    if ("x" in msg and len(msg) == 5) or ("x" not in msg and len(msg) == 4):
        if "x" in msg and len(msg) == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]
        if "x" not in msg and len(msg) == 4:
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
    if ("x" in msg and len(msg) == 6) or ("x" not in msg and len(msg) == 5):
        start = [col_to_num(msg[1]), ranks[int(msg[2])]]
        if "x" in msg and len(msg) == 6:
            end = [col_to_num(msg[4]), ranks[int(msg[5])]]
        if "x" not in msg and len(msg) == 5:
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
    if ("x" in msg and len(msg) == 4) or ("x" not in msg and len(msg) == 3):
        if "x" in msg and len(msg) == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        if "x" not in msg and len(msg) == 3:
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
    if ("x" in msg and len(msg) == 5) or ("x" not in msg and len(msg) == 4):
        if "x" in msg and len(msg) == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]
        if "x" not in msg and len(msg) == 4:
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
    if ("x" in msg and len(msg) == 6) or ("x" not in msg and len(msg) == 5):
        start = [col_to_num(msg[1]), ranks[int(msg[2])]]
        if "x" in msg and len(msg) == 6:
            end = [col_to_num(msg[4]), ranks[int(msg[5])]]
        if "x" not in msg and len(msg) == 5:
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
    if ("x" in msg and len(msg) == 4) or ("x" not in msg and len(msg) == 3):
        if "x" in msg and len(msg) == 4:
            end = [col_to_num(msg[2]), ranks[int(msg[3])]]
        if "x" not in msg and len(msg) == 3:
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
    if ("x" in msg and len(msg) == 5) or ("x" not in msg and len(msg) == 4):
        if "x" in msg and len(msg) == 5:
            end = [col_to_num(msg[3]), ranks[int(msg[4])]]
        if "x" not in msg and len(msg) == 4:
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
    if len(msg) == 2:
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
    if len(msg) == 4 and msg[1] == "x":
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
    if len(msg) == 4 and msg[1] == "=":
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


# returns true if color given is same color as piece p
def same_color(p, color):
    if p == "" or p is False or p is None:
        return False
    white = {"♙", "♖", "♘", "♗", "♕", "♔"}
    black = {"♟", "♜", "♞", "♝", "♛", "♚"}
    return (p in white and color == "white") or (p in black and color == "black")


# returns a string of the board
def print_board(board):
    strbldr = "```\n"
    strbldr += "+---+---+---+---+---+---+---+---+"
    for i in range(len(board)):
        strbldr += "\n|"
        for j in range(len(board[i])):
            strbldr += board[i][j] if board[i][j] != "" else " "
            # fill the rest with dots instead of spaces
            if board[i][j] == "":
                strbldr += "  "
            else:
                strbldr += " "
            strbldr += "|"
        strbldr += "\n"
        strbldr += "+---+---+---+---+---+---+---+---+"
    return strbldr + "```"


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

    # check if this move will result in us being in check
    board_post_move = board
    make_move(board_post_move, color, turn, piece, start, end, False)
    # find king's location
    king_location = find_king(board_post_move, color)
    if is_square_attacked(board_post_move, king_location, opponent_color(color))[0]:
        return False

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
        return False

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
    # just check that piece is indeed at start location here

    # sliding pieces: bishop, rook, queen
    # check you aren't moving thru another piece
    if piece in ["♝", "♗", "♖", "♜", "♕", "♛"]:
        if path_clear(board, start, end) and get_piece_at(board, start) == piece:
            return True
        else:
            return False

    # knight
    if piece in ["♘", "♞"]:
        if get_piece_at(board, start) == piece:
            return True
        else:
            return False

    # king
    if piece in ["♔", "♚"]:
        # if castling
        if k_castling:
            if color == "white":
                if (
                    not in_check
                    and not h1_rook_moved
                    and not white_king_moved
                    and not is_square_attacked(board, [column6, rank1], "black")[0]
                ):
                    return True
            elif color == "black":
                if (
                    not in_check
                    and not h8_rook_moved
                    and not black_king_moved
                    and not is_square_attacked(board, [column6, rank8], "white")[0]
                ):
                    return True
        elif q_castling:
            if color == "white":
                if (
                    not in_check
                    and not a1_rook_moved
                    and not white_king_moved
                    and not is_square_attacked(board, [column4, rank1], "black")[0]
                ):
                    return True
            elif color == "black":
                if (
                    not in_check
                    and not a8_rook_moved
                    and not black_king_moved
                    and not is_square_attacked(board, [column4, rank8], "white")[0]
                ):
                    return True
        # if the king is indeed found at start
        elif get_piece_at(board, start) == piece:
            return True
        else:
            return False

    return False


# returns a list of tuples that represent all locations on board attacked by piece
def get_attacked_squares(board, piece, piece_location):
    col, row = piece_location
    attacked = []

    rook_dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    bishop_dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    king_moves = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    knight_moves = [
        (2, 1),
        (2, -1),
        (-2, 1),
        (-2, -1),
        (1, 2),
        (1, -2),
        (-1, 2),
        (-1, -2),
    ]

    def in_bounds(c, r):
        return 0 <= c < 8 and 0 <= r < 8

    white = {"♔", "♕", "♖", "♗", "♘", "♙"}
    black = {"♚", "♛", "♜", "♝", "♞", "♟"}

    # identify color + base piece type
    if piece in white:
        color = "white"
    else:
        color = "black"

    # queen
    if piece in ["♕", "♛"]:
        directions = rook_dirs + bishop_dirs
        for dx, dy in directions:
            c, r = col + dx, row + dy
            while in_bounds(c, r):
                attacked.append((c, r))
                c += dx
                r += dy

    # rook
    elif piece in ["♖", "♜"]:
        for dx, dy in rook_dirs:
            c, r = col + dx, row + dy
            while in_bounds(c, r):
                attacked.append((c, r))
                c += dx
                r += dy

    # bishop
    elif piece in ["♗", "♝"]:
        for dx, dy in bishop_dirs:
            c, r = col + dx, row + dy
            while in_bounds(c, r):
                attacked.append((c, r))
                c += dx
                r += dy

    # knight
    elif piece in ["♘", "♞"]:
        for dx, dy in knight_moves:
            c, r = col + dx, row + dy
            if in_bounds(c, r):
                attacked.append((c, r))

    # king
    elif piece in ["♔", "♚"]:
        for dx, dy in king_moves:
            c, r = col + dx, row + dy
            if in_bounds(c, r):
                attacked.append((c, r))

    # pawn
    elif piece in ["♙", "♟"]:
        if piece == "♟":  # white
            for c, r in [(col + 1, row - 1), (col - 1, row - 1)]:
                if in_bounds(c, r):
                    attacked.append((c, r))
        else:  # black
            for c, r in [(col + 1, row + 1), (col - 1, row + 1)]:
                if in_bounds(c, r):
                    attacked.append((c, r))
    return attacked


# [0] returns true if square is being attacked by an opponent's piece, else false
# [1] returns locations in x, y of pieces on the board delivering the attack on square
# EX: [[x1, y1], [x2, y2]]
# takes in square as x, y and color of atkr
def is_square_attacked(board, target_square: list[int], color_of_attacker: str) -> Tuple[bool, List[List[int]]]:
    return_val: Tuple[bool, List[List[int]]] = (False, [])
    attacked = False
    attackers: List[List[int]] = []

    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            piece_location = [col, row]
            if piece != "" and same_color(piece, color_of_attacker):
                atked_squares = get_attacked_squares(board, piece, piece_location)
                for sq in atked_squares:
                    if target_square == sq:
                        if piece in ["♖", "♜", "♗", "♝", "♕", "♛"]:
                            if path_clear(board, target_square, sq):
                                attacked = True
                                attackers.append(piece_location)
                        elif piece in ["♘", "♞", "♔", "♚", "♙", "♟"]:
                            attacked = True
                            attackers.append(piece_location)
    return attacked, attackers


# returns the location of the king of color in x,y format
def find_king(board, color):
    king = "NULL"
    if color == "black":
        king = "♔"
    else:
        king = "♚"
    for i in range(8):
        for j in range(8):
            if board[i][j] == king:
                return [j, i]
    # shouldn't ever get here
    return [-1, -1]


# returns the (non-inclusive) squares between start and end if there is a perfect path
# else returns False
def get_squares_between(board, start, end):
    start_col, start_row = start
    end_col, end_row = end
    squares_between = []

    d_col = end_col - start_col
    d_row = end_row - start_row

    # Determine direction of movement
    step_col = 0 if d_col == 0 else (1 if d_col > 0 else -1)
    step_row = 0 if d_row == 0 else (1 if d_row > 0 else -1)

    # Check if the path is straight or diagonal
    if not (d_col == 0 or d_row == 0 or abs(d_col) == abs(d_row)):
        return False  # Not aligned along a valid path

    # Start moving one step from start toward end
    c, r = start_col + step_col, start_row + step_row

    while (c, r) != (end_col, end_row):
        # Ensure still within board bounds
        if not (0 <= c < 8 and 0 <= r < 8):
            break
        squares_between.append([c, r])
        c += step_col
        r += step_row

    return squares_between


# returns list of all pieces associated with given color
def pieces_of_color(color):
    if color == "black":
        return ["♖", "♘", "♗", "♕", "♔", "♙"]
    else:
        return ["♛", "♚", "♝", "♞", "♜", "♟"]


# check for checkmate
# takes in board post move
# returns true if checkmate in on the board after a move by color, false otherwise
def check_win(board, color):
    # find opponent king of color
    king_color = opponent_color(color)
    king_attacker_color = opponent_color(king_color)
    king_location = find_king(board, king_color)
    # check for square that king is on is under attack
    if is_square_attacked(board, king_location, king_attacker_color)[0]:
        in_check = True
        # all adjacent squares must be attacked or occupied by same color piece
        symbols = pieces_of_color(color)
        symbols.append("")
        king_is_trapped = True
        for i in [1, 0, -1]:
            for j in [1, 0, -1]:
                if (
                    get_piece_at(board, [king_location[0] + i, king_location[1] + j]) in symbols
                    and not is_square_attacked(board, [j, i], king_color)[0]
                ):
                    king_is_trapped = False
        # identify piece(s) giving check
        attacker_squares = is_square_attacked(board, king_location, king_attacker_color)[1]
        # if double check, blocking and taking impossible
        if len(attacker_squares) > 1:
            piece_giving_check_is_takeable = False
            check_is_blockable = False
        # if attacker can be attacked and taking attacker doesn't leave us in check (pins)
        atkr_is_atkd, atkr_atkd_by = is_square_attacked(board, attacker_squares[0], king_color)
        if len(attacker_squares) == 1:
            if atkr_is_atkd:
                for atkr_loc in atkr_atkd_by:
                    board_post_takes = board
                    make_move(
                        board_post_takes,
                        color,
                        -2,
                        board_post_takes[atkr_loc[1]][atkr_loc[0]],
                        atkr_loc,
                        attacker_squares[0],
                        False,
                    )
                    # then check-giving piece is takeable
                    if not is_square_attacked(board_post_takes, king_location, king_attacker_color)[0]:
                        piece_giving_check_is_takeable = True

            # for rook, bishop, queen: can we block?
            if get_piece_at(board, attacker_squares[0]) in [
                "♖",
                "♜",
                "♗",
                "♝",
                "♕",
                "♛",
            ]:
                # find all squares where you can potentially block
                blocking_squares = get_squares_between(board, king_location, attacker_squares[0])
                if blocking_squares is not False:
                    for block_square in blocking_squares:
                        exists_blockers, blocker_locs = is_square_attacked(board, block_square, king_color)
                        # if blocking on this square is possible
                        if exists_blockers:
                            # loop through potential blockers, try to find a valid one
                            for blocker_loc in blocker_locs:
                                board_post_block = board
                                make_move(
                                    board_post_block,
                                    color,
                                    -2,
                                    board_post_block[blocker_loc[1]][blocker_loc[0]],
                                    blocker_loc,
                                    attacker_squares[0],
                                    False,
                                )
                                # then blocking is possible
                                if not is_square_attacked(board_post_block, king_location, king_attacker_color)[0]:
                                    check_is_blockable = True

        if king_is_trapped and not check_is_blockable and not piece_giving_check_is_takeable:
            return True
        else:
            return False
    else:
        return False


# returns a list of all pieces on board other than kings
def get_pieces_on_board(board):
    pieces = []
    for i in range(8):
        for j in range(8):
            if board[i][j] != "" and board[i][j] != "♔" and board[i][j] != "♚":
                pieces.append(board[i][j])
    return pieces


# returns a list of tuples containing (piece, piece_location) for all pieces of color on board
# does not include king
def get_pieces_of_color(board, color):
    pieces = []
    for i in range(8):
        for j in range(8):
            if board[i][j] != "" and board[i][j] != "♔" and board[i][j] != "♚" and same_color(board[i][j], color):
                pieces.append((board[i][j], [j, i]))
    return pieces


# returns the true or false value representing whether there is a draw by insufficient material
def check_draw_by_insufficient_material(board):
    # draws by lack of material:
    # King vs King
    # King + Bishop vs King
    # King + Knight vs King
    # King + Bishop vs King + Bishop
    # King + Knight vs King + Knight
    # King + Bishop vs King + Knight
    # King vs Bishops of same square complex
    # overall to keep playing:
    # must have one major piece or two minor pieces (if bishops, can't be same complex)
    # I am making the preferential choice of no auto-draw in NNK vs K
    pieces_on_board = get_pieces_on_board(board)
    major_pieces = ["♖", "♜", "♕", "♛", "♙", "♟"]
    minor_pieces = ["♗", "♝", "♘", "♞"]
    for M in major_pieces:
        if M in pieces_on_board:
            return False
    num_white_bishops = 0
    num_white_knights = 0
    num_black_bishops = 0
    num_black_knights = 0
    for piece in pieces_on_board:
        if piece == "♝":
            num_white_bishops += 1
        elif piece == "♞":
            num_white_knights += 1
        elif piece == "♗":
            num_black_bishops += 1
        elif piece == "♘":
            num_black_knights += 1
    # if enough minor pieces to mate
    if num_white_bishops + num_white_knights >= 2:
        # if only bishops, check complexes
        if num_white_knights == 0:
            even_bishops = 0
            odd_bishops = 0
            for i in range(8):
                for j in range(8):
                    if board[i][j] == "♝":
                        if i + j % 2 == 0:
                            even_bishops += 1
                        else:
                            odd_bishops += 1
            if even_bishops is not 0 and odd_bishops is not 0:
                return False
        # if at least one knight among 2 minor pieces, no draw
        else:
            return False
    # if enough minor pieces to mate
    if num_black_bishops + num_black_knights >= 2:
        # if only bishops, check complexes
        if num_black_knights == 0:
            even_bishops = 0
            odd_bishops = 0
            for i in range(8):
                for j in range(8):
                    if board[i][j] == "♗":
                        if i + j % 2 == 0:
                            even_bishops += 1
                        else:
                            odd_bishops += 1
            if even_bishops is not 0 and odd_bishops is not 0:
                return False
        # if at least one knight among 2 minor pieces, no draw
        else:
            return False

    return True


# returns true if given piece has any legal move, else false
def piece_has_legal_move(board, piece, turn, color, location):
    if piece in ["♙", "♟"]:
        if color is "black":
            # try possible moves for a black pawn
            # single move
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] + 1, location[0]]):
                return True
            # double move
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] + 2, location[0]]):
                return True
            # takes left and right
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] + 1, location[0] - 1]):
                return True
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] + 1, location[0] + 1]):
                return True

        elif color == "white":
            # try possible moves for a white pawn
            # single move
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] - 1, location[0]]):
                return True
            # double move
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] - 2, location[0]]):
                return True
            # takes left and right
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] - 1, location[0] - 1]):
                return True
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [location[1] - 1, location[0] + 1]):
                return True
        else:
            return False

    if piece in ["♘", "♞"]:
        for i in [1, 2, -1, -2]:
            for j in [1, 2, -1, -2]:
                if abs(i) != abs(j):
                    if is_move_legal(board, turn, piece, color, [location[1], location[0]], [i, j]):
                        return True

    if piece in ["♕", "♛", "♗", "♝", "♖", "♜"]:
        # get potential moves
        atked_squares = get_attacked_squares(board, piece, location)
        # see if any of these potential moves are valid
        for square in atked_squares:
            # check if move is legal for each possible move
            if is_move_legal(board, turn, piece, color, [location[1], location[0]], [square[1], square[0]]):
                return True

    # if this point is reached, no legal move was found
    return False


# returns true if king is in stalemate (no legal moves) but king not under attack
def check_draw_by_stalemate(board, turn, color):
    # find the king in question
    king_loc = find_king(board, color)
    kingx = king_loc[0]
    kingy = king_loc[1]
    # see if king is in check
    if in_check:
        return False

    # check for all possible king moves
    for i in [0, 1, -1]:
        for j in [0, 1, -1]:
            if not (i == 0 and j == 0):
                if is_move_legal(board, turn, get_piece_at(board, king_loc), color, king_loc, [kingx + i, kingy + j]):
                    return False

    # if we get past this, king has no legal moves

    # check for other pieces
    for color_piece in pieces_of_color(color):
        # if other pieces of same color to king exist
        pieces_on_board = get_pieces_on_board(board)
        if color_piece in pieces_on_board:
            # then we have other pieces to check legal moves for
            # get these pieces
            pieces_and_location = get_pieces_of_color(board, color)

            # now we have all pieces of color not including king
            # loop through these pieces checking for legal moves
            for pl in pieces_and_location:
                if piece_has_legal_move(board, pl[0], turn, color, pl[1]):
                    return False

        # otherwise king has no legal moves, and no other pieces exist
        else:
            return True

        # if we reach here then no pieces of color have legal moves
        return True


# returns true if no pawns moved and no pieces taken for 50 consecutive moves
def check_draw_by_50_move(board):
    if num_moves_since_takes >= 50 and num_moves_since_pawn_moved >= 50:
        return True
    else:
        return False


# check for stalemate, 50-move rule, repetition or not enough material left to possibly mate
# returns true if stalemate or repetition found, false otherwise
def check_draw(board, turn, color):
    # draw by insufficient material: not enough material left on the board for any possible checkmate
    draw_by_insufficient_material = check_draw_by_insufficient_material(board)
    # draw by repetition: same board position occurs 3 times
    draw_by_repetition = log_position(board)
    # draw by 50-move rule: No pawn moves and no pieces taken for 50 consecutive moves
    draw_by_50_move_rule = check_draw_by_50_move(board)
    # draw by stalemate: color has no legal moves and king of color is not in check
    draw_by_stalemate = check_draw_by_stalemate(board, turn, color)

    return draw_by_insufficient_material or draw_by_repetition or draw_by_50_move_rule or draw_by_stalemate


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

        # tracking of whether pieces have moved (for castling)
        a1_rook_moved = False
        h1_rook_moved = False
        a8_rook_moved = False
        h8_rook_moved = False
        black_king_moved = False
        white_king_moved = False

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
                color = "white" if turn % 2 == 0 else "black"
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
                elif move_msg.content == "decline" and draw_proposed:
                    draw_proposed = False
                    draw_msg = "declines to draw"
                    await interaction.followup.send(f"{print_board(board)}\n{players[turn % 2].mention} {draw_msg}.")
                    return

                # check for checkmates or resignations
                elif check_win(board, color) or move_msg.content == "resign":
                    await interaction.followup.send(f"{print_board(board)}\n✅ {players[turn % 2].mention} wins! 🎉")
                    return

                # check for draw
                elif check_draw(board, turn, color) or (draw_proposed and move_msg.content == "accept"):
                    await interaction.followup.send(f"{print_board(board)}\nIt's a draw!")
                    return

                # actually makes the move specified by user
                else:
                    parsed_message = parse_notation(board, move_msg.content, turn)
                    make_move(board, color, turn, parsed_message[0], parsed_message[1], parsed_message[2], True)

                # reset necessary globals
                q_castling = False
                k_castling = False
                en_passant = False
                promotion_type = "X"

                # no longer in check if was
                in_check = False

                # increment turn based vals
                num_moves_since_takes += 1
                num_moves_since_pawn_moved += 1
                turn += 1

                await interaction.followup.send(f"{print_board(board)}\n{players[turn % 2].mention}, it's your turn!")
            except TimeoutError:
                await interaction.followup.send("⌛ Game timed out!")
                return


async def setup(bot: commands.Bot):
    await bot.add_cog(MultiChess(bot))
