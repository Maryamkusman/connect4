# Connect 4 AI

Play Connect 4 against a computer opponent that uses **minimax**,
**alpha-beta pruning** and **iterative deepening**, in your browser or your
terminal.

Pure Python and the standard library only. Nothing to install.
<img width="1770" height="869" alt="image" src="https://github.com/user-attachments/assets/766ce651-cb7c-4a59-8566-503ad9d43513" />


```
AI plays column 5 (depth 12, 667,648 positions, 2.00s, eval -40)

| . . . . . . . |
| . . . . . . . |
| . . . . . . . |
| . . . . . . . |
| . . . O . . . |
| . . X X O . . |
+---------------+
  1 2 3 4 5 6 7
          ^
Your move:
```

## Requirements

- Python 3.10 or newer

## Quick start: browser

```bash
git clone <this repo>
cd connect4
python3 -m connect4.web
```

This starts a local server and opens the game at <http://127.0.0.1:8000>.
Click a column (or press `1`–`7`) to drop a disc. The side panel lets you pick
the difficulty and your colour, and shows the AI's analysis after each move:
who it thinks is winning, how far ahead it looked, and how many positions it
checked. Press `Ctrl+C` in the terminal to stop the server.

Use `--port 8001` if port 8000 is taken, or `--no-browser` to skip opening a
tab.

## Quick start: terminal

```bash
python3 -m connect4
```

Enter a column number (`1`–`7`) to drop a stone, `u` to undo your last move,
or `q` to quit.

## Terminal options

| Flag | Description | Default |
|------|-------------|---------|
| `--difficulty {easy,medium,hard}` | AI strength (see below) | `hard` |
| `--time SECONDS` | Thinking time per move. Overrides `--difficulty` | – |
| `--first {human,ai}` | Who moves first | `human` |
| `--no-color` | Use `X` / `O` instead of coloured stones | off |

| Difficulty | How it searches |
|------------|-----------------|
| easy   | Looks 2 moves ahead |
| medium | Looks 5 moves ahead |
| hard   | Searches as deep as it can in 2 seconds (usually 10–14 moves) |

Examples:

```bash
python3 -m connect4 --difficulty easy
python3 -m connect4 --first ai --time 5
```

After each move the AI reports what it found: how deep it searched, how many
positions it looked at, and its evaluation. A positive evaluation means the AI
thinks it is ahead. When it can prove the result, it says
`I have a forced win` or `you can force a win`.

## How the AI works

1. **Minimax (negamax form)**: looks at every possible sequence of moves and
   assumes both sides play their best. Because the game is zero-sum, a single
   function serves both players: a score of +X for one side is -X for the other.
2. **Alpha-beta pruning**: skips branches that can't change the decision,
   because the opponent already has a better option elsewhere.
3. **Iterative deepening**: searches 1 move deep, then 2, then 3, until time
   runs out. This makes a time limit possible, and the best moves from each
   pass are tried first in the next, which makes pruning much more effective.
4. **Heuristic evaluation**: when the search stops before the game ends, it
   scores the position by counting the possible four-in-a-row lines each
   player could still complete.
5. **Bitboards**: the board is stored as two integers, so playing a move,
   undoing it and checking for a win each take a few bit operations.

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) has the full design walkthrough.

## Deploying

The browser version runs on any host that can run a Python web process. On
[Render](https://render.com), create a free **Web Service** from this repo with:

| Setting | Value |
|---------|-------|
| Runtime | Python |
| Build command | `pip install -r requirements.txt` (there are no dependencies) |
| Start command | `python3 -m connect4.web --host 0.0.0.0 --port $PORT --no-browser` |

`--host 0.0.0.0` accepts connections from outside the machine, and `--port`
uses the port the platform provides (the server also reads `$PORT` by itself).

## Project structure

```
connect4/
├── board.py        # Bitboard game state: play, undo, win detection
├── evaluation.py   # Heuristic scoring of non-final positions
├── ai.py           # Negamax + alpha-beta + iterative deepening
├── cli.py          # Terminal UI and argument parsing
├── web.py          # HTTP server + JSON API for the browser UI
├── static/         # Browser front end (HTML, CSS, JavaScript)
└── __main__.py     # Entry point for `python -m connect4`
tests/
├── test_board.py   # Rules, win detection, evaluation
├── test_ai.py      # AI takes wins, blocks losses, respects time limits
└── test_web.py     # API validation and HTTP endpoints
docs/
└── ARCHITECTURE.md # Design document
```

## Running the tests

```bash
python3 -m unittest -v
```

## Using the engine from code

```python
from connect4 import AIPlayer, Board

board = Board.from_moves([3, 3, 2])   # columns are 0-indexed
result = AIPlayer(time_limit=1.0).choose_move(board)
print(result.move, result.score, result.depth)
```
