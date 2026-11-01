# Connect 4 AI: Architecture

This document explains how the project is built and why. It goes from the
high-level design down to each algorithm, then covers trade-offs, known
limitations, and questions an interviewer is likely to ask.

---

## 1. The 30-second summary

> "I built a Connect 4 engine in Python. The board is a bitboard (two
> integers), so moves, undo and win detection are a few bit operations each.
> The AI uses minimax in its negamax form with alpha-beta pruning, wrapped in
> iterative deepening so it can play under a time limit. Iterative deepening
> also improves move ordering: the best move from each shallower search is
> tried first in the next one, which makes alpha-beta prune much more. When
> the search can't reach the end of the game, a heuristic scores positions by
> counting the four-in-a-row lines each player could still complete. In 2
> seconds it searches about 12 moves ahead and around 600,000 positions.
> You can play it in the terminal or in a browser. The browser front end talks
> to a small stateless JSON API, and the engine code didn't change at all
> when I added it."

---

## 2. Module layout

```
   Browser (static/: HTML + CSS + JS)
          │  JSON over HTTP  (POST /api/play)
          ▼
   ┌───────────┐        ┌───────────┐
   │  web.py   │        │  cli.py   │   Two interchangeable front ends
   └─────┬─────┘        └─────┬─────┘
         └─────────┬──────────┘
                   │ uses
       ┌───────────┴─────┐
       ▼                 ▼
 ┌───────────┐     ┌───────────┐
 │  ai.py    │────▶│ board.py  │  Game rules and state (no I/O, no AI)
 └─────┬─────┘     └───────────┘
       │ uses            ▲
       ▼                 │
 ┌───────────────┐       │
 │ evaluation.py │───────┘     Heuristic scoring
 └───────────────┘
```

Each module has one job, and dependencies point one way:

| Module | Responsibility | Knows about |
|--------|----------------|-------------|
| `board.py` | Rules: legal moves, playing, undo, win/draw detection | Nothing else |
| `evaluation.py` | "How good is this position?" for unfinished games | `board` |
| `ai.py` | Search: choosing the best move | `board`, `evaluation` |
| `cli.py` | Terminal front end | `board`, `ai` |
| `web.py` | HTTP server and JSON API for the browser | `board`, `ai`, `evaluation` |
| `static/` | Browser front end: drawing, animation, input | Only the JSON API |

**Why this matters:** the engine (`board`, `evaluation`, `ai`) knows nothing
about terminals or browsers. That's why adding the web UI needed **no changes
to the search or the rules**, only a new front-end module. The board can be
tested on its own, and the evaluation function can be swapped without touching
the search.

---

## 3. Board representation: bitboards

### The idea

Instead of a 6×7 grid of cells, each player's stones are stored as one
integer, with one bit per cell. A cell's bit is 1 if that player has a stone
there.

```
bit index = column * 7 + row      (row 0 is the bottom)

  col:  0  1  2  3  4  5  6
        6 13 20 27 34 41 48   <- sentinel row (always empty)
        5 12 19 26 33 40 47   <- top row
        4 11 18 25 32 39 46
        3 10 17 24 31 38 45
        2  9 16 23 30 37 44
        1  8 15 22 29 36 43
        0  7 14 21 28 35 42   <- bottom row
```

Each column uses **7 bits for 6 rows**. The extra bit at the top (the
*sentinel*) is never set. The next section shows why it's needed.

State held by `Board`:

- `_bitboards[2]`: one integer per player
- `_heights[7]`: the bit index of the next free cell in each column
- `_moves`: list of columns played, so moves can be undone

### Playing and undoing a move: O(1)

```python
self._bitboards[player] |= 1 << self._heights[col]   # set the bit
self._heights[col] += 1                               # column is one taller
```

Undo reverses those two steps. The search plays and undoes a move at every
node instead of copying the board, which saves a lot of memory allocation.

### Win detection with bit shifts

To find four in a row in some direction, shift the board by the distance
between neighbouring cells in that direction:

| Direction | Shift |
|-----------|-------|
| Vertical (up) | 1 |
| Horizontal (right) | 7 |
| Diagonal `/` | 8 (one column right, one row up) |
| Diagonal `\` | 6 (one column right, one row down) |

```python
pairs = stones & (stones >> shift)        # stones with a neighbour in this direction
if pairs & (pairs >> 2 * shift):          # a pair followed by another pair
    return True                           # = four in a row
```

That's 4 directions × 3 operations, with no loops over cells.

**Why the sentinel bit:** if each column used only 6 bits, the top cell of
column 0 (bit 5) and the bottom cell of column 1 (bit 6) would be adjacent
bits, and a vertical shift would treat them as stacked. Because the sentinel is always 0, every line that
crosses it is broken. A unit test (`test_no_wrap_between_columns`) checks this.

### Trade-off

A bitboard is harder to read than a 2D list. I chose it because the search
calls `play`, `undo` and `last_move_won` hundreds of thousands of times per
move, and in Python a few integer operations are much faster than looping over
cells. The extra complexity stays inside `board.py`, and the other modules
use readable methods like `cell(col, row)`.

---

## 4. The search algorithm

### 4.1 Minimax

Connect 4 is a two-player, zero-sum game with perfect information. Minimax
models it as a tree:

- Each **node** is a position; each **edge** is a move.
- On my turn I pick the child with the **max** score.
- On the opponent's turn they pick the child with the **min** score (they play
  as well as possible).
- **Leaves** are finished games (win/loss/draw) or positions where we stopped
  searching, which the heuristic scores.

### 4.2 Negamax: minimax with one function

In a zero-sum game, "the best score for me" equals "minus the best score for
my opponent". So instead of separate max and min branches:

```
score(position) = max over moves of ( -score(position after move) )
```

every score is "from the point of view of the player to move". It's the same
algorithm as minimax with half the code and no `if maximizing:` branches.
It needs a **symmetric** evaluation function:
`evaluate(board, p) == -evaluate(board, opponent)`, and there's a unit test
for that.

### 4.3 Alpha-beta pruning

Plain minimax looks at every node, about 7^depth of them. Alpha-beta skips
branches that can't affect the result.

Each call carries a window `[alpha, beta]`:

- **alpha**: the score the player to move is already guaranteed (from moves
  searched earlier). Anything ≤ alpha is no improvement.
- **beta**: the score the opponent is already guaranteed. If this position
  scores ≥ beta, the opponent will never let the game reach it.

```python
for col in ordered_moves:
    board.play(col)
    score = -negamax(board, depth - 1, -beta, -alpha, ply + 1)
    board.undo()
    best_score = max(best_score, score)
    alpha = max(alpha, score)
    if alpha >= beta:
        break          # beta cutoff: prune the remaining moves
```

The window is negated and swapped (`-beta, -alpha`) for the child because the
child scores from the opponent's point of view.

**Example of a cutoff:** I've found a move that guarantees me +5. Exploring
my second move, I see the opponent can answer with something that gives me
only +2. I don't need to look at their other replies: this move is already
worse than +5, so I won't choose it.

**Why move ordering matters:** alpha-beta always returns the same answer as
minimax, but how much it prunes depends on searching the best move first. With
perfect ordering it visits about `b^(d/2)` nodes instead of `b^d`, which lets
it search **twice as deep** in the same time. With bad ordering it prunes
almost nothing.

### 4.4 Iterative deepening

```python
for depth in 1, 2, 3, ...:
    try:
        best_move = search(depth)
    except Timeout:
        break                       # keep the last COMPLETED result
```

Two benefits:

1. **Time control.** We don't know in advance how deep we can go in 2 seconds.
   Iterative deepening always has a complete answer from the previous depth,
   so it can stop at any time. A search cut off halfway is thrown away,
   because only some root moves would have been checked.
2. **Better move ordering.** Each node's best move is stored in a dictionary
   (`_best_moves`, keyed by position). On the next, deeper iteration that move
   is tried first. The shallow search's best move is usually the deep search's
   best move too, so alpha-beta gets close to perfect ordering.

**"Isn't searching depths 1 to d-1 again wasteful?"** Very little. The tree
grows by about 7× per level, so all the shallower searches together cost a
fraction of the last one. The better ordering more than pays that back.

Other details:

- **Early exit:** if a forced win or loss is found, searching deeper won't
  change the result, so the search stops.
- **Depth cap:** never deeper than the number of empty cells.
- **Cheap clock checks:** the time is checked every 1,024 nodes, since reading
  the clock on every node would be slow.
- **Timeout via exception:** the deadline raises `_SearchTimeout`, which
  unwinds the whole recursion at once. The search runs on a **copy** of the
  board, so moves left un-undone by the exception don't affect the real game.

### 4.5 Move ordering

At each node, moves are tried in this order:

1. The best move remembered from the previous iteration (if any).
2. The rest, from the centre outwards: `3, 2, 4, 1, 5, 0, 6`.

Centre columns belong to more possible lines of four, so they are usually
stronger.

### 4.6 Scoring wins by distance

A win is scored `WIN_SCORE - ply`, where `ply` is the number of moves from the
current position. So:

- A win in 3 moves scores higher than a win in 7: **the AI finishes quickly**
  instead of wandering.
- A loss in 9 scores higher than a loss in 3: **when losing, the AI holds out
  as long as possible**, giving a human more chances to go wrong.

`WIN_SCORE` is 1,000,000, far above any heuristic score (at most a few
thousand), so a proven win always beats a good-looking position.

---

## 5. The evaluation function (heuristic)

Called at depth 0 when the game isn't over. It uses **windows**: every set of
4 cells in a line. A 7×6 board has 69 of them (24 horizontal, 21 vertical,
12 + 12 diagonal). They are calculated once as bitmasks when the module loads.

For each window:

| Contents | Score |
|----------|-------|
| Stones from both players | 0 (nobody can win there) |
| 3 of mine + 1 empty | +50 |
| 2 of mine + 2 empty | +10 |
| Same for the opponent | negative of the above |

Plus **+6 per stone in the centre column**.

Counting stones in a window is `(stones & window).bit_count()`, a single CPU
popcount.

**Trade-off:** this is simple and quick. It doesn't know about deeper
Connect 4 ideas like *odd/even threats* (which player will be forced to fill
the cell under a threat). That would be the next improvement.

---

## 6. Data flow for one AI move

```
cli.play_game()
  └─ ai.choose_move(board)
       ├─ board.copy()
       ├─ for depth = 1, 2, 3, ...
       │    └─ _search_root(depth)
       │         └─ for each move (ordered):
       │              play → _negamax(...) → undo
       │                       ├─ last move won?  → -(WIN - ply)
       │                       ├─ board full?     → 0
       │                       ├─ depth == 0?     → evaluate()
       │                       └─ recurse over children, alpha-beta cutoffs,
       │                          remember best move for the next iteration
       └─ return SearchResult(move, score, depth, nodes, elapsed)
  └─ board.play(result.move)
  └─ print stats
```

`SearchResult` is a frozen dataclass, so the UI can show what the AI found
(depth, node count, forced win or loss) without knowing how the search works.

---

## 7. The web front end

### Request flow

```
 Browser                                    web.py (Python)
 ───────                                    ───────────────
 user clicks column 3
 moves = [..., 3]; draw disc (animated)
 POST /api/play ─────────────────────────▶  rebuild Board from moves, checking each move
   {moves, aiMove: true, difficulty}        if the game isn't over:
                                              AIPlayer.choose_move(board)
                                              board.play(ai move)
                ◀─────────────────────────  {moves, winner, isDraw, winningCells,
 draw the AI's disc, update analysis         ai: {move, score, depth, nodes, elapsed, ...}}
 panel, highlight winning four
```

### Key design decision: a stateless server

The server stores **no games**. The browser keeps the game as a list of
columns played and sends the whole list with every request. The server
rebuilds the board (at most 42 moves, which takes microseconds), checks every
move is legal, runs the AI and returns the new state.

Why:

- **Simple:** no sessions, game IDs, cleanup or memory growth.
- **Robust:** restarting the server loses nothing; several tabs can play at once.
- **Safe:** the server never trusts the client. Every move is re-validated, so
  a tampered request gets a `400` with a clear message instead of a corrupt
  game.
- **Undo is free:** the browser just removes moves from its list.

The trade-off is a few hundred bytes of extra data per request, which doesn't
matter here.

### Other details

- **Standard library only:** `http.server.ThreadingHTTPServer`. No Flask, no
  npm, no build step. Each request runs in its own thread, so a 2-second AI
  search doesn't block serving the page.
- **Static files are allow-listed:** only `/`, `/app.js` and `/style.css` are
  served, so a request can never read other files on disk.
- **Winning-line highlight:** the server finds the winning four with the same
  69 precomputed window bitmasks the evaluation function uses.
- **Visuals:** discs are drawn underneath a board "frame" whose holes are a
  CSS radial gradient, so discs appear to fall behind the board. Only newly
  added discs get the drop animation, and an AI reply that arrives after the
  user has started a new game is ignored (each request has an ID).
- **AI analysis panel:** shows the AI's score as a bar (scaled with `tanh`, and
  full for a proven win or loss), along with depth reached, positions searched
  and positions per second. This makes the algorithm visible, which is useful
  in a demo.

---

## 8. Testing

`python3 -m unittest -v` runs 32 tests.

- **Rules:** stones stack, full columns are rejected, undo restores the exact
  position, wins in all four directions, no wrap-around between columns, and a
  full board with no winner is a draw.
- **Evaluation:** there are exactly 69 windows, the score is symmetric, and
  the centre is preferred.
- **AI behaviour:** takes an immediate win, blocks an immediate loss, finds a
  two-move forced win, opens in the centre, stays within its time limit,
  doesn't change the caller's board, never picks a full column, and rejects a
  finished game.
- **Web API:** rejects malformed or illegal move lists and unknown
  difficulties, doesn't let the AI move after the human has won, reports the
  winning cells, and over real HTTP: serves the page, returns 404 for unknown
  paths, and returns 400 with an error message for bad input.

The AI tests check *behaviour* (what a good player does) rather than exact
scores, so changing the heuristic weights doesn't break them.

---

## 9. Performance

On an empty board with 2 seconds per move: **depth 12, about 640,000
positions**, roughly 300,000 positions/second in pure Python.

Where the speed comes from:

| Technique | Effect |
|-----------|--------|
| Bitboards | Move/undo/win check in a few integer operations |
| Play/undo instead of copying | No memory allocation per node |
| Alpha-beta | Up to 2× deeper search for the same work |
| Iterative deepening + best-move memory | Near-ideal move ordering, so more pruning |
| Clock checked every 1,024 nodes | Little timing overhead |

---

## 10. Design decisions and trade-offs

| Decision | Alternative | Why I chose it |
|----------|-------------|----------------|
| Negamax | Explicit min/max minimax | Same algorithm, half the code, fewer places for bugs |
| Bitboards | 2D list | Much faster in the hot loop; complexity stays inside `board.py` |
| Best-move dictionary for ordering only | Full transposition table that also reuses scores | Reusing scores is trickier to get right (bounds, depth, win distance). Ordering-only is always correct and gives most of the benefit |
| Exception for timeout | Checking a flag at every return | Unwinds a deep recursion cleanly in one step |
| Search a copy of the board | Search in place with try/finally | Simpler; one copy per move costs nothing |
| Standard library only | numpy, Flask, etc. | Nothing to install, and runs anywhere |
| Stateless web server (client sends full move list) | Server-side game sessions | No session storage or cleanup; every move is re-validated |
| AI runs in Python on the server | Port the AI to JavaScript | One engine, tested once, shared by both UIs |

---

## 11. Possible extensions

1. **Full transposition table**: also store scores and bounds (exact /
   lower / upper) to skip re-searching positions reached by different move
   orders. Win scores have to be adjusted by ply when stored and loaded.
2. **Better heuristic**: odd/even threat analysis, which is how strong
   Connect 4 players think about the endgame.
3. **Principal variation search / aspiration windows**: search with narrow
   alpha-beta windows on the assumption the first move is best, and re-search
   only if wrong.
4. **Opening book**: stored best replies for the first few moves.
5. **Perfect play**: Connect 4 is solved (the first player wins with
   perfect play). A fast compiled solver with a transposition table can reach
   the end of the game from any position.
6. **Faster language or PyPy**: the same code runs several times faster under
   PyPy.
7. **Run the AI in the browser**: compile the engine to WebAssembly, or port
   it to JavaScript, so the game works with no server at all.

---

## 12. Likely interview questions

**Q: What's the time complexity of minimax?**
O(b^d), where b is the branching factor (7 for Connect 4) and d the depth.
Memory is O(d) because it's depth-first.

**Q: And with alpha-beta?**
Best case about O(b^(d/2)) with perfect move ordering, which is like halving
the depth. Worst case (worst move ordering) it's still O(b^d). It always
returns the same move as plain minimax; it only skips work.

**Q: Why use iterative deepening instead of a fixed depth?**
A fixed depth takes very different amounts of time in different positions.
Iterative deepening gives a time-bounded search that always has an answer, and
each iteration improves move ordering for the next.

**Q: What happens if time runs out in the middle of a depth?**
The partial result is thrown away and the last fully completed depth is used.
A partial search may not have looked at the best move yet.

**Q: How do you detect a win so quickly?**
Bit shifts: AND the board with itself shifted by one step in a direction to
find pairs, then AND the pairs with themselves shifted by two steps to find
fours. Four directions, constant time.

**Q: Why does the AI prefer faster wins?**
Wins are scored `WIN_SCORE - ply`, so a closer win scores higher. Without
this, every winning move scores the same and the AI might delay forever.

**Q: Why is the evaluation function symmetric?**
Negamax negates the child's score to get the parent's score. That's only
correct if a position worth +X to one player is worth exactly -X to the
other.

**Q: What's the horizon effect?**
The search stops at a fixed depth, so a threat just beyond it is invisible.
The AI may make a move that looks fine at depth d and loses at d+1. Deeper
search, better heuristics and quiescence search (extending the search when
threats are pending) all help.

**Q: How would you make it stronger?**
A full transposition table, odd/even threat evaluation, and a faster
implementation to search deeper. See section 11.

**Q: How did you test an AI?**
Small positions with a known correct answer: a win in 1, a forced block, a
two-move forced win. Plus checks that it respects time limits and never
changes the caller's board.

**Q: Why is the web server stateless?**
The browser sends the full move list each time, and the server rebuilds and
re-validates the board. There are no sessions to store or clean up, a restart
loses nothing, and the client can't put the game into an invalid state.

**Q: What happens if the AI is thinking and the user starts a new game?**
Each AI request gets an incrementing ID. When a reply arrives, the browser
ignores it if the ID no longer matches the current game.
