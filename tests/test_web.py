import json
import threading
import unittest
import urllib.error
import urllib.request

from connect4.web import BadRequest, board_from_moves, create_server, handle_play, winning_cells


class GameApiTests(unittest.TestCase):
    def test_rejects_invalid_move_lists(self):
        for moves in ("3", [3, "4"], [7], [-1], [True], [0] * 7):
            with self.subTest(moves=moves), self.assertRaises(BadRequest):
                board_from_moves(moves)

    def test_rejects_moves_after_game_over(self):
        with self.assertRaises(BadRequest):
            board_from_moves([0, 6, 1, 6, 2, 6, 3, 5])

    def test_rejects_unknown_difficulty(self):
        with self.assertRaises(BadRequest):
            handle_play({"moves": [], "difficulty": "impossible"})

    def test_winning_cells_marks_the_line(self):
        board = board_from_moves([0, 6, 1, 6, 2, 6, 3])
        self.assertEqual(winning_cells(board), [[0, 0], [1, 0], [2, 0], [3, 0]])

    def test_ai_replies_when_asked(self):
        state = handle_play({"moves": [3], "aiMove": True, "difficulty": "easy"})
        self.assertEqual(len(state["moves"]), 2)
        self.assertEqual(state["ai"]["move"], state["moves"][-1])
        self.assertIsNone(state["winner"])

    def test_ai_does_not_move_after_human_wins(self):
        state = handle_play({"moves": [0, 6, 1, 6, 2, 6, 3], "aiMove": True})
        self.assertEqual(state["winner"], 0)
        self.assertIsNone(state["ai"])
        self.assertEqual(len(state["winningCells"]), 4)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, path, body):
        request = urllib.request.Request(
            self.url + path, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def test_serves_front_end(self):
        for path in ("/", "/app.js", "/style.css"):
            with self.subTest(path=path), urllib.request.urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)

    def test_unknown_paths_are_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url + "/../board.py")
        self.assertEqual(caught.exception.code, 404)

    def test_play_endpoint(self):
        state = self.post("/api/play", {"moves": [], "aiMove": True, "difficulty": "easy"})
        self.assertEqual(state["moves"], [3])

    def test_bad_request_returns_400_with_message(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/play", {"moves": [9]})
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("Illegal move", json.load(caught.exception)["error"])


if __name__ == "__main__":
    unittest.main()
