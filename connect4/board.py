"""Connect 4 board represented as a pair of bitboards.

Bit layout
----------
Each column is stored as HEIGHT + 1 consecutive bits. The extra bit at the
top of every column is a permanently empty *sentinel*: it stops a line of
stones from "wrapping" from the top of one column into the bottom of the
next when we shift bits during win detection.

    col:  0  1  2  3  4  5  6
          6 13 20 27 34 41 48   <- sentinel row (always 0)
          5 12 19 26 33 40 47   <- top row
          4 11 18 25 32 39 46
          3 10 17 24 31 38 45
          2  9 16 23 30 37 44
          1  8 15 22 29 36 43
          0  7 14 21 28 35 42   <- bottom row

    bit index = col * (HEIGHT + 1) + row
"""

from __future__ import annotations

from typing import Iterable

WIDTH = 7
HEIGHT = 6
COLUMN_BITS = HEIGHT + 1  # includes the sentinel bit
CELLS = WIDTH * HEIGHT

# Bit shifts that move one step along each of the four line directions.
_DIRECTIONS = (
    1,                # vertical
    COLUMN_BITS,      # horizontal
    COLUMN_BITS - 1,  # diagonal going down-right  (\)
    COLUMN_BITS + 1,  # diagonal going up-right    (/)
)


def bit_index(col: int, row: int) -> int:
    """Return the bit position of the cell at (col, row); row 0 is the bottom."""
    return col * COLUMN_BITS + row


class Board:
    """Mutable Connect 4 position with O(1) play/undo.

    Players are numbered 0 (moves first) and 1. Columns are 0-indexed.
    """

    def __init__(self) -> None:
        self._bitboards = [0, 0]                                  # stones per player
        self._heights = [bit_index(c, 0) for c in range(WIDTH)]  # next free bit per column
        self._moves: list[int] = []                               # column history, for undo

    @classmethod
    def from_moves(cls, columns: Iterable[int]) -> Board:
        """Build a position by playing the given columns in order."""
        board = cls()
        for col in columns:
            board.play(col)
        return board

    def copy(self) -> Board:
        clone = Board()
        clone._bitboards = self._bitboards.copy()
        clone._heights = self._heights.copy()
        clone._moves = self._moves.copy()
        return clone

    # ------------------------------------------------------------------ state

    @property
    def current_player(self) -> int:
        """The player whose turn it is (0 or 1)."""
        return len(self._moves) & 1

    @property
    def move_count(self) -> int:
        return len(self._moves)

    @property
    def moves(self) -> list[int]:
        """Columns played so far, in order."""
        return self._moves.copy()

    @property
    def last_move(self) -> int | None:
        return self._moves[-1] if self._moves else None

    def stones(self, player: int) -> int:
        """Bitboard of the given player's stones."""
        return self._bitboards[player]

    def key(self) -> tuple[int, int]:
        """Hashable identifier of the position (used for caching)."""
        return self._bitboards[0], self._bitboards[1]

    def cell(self, col: int, row: int) -> int | None:
        """Return the player occupying (col, row), or None if empty."""
        bit = 1 << bit_index(col, row)
        if self._bitboards[0] & bit:
            return 0
        if self._bitboards[1] & bit:
            return 1
        return None

    # ------------------------------------------------------------------ moves

    def can_play(self, col: int) -> bool:
        return 0 <= col < WIDTH and self._heights[col] < bit_index(col, HEIGHT)

    def legal_moves(self) -> list[int]:
        return [col for col in range(WIDTH) if self.can_play(col)]

    def play(self, col: int) -> None:
        """Drop a stone for the current player into `col`."""
        if not self.can_play(col):
            raise ValueError(f"Column {col} is full or out of range")
        self._bitboards[self.current_player] |= 1 << self._heights[col]
        self._heights[col] += 1
        self._moves.append(col)

    def undo(self) -> None:
        """Take back the most recent move."""
        col = self._moves.pop()
        self._heights[col] -= 1
        # After popping, current_player is the player who made that move.
        self._bitboards[self.current_player] ^= 1 << self._heights[col]

    # ------------------------------------------------------------- game end

    def has_won(self, player: int) -> bool:
        """True if `player` has four in a row anywhere on the board.

        For each direction, `pairs` marks every stone that has a neighbour one
        step further along. If a pair is followed by another pair two steps
        further along, that is four in a row.
        """
        stones = self._bitboards[player]
        for shift in _DIRECTIONS:
            pairs = stones & (stones >> shift)
            if pairs & (pairs >> (2 * shift)):
                return True
        return False

    def last_move_won(self) -> bool:
        """True if the player who just moved completed four in a row."""
        return bool(self._moves) and self.has_won(1 - self.current_player)

    def is_full(self) -> bool:
        return len(self._moves) == CELLS

    def is_game_over(self) -> bool:
        return self.last_move_won() or self.is_full()

    def winner(self) -> int | None:
        """The winning player, or None if nobody has won (yet)."""
        return 1 - self.current_player if self.last_move_won() else None
