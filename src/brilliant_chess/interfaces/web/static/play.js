import { api, formatMoveList } from "/static/api.js";
import { createBoard, kingSquare } from "/static/board.js";

const elements = {
  color: document.getElementById("color"),
  strength: document.getElementById("strength"),
  newGame: document.getElementById("new-game"),
  undo: document.getElementById("undo"),
  flip: document.getElementById("flip"),
  exportPgn: document.getElementById("export-pgn"),
  status: document.getElementById("status"),
  error: document.getElementById("error"),
  moves: document.getElementById("moves"),
};

let game = null;
let busy = false;

const board = createBoard(document.getElementById("board"), {
  orientation: "white",
  onMove: (uci) => submitMove(uci),
});

function showError(message) {
  elements.error.textContent = message || "";
}

function setBusy(value) {
  busy = value;
  const playable =
    Boolean(game) &&
    game.board.status === "in_progress" &&
    game.board.side_to_move === game.human_color;
  board.setInteractive(!value && playable);
  elements.newGame.disabled = value;
  elements.undo.disabled = value || !game;
  elements.exportPgn.disabled = value || !game;
}

function render() {
  if (!game) return;
  const { board: view } = game;
  board.setPosition(view.fen, {
    legalMoves: view.side_to_move === game.human_color ? view.legal_moves : [],
    lastMove: view.last_move_uci ? [view.last_move_uci.slice(0, 2), view.last_move_uci.slice(2, 4)] : null,
    checkSquare: view.is_check ? kingSquare(view.fen, view.side_to_move) : null,
  });
  elements.moves.innerHTML = formatMoveList(game.moves_san);
  const finished = view.status !== "in_progress";
  elements.status.classList.toggle("finished", finished);
  if (finished) {
    elements.status.textContent = game.result_text;
  } else if (busy) {
    elements.status.innerHTML = '<span class="spinner"></span> Motor pensando...';
  } else {
    const turn = view.side_to_move === game.human_color ? "Sua vez" : "Vez do motor";
    elements.status.textContent = `${turn} — lance ${view.move_number} — ${game.strength.label}`;
  }
}

async function submitMove(uci) {
  if (!game || busy) return;
  setBusy(true);
  elements.status.innerHTML = '<span class="spinner"></span> Motor pensando...';
  try {
    game = await api.move(game.game_id, uci);
    showError("");
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
    render();
  }
}

async function startGame() {
  setBusy(true);
  showError("");
  try {
    game = await api.newGame({
      human_color: elements.color.value,
      strength_key: elements.strength.value,
    });
    board.setOrientation(game.human_color);
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
    render();
  }
}

async function undoMove() {
  if (!game || busy) return;
  setBusy(true);
  try {
    game = await api.undo(game.game_id);
    showError("");
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
    render();
  }
}

function exportPgn() {
  if (!game || busy) return;
  const link = document.createElement("a");
  link.href = `/api/game/${encodeURIComponent(game.game_id)}/pgn`;
  link.download = `brilliant-chess-${game.game_id}.pgn`;
  document.body.append(link);
  link.click();
  link.remove();
}

async function loadStrengths() {
  try {
    const levels = await api.strengths();
    elements.strength.replaceChildren(
      ...levels.map((level) => {
        const option = document.createElement("option");
        option.value = level.key;
        option.textContent = level.label;
        if (level.key === "clube") option.selected = true;
        return option;
      }),
    );
  } catch (error) {
    showError(error.message);
  }
}

elements.newGame.addEventListener("click", startGame);
elements.undo.addEventListener("click", undoMove);
elements.flip.addEventListener("click", () => board.flip());
elements.exportPgn.addEventListener("click", exportPgn);

await loadStrengths();
