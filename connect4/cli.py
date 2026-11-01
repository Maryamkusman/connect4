"""Terminal interface: play Connect 4 against the AI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from .ai import DIFFICULTIES, AIPlayer, SearchResult
from .board import HEIGHT, WIDTH, Board

HELP_TEXT = f"Enter a column 1-{WIDTH}, 'u' to undo your last move, or 'q' to quit."


@dataclass(frozen=True)
class Style:
    """How stones are drawn. Players 0 and 1 map to index 0 and 1."""

    stones: tuple[str, str]

    @classmethod
    def create(cls, use_color: bool) -> Style:
        if use_color:
            red, yellow, reset = "\033[91m", "\033[93m", "\033[0m"
            return cls(stones=(f"{red}●{reset}", f"{yellow}●{reset}"))
        return cls(stones=("X", "O"))


def render(board: Board, style: Style) -> str:
    """Draw the board as text, top row first."""
    lines = []
    for row in reversed(range(HEIGHT)):
        cells = []
        for col in range(WIDTH):
            player = board.cell(col, row)
            cells.append("." if player is None else style.stones[player])
        lines.append("| " + " ".join(cells) + " |")
    lines.append("+" + "-" * (2 * WIDTH + 1) + "+")
    lines.append("  " + " ".join(str(col + 1) for col in range(WIDTH)))

    if board.last_move is not None:
        marker = [" "] * WIDTH
        marker[board.last_move] = "^"
        lines.append("  " + " ".join(marker))
    return "\n".join(lines)


def describe_search(result: SearchResult) -> str:
    if result.is_forced_win:
        outlook = "I have a forced win"
    elif result.is_forced_loss:
        outlook = "you can force a win"
    else:
        outlook = f"eval {result.score:+d}"
    return (
        f"AI plays column {result.move + 1} "
        f"(depth {result.depth}, {result.nodes:,} positions, "
        f"{result.elapsed:.2f}s, {outlook})"
    )


def read_human_command(board: Board) -> str | int:
    """Prompt until the user enters a legal column, 'u' or 'q'.

    Returns the 0-indexed column, or the command letter.
    """
    while True:
        try:
            text = input("Your move: ").strip().lower()
        except EOFError:
            return "q"
        if text in ("q", "u"):
            return text
        if text.isdigit() and board.can_play(int(text) - 1):
            return int(text) - 1
        print(f"Invalid input. {HELP_TEXT}")


def play_game(ai: AIPlayer, human_player: int, style: Style) -> None:
    board = Board()
    print(f"\nYou play {style.stones[human_player]}. {HELP_TEXT}")

    while not board.is_game_over():
        print("\n" + render(board, style))

        if board.current_player == human_player:
            command = read_human_command(board)
            if command == "q":
                print("Goodbye!")
                return
            if command == "u":
                undo_human_turn(board, human_player)
                continue
            board.play(command)
        else:
            print("AI is thinking...")
            result = ai.choose_move(board)
            board.play(result.move)
            print(describe_search(result))

    print("\n" + render(board, style))
    winner = board.winner()
    if winner is None:
        print("It's a draw!")
    elif winner == human_player:
        print("You win! Congratulations.")
    else:
        print("The AI wins.")


def undo_human_turn(board: Board, human_player: int) -> None:
    """Undo moves until it is the human's turn again, with one human move removed."""
    if board.move_count == 0 or (board.move_count == 1 and human_player == 1):
        print("Nothing to undo.")
        return
    board.undo()
    while board.current_player != human_player:
        board.undo()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="connect4",
        description="Play Connect 4 against a minimax AI with alpha-beta pruning.",
    )
    parser.add_argument(
        "--difficulty", choices=DIFFICULTIES, default="hard",
        help="AI strength (default: hard)",
    )
    parser.add_argument(
        "--time", type=float, metavar="SECONDS",
        help="AI thinking time per move; overrides --difficulty",
    )
    parser.add_argument(
        "--first", choices=("human", "ai"), default="human",
        help="who moves first (default: human)",
    )
    parser.add_argument("--no-color", action="store_true", help="disable coloured output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = {"time_limit": args.time} if args.time else DIFFICULTIES[args.difficulty]
    ai = AIPlayer(**settings)
    human_player = 0 if args.first == "human" else 1

    try:
        play_game(ai, human_player, Style.create(use_color=not args.no_color))
    except KeyboardInterrupt:
        print("\nGoodbye!")
