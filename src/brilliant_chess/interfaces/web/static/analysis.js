import { api } from "/static/api.js";
import { createBoard, kingSquare } from "/static/board.js";

const STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const elements = {
  fen: document.getElementById("fen"),
  load: document.getElementById("load"),
  startpos: document.getElementById("startpos"),
  back: document.getElementById("back"),
  flip: document.getElementById("flip"),
  copy: document.getElementById("copy"),
  error: document.getElementById("error"),
  evalMain: document.getElementById("eval-main"),
  evalSide: document.getElementById("eval-side"),
  evalBar: document.getElementById("eval-bar"),
  engineInfo: document.getElementById("engine-info"),
  lines: document.getElementById("lines"),
  auto: document.getElementById("auto"),
  analyze: document.getElementById("analyze"),
  linesBody: document.getElementById("lines-body"),
  warnings: document.getElementById("warnings"),
  moves: document.getElementById("moves"),
};

const state = { baseFen: STARTPOS, moves: [], view: null, analyzing: false };

const board = createBoard(document.getElementById("board"), {
  orientation: "white",
  onMove: (uci) => applyMove(uci),
});

function showError(message) {
  elements.error.textContent = message || "";
}

function renderBoard() {
  const view = state.view;
  if (!view) return;
  board.setPosition(view.fen, {
    legalMoves: view.legal_moves,
    lastMove: view.last_move_uci
      ? [view.last_move_uci.slice(0, 2), view.last_move_uci.slice(2, 4)]
      : null,
    checkSquare: view.is_check ? kingSquare(view.fen, view.side_to_move) : null,
  });
  elements.fen.value = view.fen;
  elements.moves.textContent = view.moves_san.length
    ? view.moves_san.join(" ")
    : "Mova as peças para explorar variantes.";
  elements.back.disabled = state.moves.length === 0;
}

function renderAnalysis(result) {
  const best = result.candidates[0];
  if (!best) {
    elements.evalMain.textContent = "—";
    elements.evalSide.textContent = result.board.status !== "in_progress" ? "posição final" : "";
    elements.linesBody.innerHTML = '<tr><td colspan="4" class="muted">Sem jogadas legais nesta posição.</td></tr>';
    board.setArrows([]);
    return;
  }
  const side = result.side_to_move === "white" ? "brancas" : "pretas";
  elements.evalMain.textContent = best.evaluation_text;
  elements.evalSide.textContent = `ponto de vista das ${side}`;
  elements.evalBar.style.width = `${Math.round(result.expected_points_before * 100)}%`;
  elements.engineInfo.textContent =
    `${result.engine_name} ${result.engine_version}` +
    (result.nnue_name ? ` · ${result.nnue_name}` : "") +
    ` · ${best.nodes.toLocaleString("pt-BR")} nós · profundidade ${best.depth}`;

  elements.linesBody.replaceChildren(
    ...result.candidates.map((candidate) => {
      const row = document.createElement("tr");
      if (candidate.rank === 1) row.className = "best";
      const arrow = result.arrows.find((item) => item.rank === candidate.rank);
      const dot = arrow ? `<span class="dot" style="background:${arrow.color}"></span>` : "";
      row.innerHTML =
        `<td>${dot}${candidate.rank}</td>` +
        `<td class="move">${candidate.move_san}</td>` +
        `<td class="eval">${candidate.evaluation_text}</td>` +
        `<td class="pv">${candidate.pv_san.slice(0, 6).join(" ")}</td>`;
      row.addEventListener("click", () => applyMove(candidate.move_uci));
      row.style.cursor = "pointer";
      return row;
    }),
  );
  elements.warnings.textContent = result.warnings.length
    ? `Avisos: ${result.warnings.join(", ")}`
    : "";
  board.setArrows(result.arrows);
}

async function refresh({ analyze = true } = {}) {
  showError("");
  try {
    state.view = await api.board({ fen: state.baseFen, moves: state.moves });
    renderBoard();
  } catch (error) {
    showError(error.message);
    return;
  }
  if (analyze && elements.auto.checked) await runAnalysis();
}

async function runAnalysis() {
  if (!state.view || state.analyzing) return;
  state.analyzing = true;
  elements.analyze.disabled = true;
  elements.engineInfo.innerHTML = '<span class="spinner"></span> Analisando...';
  board.setArrows([]);
  try {
    const result = await api.analyze({
      fen: state.view.fen,
      multipv: Number(elements.lines.value),
    });
    renderAnalysis(result);
  } catch (error) {
    showError(error.message);
    elements.engineInfo.textContent = "Análise indisponível.";
  } finally {
    state.analyzing = false;
    elements.analyze.disabled = false;
  }
}

async function applyMove(uci) {
  const previous = state.moves.slice();
  state.moves.push(uci);
  try {
    state.view = await api.board({ fen: state.baseFen, moves: state.moves });
    renderBoard();
  } catch (error) {
    state.moves = previous;
    showError(error.message);
    return;
  }
  if (elements.auto.checked) await runAnalysis();
}

function loadFen(fen) {
  state.baseFen = fen.trim() || STARTPOS;
  state.moves = [];
  refresh();
}

elements.load.addEventListener("click", () => loadFen(elements.fen.value));
elements.startpos.addEventListener("click", () => loadFen(STARTPOS));
elements.flip.addEventListener("click", () => board.flip());
elements.analyze.addEventListener("click", runAnalysis);
elements.lines.addEventListener("change", () => elements.auto.checked && runAnalysis());
elements.copy.addEventListener("click", async () => {
  await navigator.clipboard.writeText(elements.fen.value);
  showError("");
});
elements.back.addEventListener("click", () => {
  if (!state.moves.length) return;
  state.moves.pop();
  refresh();
});

await refresh();
