"""The computer opponent.

Three techniques are layered on top of each other:

1. Minimax, written in its *negamax* form. Connect 4 is zero-sum, so a
   position worth +X to one player is worth -X to the other. Instead of
   separate "maximise" and "minimise" branches, every node maximises the
   negation of its children's scores.

2. Alpha-beta pruning. `alpha` is the best score the side to move is already
   guaranteed elsewhere in the tree; `beta` is the best the opponent is
   guaranteed. Once a move scores >= beta, the opponent would never allow
   this position, so the remaining moves need not be searched.

3. Iterative deepening. We search to depth 1, then 2, then 3, ... until the
   time budget runs out, and keep the result of the last *completed*
   iteration. Each iteration records the best move found in every position,
   and the next iteration tries that move first, which makes alpha-beta
   prune far more.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .board import CELLS, WIDTH, Board
from .evaluation import WIN_SCORE, evaluate

INFINITY = WIN_SCORE + 1

# AIPlayer keyword arguments for each named difficulty, shared by all UIs.
DIFFICULTIES = {
    "easy": {"max_depth": 2},
    "medium": {"max_depth": 5},
    "hard": {"time_limit": 2.0},
}

# Centre columns belong to more possible lines, so they are usually stronger.
CENTER_FIRST_ORDER = tuple(sorted(range(WIDTH), key=lambda col: abs(col - WIDTH // 2)))

# Reading the clock is relatively slow, so only do it every N nodes.
_NODES_PER_TIME_CHECK = 1024


class _SearchTimeout(Exception):
    """Raised inside the search when the time budget is exhausted."""


@dataclass(frozen=True)
class SearchResult:
    move: int        # column chosen (0-indexed)
    score: int       # evaluation from the AI's point of view
    depth: int       # deepest fully completed search
    nodes: int       # positions visited across all iterations
    elapsed: float   # seconds spent thinking

    @property
    def is_forced_win(self) -> bool:
        return self.score >= WIN_SCORE - CELLS

    @property
    def is_forced_loss(self) -> bool:
        return self.score <= -(WIN_SCORE - CELLS)


class AIPlayer:
    """Chooses moves using iterative-deepening negamax with alpha-beta pruning.

    Args:
        max_depth: never search deeper than this many plies.
        time_limit: stop deepening after this many seconds (None = no limit).
    """

    def __init__(self, max_depth: int = CELLS, time_limit: float | None = None) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be at least 1")
        self.max_depth = max_depth
        self.time_limit = time_limit
        self._best_moves: dict[tuple[int, int], int] = {}
        self._nodes = 0
        self._deadline: float | None = None

    def choose_move(self, board: Board) -> SearchResult:
        """Return the best move found for the player to move on `board`."""
        if board.is_game_over():
            raise ValueError("The game is already over")

        # Search a private copy: a timeout can abort mid-search, leaving
        # moves played that were never undone.
        board = board.copy()
        start = time.perf_counter()
        self._deadline = start + self.time_limit if self.time_limit else None
        self._nodes = 0
        self._best_moves = {}

        best_move = self._ordered_moves(board)[0]
        best_score = 0
        completed_depth = 0
        depth_limit = min(self.max_depth, CELLS - board.move_count)

        for depth in range(1, depth_limit + 1):
            try:
                best_move, best_score = self._search_root(board, depth)
            except _SearchTimeout:
                break  # keep the result of the last completed depth
            completed_depth = depth
            if abs(best_score) >= WIN_SCORE - CELLS:
                break  # the outcome is already decided; deeper search won't change it

        return SearchResult(
            move=best_move,
            score=best_score,
            depth=completed_depth,
            nodes=self._nodes,
            elapsed=time.perf_counter() - start,
        )

    # ---------------------------------------------------------------- search

    def _search_root(self, board: Board, depth: int) -> tuple[int, int]:
        """Search every root move to `depth` and return (best move, score)."""
        alpha = -INFINITY
        best_move, best_score = -1, -INFINITY

        for col in self._ordered_moves(board):
            board.play(col)
            score = -self._negamax(board, depth - 1, -INFINITY, -alpha, ply=1)
            board.undo()

            if score > best_score:
                best_move, best_score = col, score
            alpha = max(alpha, score)

        self._best_moves[board.key()] = best_move
        return best_move, best_score

    def _negamax(self, board: Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        """Score `board` from the point of view of the player to move.

        `ply` is the distance from the root. Wins are scored as
        WIN_SCORE - ply so that the AI prefers faster wins and slower losses.
        """
        self._check_time()

        if board.last_move_won():
            return -(WIN_SCORE - ply)  # the opponent just won
        if board.is_full():
            return 0
        if depth == 0:
            return evaluate(board, board.current_player)

        best_move, best_score = -1, -INFINITY
        for col in self._ordered_moves(board):
            board.play(col)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.undo()

            if score > best_score:
                best_move, best_score = col, score
            alpha = max(alpha, score)
            if alpha >= beta:
                break  # cutoff: the opponent will avoid this position

        self._best_moves[board.key()] = best_move
        return best_score

    # --------------------------------------------------------------- helpers

    def _ordered_moves(self, board: Board) -> list[int]:
        """Legal moves, best guesses first.

        The best move from the previous iteration goes first; the rest are
        ordered from the centre outwards.
        """
        moves = [col for col in CENTER_FIRST_ORDER if board.can_play(col)]
        previous_best = self._best_moves.get(board.key())
        if previous_best in moves:
            moves.remove(previous_best)
            moves.insert(0, previous_best)
        return moves

    def _check_time(self) -> None:
        self._nodes += 1
        if (
            self._deadline is not None
            and self._nodes % _NODES_PER_TIME_CHECK == 0
            and time.perf_counter() > self._deadline
        ):
            raise _SearchTimeout
