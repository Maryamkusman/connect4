import unittest

from connect4.board import CELLS, HEIGHT, WIDTH, Board
from connect4.evaluation import WINDOWS, evaluate


class BoardTests(unittest.TestCase):
    def test_new_board_is_empty(self):
        board = Board()
        self.assertEqual(board.current_player, 0)
        self.assertEqual(board.legal_moves(), list(range(WIDTH)))
        self.assertFalse(board.is_game_over())

    def test_stones_stack_from_the_bottom(self):
        board = Board.from_moves([3, 3])
        self.assertEqual(board.cell(3, 0), 0)
        self.assertEqual(board.cell(3, 1), 1)
        self.assertIsNone(board.cell(3, 2))

    def test_full_column_rejects_moves(self):
        board = Board.from_moves([0] * HEIGHT)
        self.assertFalse(board.can_play(0))
        self.assertNotIn(0, board.legal_moves())
        with self.assertRaises(ValueError):
            board.play(0)

    def test_out_of_range_column_rejected(self):
        board = Board()
        self.assertFalse(board.can_play(-1))
        self.assertFalse(board.can_play(WIDTH))

    def test_undo_restores_position(self):
        board = Board.from_moves([3, 2, 3])
        key = board.key()
        board.play(4)
        board.undo()
        self.assertEqual(board.key(), key)
        self.assertEqual(board.current_player, 1)

    def test_horizontal_win(self):
        board = Board.from_moves([0, 0, 1, 1, 2, 2, 3])
        self.assertEqual(board.winner(), 0)

    def test_vertical_win(self):
        board = Board.from_moves([4, 5, 4, 5, 4, 5, 4])
        self.assertEqual(board.winner(), 0)

    def test_rising_diagonal_win(self):
        board = Board.from_moves([0, 1, 1, 2, 2, 3, 2, 3, 3, 6, 3])
        self.assertEqual(board.winner(), 0)

    def test_falling_diagonal_win(self):
        board = Board.from_moves([6, 5, 5, 4, 4, 3, 4, 3, 3, 0, 3])
        self.assertEqual(board.winner(), 0)

    def test_no_wrap_between_columns(self):
        # Player 0 holds the top three cells of column 0 and the bottom cell
        # of column 1. Those bits are adjacent apart from the sentinel bit,
        # which must stop them counting as a vertical four.
        board = Board.from_moves([1, 0, 2, 0, 2, 0, 2, 1, 0, 6, 0, 6, 0, 1])
        self.assertEqual([board.cell(0, row) for row in range(HEIGHT)], [1, 1, 1, 0, 0, 0])
        self.assertEqual(board.cell(1, 0), 0)
        self.assertFalse(board.has_won(0))

    def test_full_board_without_four_is_a_draw(self):
        drawn_game = [
            3, 0, 3, 0, 0, 0, 3, 0, 4, 0, 6, 1, 1, 2, 1, 1, 1, 1, 2, 2, 2,
            3, 2, 3, 2, 4, 3, 5, 4, 6, 5, 6, 5, 5, 4, 5, 4, 4, 6, 6, 6, 5,
        ]
        board = Board.from_moves(drawn_game)
        self.assertEqual(board.move_count, CELLS)
        self.assertTrue(board.is_full())
        self.assertTrue(board.is_game_over())
        self.assertIsNone(board.winner())
        self.assertEqual(board.legal_moves(), [])


class EvaluationTests(unittest.TestCase):
    def test_board_has_69_winning_lines(self):
        self.assertEqual(len(WINDOWS), 69)

    def test_evaluation_is_symmetric(self):
        board = Board.from_moves([3, 2, 3, 4, 1])
        self.assertEqual(evaluate(board, 0), -evaluate(board, 1))

    def test_centre_is_preferred(self):
        centre = Board.from_moves([3])
        edge = Board.from_moves([0])
        self.assertGreater(evaluate(centre, 0), evaluate(edge, 0))


if __name__ == "__main__":
    unittest.main()
