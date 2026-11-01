// Connect 4 front end.
//
// The browser owns the game as a list of moves (column numbers). Whenever the
// AI needs to reply, the whole list is sent to the Python server, which
// validates it, runs the search and returns the new state.

const COLUMNS = 7;
const ROWS = 6;
const COLORS = ["red", "yellow"];        // player 0 moves first
const MIN_AI_DELAY_MS = 450;             // so instant replies still feel like a turn

const $ = (id) => document.getElementById(id);
const els = {
  board: $("board"),
  discs: $("discs"),
  columns: $("columns"),
  ghost: $("ghost"),
  status: $("status"),
  statusText: $("status-text"),
  newGame: $("new-game"),
  undo: $("undo"),
  difficulty: $("difficulty"),
  side: $("side"),
  evalFill: $("eval-fill"),
  evalText: $("eval-text"),
  statDepth: $("stat-depth"),
  statNodes: $("stat-nodes"),
  statTime: $("stat-time"),
  statSpeed: $("stat-speed"),
  scoreHuman: $("score-human"),
  scoreDraw: $("score-draw"),
  scoreAi: $("score-ai"),
};

const game = {
  moves: [],
  humanPlayer: 0,
  difficulty: "hard",
  winner: null,
  isDraw: false,
  winningCells: [],
  thinking: false,
  error: null,
  resultRecorded: false,
  requestId: 0,          // lets us ignore AI replies for a game that was reset
  drawnMoves: [],        // moves currently shown on screen, to animate only new discs
  hoverColumn: null,
};

const score = { human: 0, ai: 0, draw: 0 };

// ------------------------------------------------------------------- rules

const aiPlayer = () => 1 - game.humanPlayer;
const currentPlayer = () => game.moves.length % 2;
const isOver = () => game.winner !== null || game.isDraw;
const columnHeight = (col) => game.moves.filter((c) => c === col).length;
const canPlay = (col) => col >= 0 && col < COLUMNS && columnHeight(col) < ROWS;
const isHumanTurn = () => !isOver() && !game.thinking && currentPlayer() === game.humanPlayer;
const humanHasMoved = () => game.moves.some((_, i) => i % 2 === game.humanPlayer);

/** Turn a move list into disc positions: [{col, row, player}]. */
function placements(moves) {
  const heights = new Array(COLUMNS).fill(0);
  return moves.map((col, i) => ({ col, row: heights[col]++, player: i % 2 }));
}

// ---------------------------------------------------------------- server

async function requestPlay(moves, aiMove) {
  const response = await fetch("/api/play", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ moves, aiMove, difficulty: game.difficulty }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Send the current moves to the server and let the AI reply (unless the game just ended). */
async function runAiTurn() {
  const requestId = ++game.requestId;
  const movesBefore = game.moves;
  game.thinking = true;
  game.error = null;
  render();

  try {
    const [state] = await Promise.all([requestPlay(game.moves, true), delay(MIN_AI_DELAY_MS)]);
    if (requestId !== game.requestId) return;
    game.moves = state.moves;
    game.winner = state.winner;
    game.isDraw = state.isDraw;
    game.winningCells = state.winningCells;
    if (state.ai) showAnalysis(state.ai);
  } catch (error) {
    if (requestId !== game.requestId) return;
    // Take back the human move the server couldn't answer, so they can retry.
    game.moves = movesBefore.slice(0, -1);
    game.error = `Couldn't reach the AI: ${error.message}`;
  }
  game.thinking = false;
  render();
}

// --------------------------------------------------------------- actions

function playHumanMove(col) {
  if (!isHumanTurn() || !canPlay(col)) return;
  game.moves = [...game.moves, col];
  runAiTurn();
}

function undo() {
  if (game.thinking || !humanHasMoved()) return;
  const moves = [...game.moves];
  moves.pop();
  while (moves.length % 2 !== game.humanPlayer) moves.pop();
  game.moves = moves;
  game.winner = null;
  game.isDraw = false;
  game.winningCells = [];
  game.error = null;
  render();
}

function newGame() {
  game.requestId++;      // discard any AI reply still in flight
  game.moves = [];
  game.winner = null;
  game.isDraw = false;
  game.winningCells = [];
  game.thinking = false;
  game.error = null;
  game.resultRecorded = false;
  resetAnalysis();
  render();
  if (game.humanPlayer === 1) runAiTurn();
}

function setDifficulty(value) {
  game.difficulty = value;
  render();
}

function setSide(player) {
  if (player === game.humanPlayer) return;
  game.humanPlayer = player;
  // Switching sides only makes sense in a fresh game.
  newGame();
}

// ---------------------------------------------------------------- render

function render() {
  renderDiscs();
  renderColumns();
  renderGhost();
  renderStatus();
  renderControls();
  recordResult();
}

function renderDiscs() {
  const isContinuation = game.drawnMoves.every((col, i) => game.moves[i] === col);
  if (!isContinuation) els.discs.replaceChildren();

  const placed = placements(game.moves);
  for (const { col, row, player } of placed.slice(els.discs.children.length)) {
    const disc = document.createElement("div");
    disc.className = `disc ${COLORS[player]}${isContinuation ? " dropping" : ""}`;
    disc.style.setProperty("--col", col);
    disc.style.setProperty("--row", row);
    disc.addEventListener("animationend", (event) => {
      if (event.animationName === "drop") disc.classList.remove("dropping");
    });
    els.discs.append(disc);
  }
  game.drawnMoves = [...game.moves];

  const winning = new Set(game.winningCells.map(([c, r]) => `${c},${r}`));
  [...els.discs.children].forEach((disc, i) => {
    const { col, row } = placed[i];
    disc.classList.toggle("win", winning.has(`${col},${row}`));
    disc.classList.toggle("last", i === placed.length - 1 && !isOver());
  });
  els.board.classList.toggle("finished", game.winner !== null);
  els.board.classList.toggle("waiting", game.thinking);
}

function renderColumns() {
  [...els.columns.children].forEach((button, col) => {
    button.disabled = !isHumanTurn() || !canPlay(col);
  });
}

function renderGhost() {
  const col = game.hoverColumn;
  const visible = col !== null && isHumanTurn() && canPlay(col);
  els.ghost.className = `disc ghost ${COLORS[game.humanPlayer]}${visible ? " visible" : ""}`;
  if (col !== null) els.ghost.style.setProperty("--col", col);
}

function renderStatus() {
  let text;
  let mode = "";
  if (game.error) {
    text = game.error;
    mode = "error";
  } else if (game.winner === game.humanPlayer) {
    text = "You win! Nicely played.";
    mode = "over";
  } else if (game.winner !== null) {
    text = "The AI wins this one.";
    mode = "over";
  } else if (game.isDraw) {
    text = "It's a draw.";
    mode = "over";
  } else if (game.thinking) {
    text = "AI is thinking…";
    mode = "thinking";
  } else {
    text = "Your move: pick a column";
  }
  els.status.className = `status ${mode}`;
  els.statusText.textContent = text;
  document.body.className = `human-${COLORS[game.humanPlayer]}`;
}

function renderControls() {
  els.undo.disabled = game.thinking || !humanHasMoved();
  for (const button of els.difficulty.children) {
    button.classList.toggle("active", button.dataset.value === game.difficulty);
  }
  for (const button of els.side.children) {
    button.classList.toggle("active", Number(button.dataset.value) === game.humanPlayer);
  }
}

function recordResult() {
  if (!isOver() || game.resultRecorded) return;
  game.resultRecorded = true;
  if (game.isDraw) score.draw++;
  else if (game.winner === game.humanPlayer) score.human++;
  else score.ai++;
  els.scoreHuman.textContent = score.human;
  els.scoreDraw.textContent = score.draw;
  els.scoreAi.textContent = score.ai;
}

// -------------------------------------------------------------- analysis

function showAnalysis(ai) {
  // Map the score onto the bar: forced results fill it, otherwise squash with tanh.
  let advantage;
  let text;
  if (ai.forcedWin) {
    advantage = 1;
    const aiMoves = Math.ceil(ai.pliesToEnd / 2);
    text = aiMoves <= 1
      ? "The AI has found a winning move."
      : `The AI has found a forced win within ${aiMoves} of its moves.`;
  } else if (ai.forcedLoss) {
    advantage = -1;
    text = "You have a forced win from here. Can you find it?";
  } else {
    advantage = Math.tanh(ai.score / 150);
    if (ai.score > 40) text = "The AI thinks it's ahead.";
    else if (ai.score < -40) text = "The AI thinks you're ahead.";
    else text = "The position looks roughly even.";
  }

  els.evalFill.style.width = `${50 + 50 * advantage}%`;
  els.evalText.textContent = `${text} It played column ${ai.move + 1} (score ${formatScore(ai)}).`;
  els.statDepth.textContent = `${ai.depth} moves`;
  els.statNodes.textContent = ai.nodes.toLocaleString();
  els.statTime.textContent = `${ai.elapsed.toFixed(2)} s`;
  els.statSpeed.textContent = ai.elapsed > 0.01 ? `${formatCompact(ai.nodes / ai.elapsed)}/s` : "–";
}

function resetAnalysis() {
  els.evalFill.style.width = "50%";
  els.evalText.textContent = "The AI hasn't moved yet.";
  for (const el of [els.statDepth, els.statNodes, els.statTime, els.statSpeed]) el.textContent = "–";
}

const formatScore = (ai) => (ai.forcedWin ? "win" : ai.forcedLoss ? "loss" : (ai.score > 0 ? "+" : "") + ai.score);

function formatCompact(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}k`;
  return String(Math.round(n));
}

// ----------------------------------------------------------------- setup

function buildColumns() {
  for (let col = 0; col < COLUMNS; col++) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "column";
    button.setAttribute("aria-label", `Drop in column ${col + 1}`);
    button.addEventListener("click", () => playHumanMove(col));
    button.addEventListener("mouseenter", () => { game.hoverColumn = col; renderGhost(); });
    els.columns.append(button);
  }
  els.columns.addEventListener("mouseleave", () => { game.hoverColumn = null; renderGhost(); });
}

function bindControls() {
  els.newGame.addEventListener("click", newGame);
  els.undo.addEventListener("click", undo);
  els.difficulty.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button) setDifficulty(button.dataset.value);
  });
  els.side.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button) setSide(Number(button.dataset.value));
  });

  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key.toLowerCase();
    if (/^[1-7]$/.test(key)) playHumanMove(Number(key) - 1);
    else if (key === "u") undo();
    else if (key === "n") newGame();
  });
}

buildColumns();
bindControls();
render();
