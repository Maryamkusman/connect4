"""Connect 4 with a minimax / alpha-beta / iterative-deepening AI."""

from .ai import AIPlayer, SearchResult
from .board import CELLS, HEIGHT, WIDTH, Board

__all__ = ["AIPlayer", "Board", "SearchResult", "CELLS", "HEIGHT", "WIDTH"]
