import unittest

from connect4.ai import AIPlayer
from connect4.board import Board


class AITests(unittest.TestCase):
    def test_takes_immediate_win(self):
        # Player 0 has three in a row on the bottom (columns 0-2).
        board = Board.from_moves([0, 6, 1, 6, 2, 5])
        result = AIPlayer(max_depth=4).choose_move(board)
        self.assertEqual(result.move, 3)
        self.assertTrue(result.is_forced_win)

    def test_blocks_immediate_loss(self):
        # Player 0 threatens column 3; player 1 (the AI) must block.
        board = Board.from_moves([0, 6, 1, 6, 2])
        result = AIPlayer(max_depth=4).choose_move(board)
        self.assertEqual(result.move, 3)

    def test_finds_win_in_two_moves(self):
        # Two stones in columns 2-3 on an empty bottom row: playing column 1
        # or 4 makes an open-ended three that cannot be stopped.
        board = Board.from_moves([2, 2, 3, 3])
        result = AIPlayer(max_depth=6).choose_move(board)
        self.assertIn(result.move, (1, 4))
        self.assertTrue(result.is_forced_win)

    def test_prefers_centre_on_empty_board(self):
        result = AIPlayer(max_depth=4).choose_move(Board())
        self.assertEqual(result.move, 3)

    def test_respects_time_limit(self):
        result = AIPlayer(time_limit=0.3).choose_move(Board())
        self.assertLess(result.elapsed, 1.0)
        self.assertGreaterEqual(result.depth, 1)

    def test_does_not_modify_callers_board(self):
        board = Board.from_moves([3, 3, 2])
        key = board.key()
        AIPlayer(time_limit=0.2).choose_move(board)
        self.assertEqual(board.key(), key)

    def test_only_legal_moves_returned(self):
        board = Board.from_moves([3] * 6)
        result = AIPlayer(max_depth=3).choose_move(board)
        self.assertNotEqual(result.move, 3)

    def test_rejects_finished_game(self):
        board = Board.from_moves([0, 6, 1, 6, 2, 6, 3])
        with self.assertRaises(ValueError):
            AIPlayer().choose_move(board)


if __name__ == "__main__":
    unittest.main()
