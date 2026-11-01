"""Browser interface: a small HTTP server that serves the front end and runs the AI.

The server keeps no game state. The browser holds the game as a list of
moves and sends it with every request; the server rebuilds the board,
optionally lets the AI reply, and returns the new state. This keeps the
server simple and means any number of browser tabs can play at once.

Run with:  python3 -m connect4.web
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ai import DIFFICULTIES, AIPlayer, SearchResult
from .board import HEIGHT, WIDTH, Board, bit_index
from .evaluation import WIN_SCORE, WINDOWS

STATIC_DIR = Path(__file__).parent / "static"

# Only these files are served, so request paths can never reach other files.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

MAX_REQUEST_BYTES = 4096


class BadRequest(Exception):
    """The client sent something that isn't a valid game or setting."""


# ------------------------------------------------------------------ game API


def board_from_moves(moves: object) -> Board:
    """Rebuild a board from the client's move list, validating every move."""
    if not isinstance(moves, list):
        raise BadRequest("'moves' must be a list of column numbers")

    board = Board()
    for col in moves:
        if not isinstance(col, int) or isinstance(col, bool):
            raise BadRequest("'moves' must be a list of column numbers")
        if board.is_game_over():
            raise BadRequest("The game is already over")
        if not board.can_play(col):
            raise BadRequest(f"Illegal move: column {col}")
        board.play(col)
    return board


def winning_cells(board: Board) -> list[list[int]]:
    """[col, row] of every stone that is part of a winning line."""
    winner = board.winner()
    if winner is None:
        return []

    stones = board.stones(winner)
    cells = set()
    for window in WINDOWS:
        if stones & window == window:
            cells.update(
                (col, row)
                for col in range(WIDTH)
                for row in range(HEIGHT)
                if window >> bit_index(col, row) & 1
            )
    return [list(cell) for cell in sorted(cells)]


def describe_ai_move(result: SearchResult) -> dict:
    decided = result.is_forced_win or result.is_forced_loss
    return {
        "move": result.move,
        "score": result.score,
        "depth": result.depth,
        "nodes": result.nodes,
        "elapsed": result.elapsed,
        "forcedWin": result.is_forced_win,
        "forcedLoss": result.is_forced_loss,
        # Moves (plies) until the game ends, counting the AI's own move.
        "pliesToEnd": WIN_SCORE - abs(result.score) if decided else None,
    }


def handle_play(payload: dict) -> dict:
    """Validate the position, let the AI reply if asked, and return the new state."""
    board = board_from_moves(payload.get("moves", []))

    difficulty = payload.get("difficulty", "hard")
    if difficulty not in DIFFICULTIES:
        raise BadRequest(f"Unknown difficulty: {difficulty!r}")

    ai_move = None
    if payload.get("aiMove") and not board.is_game_over():
        result = AIPlayer(**DIFFICULTIES[difficulty]).choose_move(board)
        board.play(result.move)
        ai_move = describe_ai_move(result)

    return {
        "moves": board.moves,
        "winner": board.winner(),
        "isDraw": board.is_full() and board.winner() is None,
        "winningCells": winning_cells(board),
        "ai": ai_move,
    }


# ---------------------------------------------------------------- HTTP layer


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        entry = STATIC_FILES.get(self.path.split("?")[0])
        if entry is None:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        filename, content_type = entry
        self._send(HTTPStatus.OK, (STATIC_DIR / filename).read_bytes(), content_type)

    def do_POST(self) -> None:
        if self.path != "/api/play":
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            self._send_json(handle_play(self._read_json()))
        except BadRequest as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_REQUEST_BYTES:
            raise BadRequest("Request too large")
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            raise BadRequest("Request body must be JSON") from None
        if not isinstance(payload, dict):
            raise BadRequest("Request body must be a JSON object")
        return payload

    def _send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        pass  # keep the terminal quiet


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), RequestHandler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="connect4.web", description="Play Connect 4 against the AI in your browser."
    )
    parser.add_argument("--port", type=int, default=8000, help="port to listen on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = parser.parse_args(argv)

    try:
        server = create_server("127.0.0.1", args.port)
    except OSError:
        parser.exit(1, f"Port {args.port} is in use. Try: python3 -m connect4.web --port 8001\n")

    url = f"http://127.0.0.1:{args.port}"
    print(f"Connect 4 is running at {url}  (press Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
