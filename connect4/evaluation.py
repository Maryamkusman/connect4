"""Static evaluation: a heuristic score for non-terminal positions.

The search can only look a limited number of moves ahead. When it reaches
that depth without the game ending, it asks this module "how good does this
position look?". The heuristic is built on *windows*: every group of four
cells that could form a winning line (there are 69 on a 7x6 board).

A window containing stones from both players can never be won, so it is
worth nothing. A window containing only one player's stones is a potential
line for that player, and is worth more the fuller it is.
"""

from __future__ import annotations

from .board import HEIGHT, WIDTH, Board, bit_index

# A forced win is worth far more than any heuristic score can add up to.
WIN_SCORE = 1_000_000

THREE_IN_WINDOW = 50   # three stones + one empty cell: a direct threat
TWO_IN_WINDOW = 10     # two stones + two empty cells
CENTER_STONE = 6       # centre stones take part in the most windows


def _build_windows() -> tuple[int, ...]:
    """Return a bitmask for every line of four cells on the board."""
    directions = ((1, 0), (0, 1), (1, 1), (1, -1))  # (d_col, d_row)
    windows = []
    for col in range(WIDTH):
        for row in range(HEIGHT):
            for d_col, d_row in directions:
                end_col, end_row = col + 3 * d_col, row + 3 * d_row
                if 0 <= end_col < WIDTH and 0 <= end_row < HEIGHT:
                    mask = 0
                    for step in range(4):
                        mask |= 1 << bit_index(col + step * d_col, row + step * d_row)
                    windows.append(mask)
    return tuple(windows)


WINDOWS = _build_windows()
CENTER_COLUMN_MASK = sum(1 << bit_index(WIDTH // 2, row) for row in range(HEIGHT))

_WINDOW_VALUE = {0: 0, 1: 0, 2: TWO_IN_WINDOW, 3: THREE_IN_WINDOW}


def evaluate(board: Board, player: int) -> int:
    """Score the position from `player`'s point of view (positive = good).

    The score is symmetric: evaluate(board, p) == -evaluate(board, 1 - p),
    which is what the negamax search relies on.
    """
    mine = board.stones(player)
    theirs = board.stones(1 - player)

    score = CENTER_STONE * (
        (mine & CENTER_COLUMN_MASK).bit_count() - (theirs & CENTER_COLUMN_MASK).bit_count()
    )

    for window in WINDOWS:
        my_count = (mine & window).bit_count()
        their_count = (theirs & window).bit_count()
        if their_count == 0:
            score += _WINDOW_VALUE[my_count]
        elif my_count == 0:
            score -= _WINDOW_VALUE[their_count]

    return score
