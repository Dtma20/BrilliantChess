/* Laboratório de duelo: autoplay no cliente, auditoria por lance e revisão.
   O agendamento vive nesta página; fechar a aba encerra o duelo. */

import { api } from "/static/api.js";
import { createBoard, kingSquare } from "/static/board.js";

const STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const STAMPS = { strict_v1: "◆", fallback: "◇", normal: "·" };

const GATES = [
  { id: "GATE_LEGAL_001", name: "Legalidade", relation: null, tile: "L" },
  { id: "GATE_QUALITY_001", name: "Qualidade", relation: "≤", tile: "Q" },
  { id: "GATE_SACRIFICE_001", name: "Sacrifício", relation: "≥", tile: "S" },
  { id: "GATE_SOUNDNESS_001", name: "Solidez", relation: "≤", tile: "D" },
  { id: "GATE_NOT_BAD_AFTER_001", name: "Posição depois", relation: "≥", tile: "P" },
  { id: "GATE_NOT_ALREADY_WON_001", name: "Não era ganho", relation: "≤", tile: "G" },
  { id: "GATE_STABILITY_001", name: "Estabilidade", relation: "≤", tile: "E" },
];

const GATE_GLYPHS = { passed: "✓", failed: "✕", indeterminate: "?" };
const GATE_WORDS = { passed: "aprovado", failed: "reprovado", indeterminate: "indeterminado" };

const elements = {
  stateMark: document.getElementById("state-mark"),
  deckText: document.getElementById("deck-text"),
  deckCount: document.getElementById("deck-count"),
  cadence: document.getElementById("cadence"),
  cadenceFill: document.getElementById("cadence-fill"),
  toggle: document.getElementById("toggle"),
  step: document.getElementById("step"),
  reset: document.getElementById("reset"),
  pgn: document.getElementById("pgn"),
  error: document.getElementById("error"),
  ribbon: document.getElementById("ribbon"),
  ribbonEmpty: document.getElementById("ribbon-empty"),
  reviewNote: document.getElementById("review-note"),
  audit: document.getElementById("audit"),
  white: {
    row: document.getElementById("side-white"),
    strength: document.getElementById("white-strength"),
    policy: document.getElementById("white-policy"),
    thinking: document.getElementById("thinking-white"),
    tally: document.getElementById("tally-white"),
  },
  black: {
    row: document.getElementById("side-black"),
    strength: document.getElementById("black-strength"),
    policy: document.getElementById("black-policy"),
    thinking: document.getElementById("thinking-black"),
    tally: document.getElementById("tally-black"),
  },
};

const state = {
  match: null,
  settings: { max_plies: 200, autoplay_delay_ms: 250 },
  strengths: [],
  running: false,
  busy: false,
  timer: null,
  selected: null,
  renderedPlies: -1,
  error: "",
};

const positions = new Map();

const board = createBoard(document.getElementById("board"), { orientation: "white" });
board.setInteractive(false);
board.setPosition(STARTPOS, {});

/* ---------- consultas de estado ---------- */

const plies = () => state.match?.moves.length ?? 0;
const finished = () => Boolean(state.match) && !state.match.can_step;
const capped = () => finished() && plies() >= state.settings.max_plies;
const reviewing = () => state.selected !== null && state.selected < plies() - 1;
const viewedPly = () => (state.selected === null ? plies() - 1 : state.selected);
const sideName = (color) => (color === "white" ? "Brancas" : "Pretas");
const profileOf = (color) => (color === "white" ? state.match?.white : state.match?.black);

/* ---------- formatação ---------- */

function formatNumber(value) {
  if (value === null || value === undefined) return "não medido";
  if (typeof value === "boolean") return value ? "sim" : "não";
  if (typeof value !== "number") return String(value);
  return Math.abs(value) < 1 ? value.toFixed(4) : value.toFixed(2);
}

function showError(message) {
  state.error = message || "";
  elements.error.textContent = state.error;
}

/* ---------- autoplay ---------- */

function stopAutoplay() {
  state.running = false;
  if (state.timer) clearTimeout(state.timer);
  state.timer = null;
}

function scheduleNext() {
  if (!state.running || state.busy || finished()) return;
  state.timer = setTimeout(runStep, state.settings.autoplay_delay_ms);
}

async function runStep() {
  if (!state.match || state.busy || finished()) return;
  state.busy = true;
  render();
  try {
    // Um pedido já em voo não é cancelável: o lance chega mesmo depois da pausa.
    // A seleção do usuário sobrevive a ele — só quem está ao vivo segue ao vivo.
    state.match = await api.stepMatch(state.match.match_id);
    showError("");
  } catch (error) {
    showError(error.message);
    stopAutoplay();
  } finally {
    state.busy = false;
    render();
    scheduleNext();
  }
}

async function ensureMatch() {
  if (state.match) return true;
  state.busy = true;
  render();
  try {
    state.match = await api.newMatch({
      white: {
        strength_key: elements.white.strength.value,
        policy: elements.white.policy.value,
      },
      black: {
        strength_key: elements.black.strength.value,
        policy: elements.black.policy.value,
      },
    });
    positions.clear();
    state.selected = null;
    state.renderedPlies = -1;
    showError("");
    return true;
  } catch (error) {
    showError(error.message);
    return false;
  } finally {
    state.busy = false;
  }
}

async function onToggle() {
  if (state.running) {
    stopAutoplay();
    render();
    return;
  }
  if (!(await ensureMatch())) {
    render();
    return;
  }
  if (finished()) {
    render();
    return;
  }
  state.running = true;
  state.selected = null;
  render();
  runStep();
}

async function onStep() {
  stopAutoplay();
  if (!(await ensureMatch())) {
    render();
    return;
  }
  state.selected = null;
  await runStep();
}

function onReset() {
  stopAutoplay();
  state.match = null;
  state.selected = null;
  state.renderedPlies = -1;
  positions.clear();
  showError("");
  board.setPosition(STARTPOS, {});
  render();
}

function onExportPgn() {
  if (!state.match || plies() === 0) return;
  const link = document.createElement("a");
  link.href = `/api/match/${encodeURIComponent(state.match.match_id)}/pgn`;
  link.download = `brilliant-chess-lab-${state.match.match_id}.pgn`;
  document.body.append(link);
  link.click();
  link.remove();
}

/* ---------- revisão de lances ---------- */

async function selectPly(index) {
  if (!state.match || index < 0 || index >= plies()) return;
  if (index < plies() - 1) stopAutoplay();
  state.selected = index === plies() - 1 ? null : index;
  render();
  await renderBoard();
}

function backToLive() {
  state.selected = null;
  render();
  renderBoard();
}

async function positionAt(index) {
  if (positions.has(index)) return positions.get(index);
  const view = await api.board({
    fen: state.match.initial_fen,
    moves: state.match.moves_uci.slice(0, index + 1),
  });
  positions.set(index, view);
  return view;
}

async function renderBoard() {
  if (!state.match) return;
  let view = state.match.board;
  if (reviewing()) {
    try {
      view = await positionAt(state.selected);
    } catch (error) {
      showError(error.message);
      return;
    }
  }
  board.setPosition(view.fen, {
    lastMove: view.last_move_uci
      ? [view.last_move_uci.slice(0, 2), view.last_move_uci.slice(2, 4)]
      : null,
    checkSquare: view.is_check ? kingSquare(view.fen, view.side_to_move) : null,
  });
}

/* ---------- convés ---------- */

function deckState() {
  if (!state.match) return { mark: "idle", text: "Pronto para iniciar." };
  if (capped()) return { mark: "capped", text: state.match.result_text };
  if (finished()) return { mark: "done", text: state.match.result_text };
  if (state.busy) {
    return {
      mark: "thinking",
      text: `${sideName(state.match.board.side_to_move)} analisando…`,
    };
  }
  if (reviewing()) {
    return { mark: "review", text: `Revisão do meio-lance ${state.selected + 1} de ${plies()}.` };
  }
  if (state.error) return { mark: "error", text: "Duelo interrompido." };
  if (state.running) return { mark: "thinking", text: "Duelo em andamento." };
  if (plies() === 0) return { mark: "paused", text: "Perfis prontos. Falta iniciar." };
  const done = plies() === 1 ? "1 meio-lance" : `${plies()} meios-lances`;
  return { mark: "paused", text: `Em pausa após ${done}.` };
}

function renderDeck() {
  const { mark, text } = deckState();
  elements.stateMark.dataset.state = mark;
  elements.deckText.textContent = text;

  const total = state.settings.max_plies;
  const used = plies();
  elements.deckCount.textContent = `${used}/${total} meios-lances`;
  const ratio = total > 0 ? Math.min(1, used / total) : 0;
  elements.cadenceFill.style.width = `${(ratio * 100).toFixed(1)}%`;
  elements.cadence.dataset.near = String(ratio >= 0.9);
  elements.cadence.setAttribute(
    "aria-label",
    used === 0
      ? "Nenhum meio-lance jogado"
      : `${used} de ${total} meios-lances do limite experimental`,
  );
}

/* ---------- perfis ---------- */

function renderBench() {
  for (const color of ["white", "black"]) {
    const side = elements[color];
    const thinkingNow =
      state.busy && state.match !== null && state.match.board.side_to_move === color;
    side.row.classList.toggle("is-thinking", thinkingNow);
    side.thinking.hidden = !thinkingNow;
    side.strength.disabled = Boolean(state.match);
    side.policy.disabled = Boolean(state.match);

    const counts = { strict_v1: 0, fallback: 0, normal: 0 };
    for (const move of state.match?.moves ?? []) {
      if (move.color === color) counts[move.selection] += 1;
    }
    const total = counts.strict_v1 + counts.fallback + counts.normal;
    side.tally.hidden = total === 0;
    if (total === 0) continue;
    side.tally.replaceChildren(
      ...["strict_v1", "fallback", "normal"].map((kind) => {
        const item = document.createElement("span");
        const value = document.createElement("b");
        value.textContent = String(counts[kind]);
        const name = document.createElement("span");
        name.textContent = kind;
        item.append(value, name);
        return item;
      }),
    );
  }
}

/* ---------- fita de lances ---------- */

function plyButton(move, index) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ply";
  button.dataset.index = String(index);
  button.tabIndex = index === viewedPly() ? 0 : -1;
  if (index === viewedPly()) button.setAttribute("aria-current", "true");

  const san = document.createElement("span");
  san.className = "san";
  san.textContent = move.san;

  const stamp = document.createElement("span");
  stamp.className = "stamp";
  stamp.dataset.kind = move.selection;
  stamp.textContent = STAMPS[move.selection] ?? STAMPS.normal;
  stamp.setAttribute("aria-hidden", "true");

  button.append(san, stamp);
  button.setAttribute(
    "aria-label",
    `${Math.floor(index / 2) + 1}. ${move.san}, ${sideName(move.color).toLowerCase()}, escolha ${move.selection}`,
  );
  if (index >= state.renderedPlies && state.renderedPlies >= 0) button.classList.add("is-new");
  button.addEventListener("click", () => selectPly(index));
  return button;
}

function renderRibbon() {
  const moves = state.match?.moves ?? [];
  elements.ribbonEmpty.hidden = moves.length > 0;
  if (moves.length === 0) {
    elements.ribbon.replaceChildren();
    state.renderedPlies = 0;
    return;
  }

  const hadFocus = elements.ribbon.contains(document.activeElement);
  const rows = [];
  for (let index = 0; index < moves.length; index += 2) {
    const row = document.createElement("li");
    const number = document.createElement("span");
    number.className = "ribbon-no";
    number.textContent = `${index / 2 + 1}.`;
    row.append(number, plyButton(moves[index], index));
    if (moves[index + 1]) {
      row.append(plyButton(moves[index + 1], index + 1));
    } else {
      const filler = document.createElement("span");
      filler.className = "ply-void";
      row.append(filler);
    }
    rows.push(row);
  }
  elements.ribbon.replaceChildren(...rows);
  state.renderedPlies = moves.length;

  const current = elements.ribbon.querySelector('[aria-current="true"]');
  if (hadFocus && current) current.focus();
  if (!reviewing() && current) current.scrollIntoView({ block: "nearest" });

  elements.reviewNote.hidden = !reviewing();
  if (reviewing()) {
    elements.reviewNote.replaceChildren(
      document.createTextNode("Autoplay pausado para revisão. "),
    );
    const link = document.createElement("button");
    link.type = "button";
    link.textContent = "Voltar ao lance atual";
    link.addEventListener("click", backToLive);
    elements.reviewNote.append(link);
  }
}

function onRibbonKeydown(event) {
  const keys = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"];
  if (!keys.includes(event.key)) return;
  const total = plies();
  if (total === 0) return;
  const current = viewedPly();
  const deltas = { ArrowUp: -2, ArrowDown: 2, ArrowLeft: -1, ArrowRight: 1 };
  let next = current;
  if (event.key === "Home") next = 0;
  else if (event.key === "End") next = total - 1;
  else next = current + deltas[event.key];
  next = Math.max(0, Math.min(total - 1, next));
  if (next === current) return;
  event.preventDefault();
  selectPly(next);
}

/* ---------- auditoria ---------- */

function emptyAudit(text) {
  const paragraph = document.createElement("p");
  paragraph.className = "empty";
  paragraph.textContent = text;
  return [paragraph];
}

function verdict(move) {
  const paragraph = document.createElement("p");
  paragraph.className = "verdict";
  const label = profileOf(move.color)?.strength.label ?? "";
  const strong = document.createElement("strong");
  strong.textContent = move.san;

  if (move.selection === "strict_v1") {
    paragraph.append(strong);
    paragraph.append(
      ` passou pelos sete portões obrigatórios e foi a candidata elegível de maior pontuação.`,
    );
  } else if (move.selection === "fallback") {
    paragraph.append(
      "Nenhuma candidata passou pelos sete portões nesta posição. ",
      `${sideName(move.color)} jogaram `,
      strong,
      `, a melhor jogada do perfil ${label}.`,
    );
  } else {
    paragraph.append(
      strong,
      ` veio do Stockfish no perfil ${label}. A política normal não aplica nenhum critério de brilhantismo.`,
    );
  }
  return paragraph;
}

function gateRail(gates) {
  const rail = document.createElement("div");
  rail.className = "gate-rail";
  for (const meta of GATES) {
    const gate = gates.find((item) => item.gate_id === meta.id);
    const tile = document.createElement("span");
    tile.className = "gate-tile";
    tile.dataset.status = gate?.status ?? "indeterminate";
    // inicial do portão + glifo: a régua se lê sem passar o mouse e sem depender de cor
    tile.textContent = `${meta.tile}${gate ? GATE_GLYPHS[gate.status] : GATE_GLYPHS.indeterminate}`;
    tile.title = `${meta.name}: ${GATE_WORDS[gate?.status ?? "indeterminate"]}`;
    tile.setAttribute("role", "img");
    tile.setAttribute("aria-label", tile.title);
    rail.append(tile);
  }
  return rail;
}

function gateMeter(measured, threshold) {
  if (typeof measured !== "number" || typeof threshold !== "number") return null;
  const span = Math.max(Math.abs(measured), Math.abs(threshold)) * 1.35 || 1;
  const meter = document.createElement("div");
  meter.className = "meter";
  const tick = document.createElement("i");
  tick.style.left = `${Math.min(100, (Math.abs(threshold) / span) * 100)}%`;
  const dot = document.createElement("b");
  dot.style.left = `${Math.min(100, (Math.abs(measured) / span) * 100)}%`;
  meter.append(tick, dot);
  return meter;
}

function gateBlock(gate, meta) {
  const block = document.createElement("div");
  block.className = "gate";

  const head = document.createElement("div");
  head.className = "gate-head";
  const name = document.createElement("span");
  name.className = "gate-name";
  name.textContent = meta.name;
  const flag = document.createElement("span");
  flag.className = "gate-flag";
  flag.dataset.status = gate.status;
  flag.textContent = `${GATE_GLYPHS[gate.status]} ${GATE_WORDS[gate.status]}`;
  head.append(name, flag);

  const read = document.createElement("p");
  read.className = "gate-read";
  read.style.margin = "0.25rem 0 0";
  read.textContent = meta.relation
    ? `${formatNumber(gate.measured)} ${meta.relation} ${formatNumber(gate.threshold)}`
    : formatNumber(gate.measured);

  block.append(head, read);
  const meter = gateMeter(gate.measured, gate.threshold);
  if (meter) block.append(meter);

  const note = document.createElement("p");
  note.className = "gate-note";
  note.textContent = gate.explanation;
  block.append(note);
  return block;
}

function auditDrawers(audit) {
  const gatesDrawer = document.createElement("details");
  gatesDrawer.className = "drawer";
  const gatesSummary = document.createElement("summary");
  gatesSummary.textContent = "Portões e medidas";
  gatesDrawer.append(gatesSummary);
  for (const meta of GATES) {
    const gate = audit.gates.find((item) => item.gate_id === meta.id);
    if (gate) gatesDrawer.append(gateBlock(gate, meta));
  }

  const originDrawer = document.createElement("details");
  originDrawer.className = "drawer";
  const originSummary = document.createElement("summary");
  originSummary.textContent = "Procedência";
  originDrawer.append(originSummary);
  const list = document.createElement("ul");
  list.className = "reasons";
  const version = document.createElement("li");
  version.textContent = `regras = ${audit.rule_set_version}`;
  const uci = document.createElement("li");
  uci.textContent = `uci = ${audit.selected_uci}`;
  list.append(version, uci);
  for (const reason of audit.reason_codes) {
    const item = document.createElement("li");
    item.textContent = reason;
    list.append(item);
  }
  originDrawer.append(list);

  return [gatesDrawer, originDrawer];
}

function renderAudit() {
  if (!state.match) {
    elements.audit.replaceChildren(
      ...emptyAudit("Inicie o duelo para ver como cada lance foi escolhido."),
    );
    return;
  }
  const index = viewedPly();
  const move = state.match.moves[index];
  if (!move) {
    elements.audit.replaceChildren(
      ...emptyAudit("Ainda não há lances. A auditoria aparece a partir do primeiro."),
    );
    return;
  }

  const nodes = [verdict(move)];
  if (move.audit) {
    const scoreLine = document.createElement("div");
    scoreLine.className = "score-line";
    const value = document.createElement("span");
    value.className = "score-value";
    value.textContent = move.audit.score.toFixed(1);
    const scale = document.createElement("span");
    scale.className = "score-scale";
    scale.textContent = "/ 100 pontos de brilhantismo";
    scoreLine.append(value, scale);
    nodes.push(scoreLine, gateRail(move.audit.gates), ...auditDrawers(move.audit));
  }
  elements.audit.replaceChildren(...nodes);
}

/* ---------- render ---------- */

function renderControls() {
  const hasMatch = Boolean(state.match);
  elements.toggle.textContent = state.running
    ? "Pausar"
    : hasMatch && plies() > 0
      ? "Continuar"
      : "Iniciar duelo";
  elements.toggle.disabled = state.busy || finished();
  elements.step.disabled = state.busy || state.running || finished();
  elements.reset.disabled = state.busy || !hasMatch;
  elements.pgn.disabled = state.busy || !hasMatch || plies() === 0;
}

function render() {
  renderDeck();
  renderBench();
  renderControls();
  renderRibbon();
  renderAudit();
  if (state.match && !reviewing()) renderBoard();
}

/* ---------- carga inicial ---------- */

async function loadStrengths() {
  const levels = await api.strengths();
  state.strengths = levels;
  for (const [color, preferred] of [
    ["white", "maximo"],
    ["black", "iniciante"],
  ]) {
    elements[color].strength.replaceChildren(
      ...levels.map((level) => {
        const option = document.createElement("option");
        option.value = level.key;
        option.textContent = level.label;
        option.selected = level.key === preferred;
        return option;
      }),
    );
  }
}

async function loadSettings() {
  state.settings = await api.lab();
}

elements.toggle.addEventListener("click", onToggle);
elements.step.addEventListener("click", onStep);
elements.reset.addEventListener("click", onReset);
elements.pgn.addEventListener("click", onExportPgn);
elements.ribbon.addEventListener("keydown", onRibbonKeydown);

document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  const tag = event.target?.tagName ?? "";
  if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(tag)) return;
  if (event.code === "Space") {
    event.preventDefault();
    onToggle();
  } else if (event.key.toLowerCase() === "n") {
    event.preventDefault();
    onStep();
  }
});

window.addEventListener("pagehide", stopAutoplay);

try {
  await Promise.all([loadStrengths(), loadSettings()]);
} catch (error) {
  showError(error.message);
}
render();
