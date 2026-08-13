/* Tabuleiro SVG/DOM sem dependencia externa: pecas, seleção, arrasto e setas. */

const FILES = "abcdefgh";
/* U+FE0E forca apresentacao de texto: em plataformas onde U+265F tem
   apresentacao de emoji por padrao, o glifo colorido ignoraria o CSS. */
const TEXT_PRESENTATION = "︎";
const GLYPHS = Object.fromEntries(
  Object.entries({ k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" }).map(([type, glyph]) => [
    type,
    glyph + TEXT_PRESENTATION,
  ]),
);
const SVG_NS = "http://www.w3.org/2000/svg";
const PROMOTION_PIECES = ["q", "r", "b", "n"];

export function parseFen(fen) {
  const [placement, turn] = fen.split(" ");
  const pieces = {};
  placement.split("/").forEach((row, index) => {
    const rank = 8 - index;
    let file = 0;
    for (const symbol of row) {
      if (/\d/.test(symbol)) {
        file += Number(symbol);
        continue;
      }
      const square = FILES[file] + rank;
      pieces[square] = {
        type: symbol.toLowerCase(),
        color: symbol === symbol.toUpperCase() ? "white" : "black",
      };
      file += 1;
    }
  });
  return { pieces, turn: turn === "b" ? "black" : "white" };
}

export function createBoard(root, options = {}) {
  const state = {
    orientation: options.orientation || "white",
    interactive: options.interactive !== false,
    onMove: options.onMove || (() => {}),
    fen: null,
    pieces: {},
    legalMoves: [],
    selected: null,
    lastMove: null,
    checkSquare: null,
    arrows: [],
    drag: null,
  };

  root.classList.add("board");
  const squaresEl = document.createElement("div");
  squaresEl.className = "board-squares";
  const overlay = document.createElementNS(SVG_NS, "svg");
  overlay.setAttribute("class", "board-overlay");
  overlay.setAttribute("viewBox", "0 0 8 8");
  overlay.setAttribute("preserveAspectRatio", "none");
  root.append(squaresEl, overlay);

  const squareEls = new Map();
  for (const name of allSquares()) {
    const cell = document.createElement("div");
    cell.dataset.square = name;
    squareEls.set(name, cell);
  }

  function layout() {
    squaresEl.replaceChildren();
    for (const name of orderedSquares(state.orientation)) {
      const cell = squareEls.get(name);
      const file = FILES.indexOf(name[0]);
      const rank = Number(name[1]);
      // a1 e h8 sao casas escuras: soma par e clara, soma impar e escura.
      cell.className = `square ${(file + rank) % 2 === 0 ? "light" : "dark"}`;
      squaresEl.append(cell);
    }
    decorateCoordinates();
  }

  function decorateCoordinates() {
    const bottomRank = state.orientation === "white" ? 1 : 8;
    const leftFile = state.orientation === "white" ? "a" : "h";
    for (const [name, cell] of squareEls) {
      cell.querySelectorAll(".coord").forEach((node) => node.remove());
      if (Number(name[1]) === bottomRank) cell.append(coord("file", name[0]));
      if (name[0] === leftFile) cell.append(coord("rank", name[1]));
    }
  }

  function coord(kind, text) {
    const span = document.createElement("span");
    span.className = `coord ${kind}`;
    span.textContent = text;
    return span;
  }

  function render() {
    for (const [name, cell] of squareEls) {
      cell.classList.toggle("last-move", Boolean(state.lastMove?.includes(name)));
      cell.classList.toggle("check", state.checkSquare === name);
      cell.classList.toggle("selected", state.selected === name);
      cell.querySelectorAll(".piece, .hint").forEach((node) => node.remove());
      const piece = state.pieces[name];
      if (piece) cell.append(pieceEl(piece));
    }
    if (state.selected) renderHints(state.selected);
    renderArrows();
  }

  function pieceEl(piece) {
    const span = document.createElement("span");
    span.className = `piece ${piece.color}`;
    span.textContent = GLYPHS[piece.type];
    return span;
  }

  function renderHints(from) {
    for (const uci of state.legalMoves) {
      if (!uci.startsWith(from)) continue;
      const target = uci.slice(2, 4);
      const cell = squareEls.get(target);
      if (!cell) continue;
      const hint = document.createElement("span");
      hint.className = state.pieces[target] ? "hint capture" : "hint";
      cell.append(hint);
    }
  }

  function renderArrows() {
    overlay.replaceChildren();
    state.arrows.forEach((arrow, index) => {
      const start = center(arrow.from_square, state.orientation);
      const end = center(arrow.to_square, state.orientation);
      const opacity = Math.max(0.45, 1 - index * 0.2);
      for (const node of arrowShapes(start, end, arrow.color, opacity)) overlay.append(node);
    });
  }

  function squareFromEvent(event) {
    const cell = event.target.closest?.("[data-square]");
    return cell ? cell.dataset.square : null;
  }

  function movesFrom(square) {
    return state.legalMoves.filter((uci) => uci.startsWith(square));
  }

  function attempt(from, to) {
    const matches = state.legalMoves.filter((uci) => uci.slice(0, 4) === from + to);
    if (matches.length === 0) return false;
    state.selected = null;
    if (matches.length > 1 && matches.every((uci) => uci.length === 5)) {
      askPromotion(matches, to);
      return true;
    }
    render();
    state.onMove(matches[0]);
    return true;
  }

  function askPromotion(candidates, target) {
    const color = state.pieces[candidates[0].slice(0, 2)]?.color || "white";
    const overlayEl = document.createElement("div");
    overlayEl.className = "promotion";
    const box = document.createElement("div");
    box.className = "choices";
    for (const type of PROMOTION_PIECES) {
      const uci = candidates.find((item) => item.endsWith(type));
      if (!uci) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.innerHTML = `<span class="piece ${color}">${GLYPHS[type]}</span>`;
      button.title = `Promover para ${type.toUpperCase()}`;
      button.addEventListener("click", () => {
        overlayEl.remove();
        state.onMove(uci);
      });
      box.append(button);
    }
    overlayEl.append(box);
    overlayEl.addEventListener("click", (event) => {
      if (event.target === overlayEl) {
        overlayEl.remove();
        render();
      }
    });
    root.append(overlayEl);
    void target;
  }

  function onPointerDown(event) {
    if (!state.interactive || event.button !== 0) return;
    const square = squareFromEvent(event);
    if (!square) return;
    if (state.selected && attempt(state.selected, square)) return;
    if (!state.pieces[square] || movesFrom(square).length === 0) {
      state.selected = null;
      render();
      return;
    }
    state.selected = square;
    render();
    startDrag(square, event);
  }

  function startDrag(square, event) {
    const cell = squareEls.get(square);
    const piece = cell.querySelector(".piece");
    if (!piece) return;
    const ghost = piece.cloneNode(true);
    ghost.classList.add("drag-ghost");
    ghost.style.fontSize = `${cell.clientHeight * 0.78}px`;
    document.body.append(ghost);
    piece.classList.add("dragging");
    state.drag = { from: square, ghost, piece };
    moveGhost(event);
    root.setPointerCapture?.(event.pointerId);
  }

  function moveGhost(event) {
    if (!state.drag) return;
    state.drag.ghost.style.left = `${event.clientX}px`;
    state.drag.ghost.style.top = `${event.clientY}px`;
  }

  function onPointerUp(event) {
    if (!state.drag) return;
    const { from, ghost, piece } = state.drag;
    state.drag = null;
    ghost.remove();
    piece.classList.remove("dragging");
    root.releasePointerCapture?.(event.pointerId);
    const element = document.elementFromPoint(event.clientX, event.clientY);
    const target = element?.closest?.("[data-square]")?.dataset.square;
    if (target && target !== from) attempt(from, target);
  }

  root.addEventListener("pointerdown", onPointerDown);
  root.addEventListener("pointermove", moveGhost);
  root.addEventListener("pointerup", onPointerUp);
  root.addEventListener("contextmenu", (event) => event.preventDefault());

  layout();
  render();

  return {
    setPosition(fen, extra = {}) {
      state.fen = fen;
      state.pieces = parseFen(fen).pieces;
      state.legalMoves = extra.legalMoves || [];
      state.lastMove = extra.lastMove || null;
      state.checkSquare = extra.checkSquare || null;
      state.selected = null;
      render();
    },
    setArrows(arrows) {
      state.arrows = arrows || [];
      renderArrows();
    },
    setOrientation(orientation) {
      state.orientation = orientation;
      layout();
      render();
    },
    flip() {
      this.setOrientation(state.orientation === "white" ? "black" : "white");
      return state.orientation;
    },
    setInteractive(value) {
      state.interactive = value;
    },
    get orientation() {
      return state.orientation;
    },
  };
}

export function kingSquare(fen, color) {
  const { pieces } = parseFen(fen);
  for (const [square, piece] of Object.entries(pieces)) {
    if (piece.type === "k" && piece.color === color) return square;
  }
  return null;
}

function allSquares() {
  const result = [];
  for (let rank = 8; rank >= 1; rank -= 1) {
    for (const file of FILES) result.push(file + rank);
  }
  return result;
}

function orderedSquares(orientation) {
  const squares = allSquares();
  return orientation === "white" ? squares : squares.slice().reverse();
}

function center(square, orientation) {
  const file = FILES.indexOf(square[0]);
  const rank = Number(square[1]);
  const col = orientation === "white" ? file : 7 - file;
  const row = orientation === "white" ? 8 - rank : rank - 1;
  return { x: col + 0.5, y: row + 0.5 };
}

function arrowShapes(start, end, color, opacity) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy) || 1;
  const ux = dx / length;
  const uy = dy / length;
  const head = 0.3;
  const halfHead = 0.19;
  const tipX = end.x - ux * 0.06;
  const tipY = end.y - uy * 0.06;
  const baseX = tipX - ux * head;
  const baseY = tipY - uy * head;

  const shaft = document.createElementNS(SVG_NS, "line");
  shaft.setAttribute("x1", start.x + ux * 0.18);
  shaft.setAttribute("y1", start.y + uy * 0.18);
  shaft.setAttribute("x2", baseX);
  shaft.setAttribute("y2", baseY);
  shaft.setAttribute("stroke", color);
  shaft.setAttribute("stroke-width", "0.13");
  shaft.setAttribute("stroke-linecap", "round");
  shaft.setAttribute("opacity", String(opacity));

  const headShape = document.createElementNS(SVG_NS, "polygon");
  const points = [
    `${tipX},${tipY}`,
    `${baseX - uy * halfHead},${baseY + ux * halfHead}`,
    `${baseX + uy * halfHead},${baseY - ux * halfHead}`,
  ].join(" ");
  headShape.setAttribute("points", points);
  headShape.setAttribute("fill", color);
  headShape.setAttribute("opacity", String(opacity));

  return [shaft, headShape];
}
