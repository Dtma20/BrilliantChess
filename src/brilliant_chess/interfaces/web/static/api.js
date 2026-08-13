/* Cliente HTTP minimo da API local. Erros do servidor viram Error com detalhe. */

export async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = payload?.detail || `Erro ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

export const api = {
  strengths: () => request("/api/strengths"),
  newGame: (body) => request("/api/game", { method: "POST", body: JSON.stringify(body) }),
  move: (id, move) =>
    request(`/api/game/${id}/move`, { method: "POST", body: JSON.stringify({ move }) }),
  undo: (id) => request(`/api/game/${id}/undo`, { method: "POST" }),
  board: (body) => request("/api/board", { method: "POST", body: JSON.stringify(body) }),
  analyze: (body) => request("/api/analyze", { method: "POST", body: JSON.stringify(body) }),
};

export function formatMoveList(sanMoves) {
  const parts = [];
  for (let index = 0; index < sanMoves.length; index += 2) {
    const number = index / 2 + 1;
    const white = sanMoves[index] ?? "";
    const black = sanMoves[index + 1] ?? "";
    parts.push(`<b>${number}.</b> ${white} ${black}`);
  }
  return parts.join("  ");
}
