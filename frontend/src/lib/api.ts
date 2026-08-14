/**
 * Cliente da API local. Os tipos espelham `interfaces/web/schemas.py`.
 *
 * Nenhuma regra de xadrez vive aqui: o front só transporta e desenha o que o
 * backend decide. Todas as chamadas são relativas, então o alvo é sempre o
 * FastAPI em loopback — em desenvolvimento via proxy do Vite, em produção
 * porque o próprio FastAPI serve estes arquivos.
 */

/**
 * Versão de contrato que este cliente conhece. Um valor diferente vindo do
 * servidor não derruba a página: ela avisa e segue desenhando o que entende.
 */
export const API_SCHEMA_VERSION = "2"

export type Color = "white" | "black"

export type GameStatus =
  | "in_progress"
  | "checkmate"
  | "stalemate"
  | "draw_insufficient_material"
  | "draw_fifty_moves"
  | "draw_threefold_repetition"

export type MatchPolicy = "normal" | "strict_v1" | "strict_v2"

export type SelectionKind =
  | "normal"
  | "strict_v1"
  | "strict_v2"
  | "near_brilliant"
  | "fallback"

export type GateStatus = "passed" | "failed" | "indeterminate"

export type SacrificeKind =
  | "destination_offer"
  | "left_hanging"
  | "exchange_sacrifice"
  | "declined_recapture"
  | "clearance_or_deflection"

export type PieceName = "pawn" | "knight" | "bishop" | "rook" | "queen" | "king"

/**
 * O que chega pelo fio. Um servidor mais novo pode mandar um valor que este
 * cliente ainda não conhece, e nenhuma tela pode quebrar por causa disso.
 * `string & {}` mantém o autocompletar dos valores conhecidos.
 */
export type Wire<T extends string> = T | (string & {})

export type MeasuredValue = number | string | boolean | null

export interface Strength {
  key: string
  label: string
  elo: number | null
}

export interface BoardView {
  fen: string
  side_to_move: Color
  status: GameStatus
  is_check: boolean
  legal_moves: string[]
  last_move_uci: string | null
  move_number: number
  moves_san: string[]
}

export interface Game {
  schema_version: string
  game_id: string
  human_color: Color
  strength: Strength
  board: BoardView
  moves_san: string[]
  moves_uci: string[]
  engine_thinking: boolean
  result_text: string
}

export interface Gate {
  gate_id: string
  status: Wire<GateStatus>
  measured: MeasuredValue
  threshold: MeasuredValue
  explanation: string
}

/** Peça oferecida e as capturas legais que aceitariam a oferta. */
export interface Sacrifice {
  kind: Wire<SacrificeKind>
  offered_square: string
  offered_piece: Wire<PieceName>
  nominal_value: number
  confidence: number
  acceptance_san: string[]
  accepted_by_best_defense: boolean
  material_conceded: number
}

export interface ExchangeEvidence {
  disposition: string
  material_before: number
  material_immediately_after: number
  material_after_best_acceptance: number | null
  material_captured_by_candidate: number
  material_lost_by_mover: number
  material_captured_later_by_mover: number
  net_material_concession: number
  sequence_uci: string[]
  sequence_san: string[]
  clean_trade: boolean
  obvious_recapture: boolean
  temporary_offer: boolean
  favorable_trade: boolean
  xray_recapture: boolean
}

export interface NonObviousnessEvidence {
  shallow_rank: number | null
  deep_rank: number | null
  shallow_expected_points: number | null
  deep_expected_points: number | null
  expected_points_improvement: number | null
  shallow_nodes: number | null
  shallow_multipv: number | null
  condition: string | null
}

export interface EngineIdentity {
  name: string
  version: string
  binary_sha256: string
  nnue_name: string | null
}

export interface NodeBudgets {
  discovery_nodes: number | null
  confirmation_nodes: number | null
  best_defense_nodes: number | null
  stability_nodes: number | null
  shallow_nodes: number | null
  shallow_multipv: number | null
}

export interface CandidateAudit {
  selected_uci: string
  selected_san: string
  score: number
  rule_set_version: string
  gates: Gate[]
  reason_codes: string[]
  sacrifice: Sacrifice | null
  best_defense_san: string | null
  terminal_status: Wire<GameStatus> | null
  exchange?: ExchangeEvidence | null
  non_obviousness?: NonObviousnessEvidence | null
  detector_version?: string | null
  engine_identity?: EngineIdentity | null
  budgets?: NodeBudgets | null
}

export interface MatchMove {
  color: Color
  uci: string
  san: string
  selection: Wire<SelectionKind>
  fallback: boolean
  audit: CandidateAudit | null
}

export interface MatchProfile {
  strength: Strength
  policy: MatchPolicy
}

export interface Match {
  schema_version: string
  match_id: string
  initial_fen: string
  white: MatchProfile
  black: MatchProfile
  board: BoardView
  moves_uci: string[]
  moves_san: string[]
  moves: MatchMove[]
  result_text: string
  can_step: boolean
}

export interface LabSettings {
  schema_version: string
  max_fullmoves: number
  max_plies: number
  autoplay_delay_ms: number
  strict_policy?: MatchPolicy
}

export interface Candidate {
  move_uci: string
  move_san: string
  rank: number
  expected_points_after: number
  expected_points_loss: number
  centipawns: number | null
  mate_in: number | null
  evaluation_text: string
  depth: number
  nodes: number
  pv_san: string[]
}

export interface Arrow {
  from_square: string
  to_square: string
  rank: number
  color: string
  label: string
}

export interface Analysis {
  schema_version: string
  fen: string
  side_to_move: Color
  engine_name: string
  engine_version: string
  nnue_name: string | null
  expected_points_before: number
  candidates: Candidate[]
  arrows: Arrow[]
  warnings: string[]
  board: BoardView
}

export interface Health {
  status: string
  engine_binary: string | null
  rule_set: string
}

export interface MatchProfileInput {
  strength_key: string
  policy: MatchPolicy
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...init,
    })
  } catch {
    throw new ApiError("Servidor local fora do ar. Rode `brilliant-chess serve`.", 0)
  }
  const text = await response.text()
  const payload: unknown = text ? JSON.parse(text) : null
  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail
    const message =
      typeof detail === "string" && detail ? detail : `Erro ${response.status} do servidor local.`
    throw new ApiError(message, response.status)
  }
  return payload as T
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export const api = {
  health: () => request<Health>("/api/health"),
  strengths: () => request<Strength[]>("/api/strengths"),
  lab: () => request<LabSettings>("/api/lab"),

  createGame: (body: { human_color: Color; strength_key: string; initial_fen?: string }) =>
    post<Game>("/api/game", body),
  readGame: (gameId: string) => request<Game>(`/api/game/${encodeURIComponent(gameId)}`),
  playMove: (gameId: string, move: string) =>
    post<Game>(`/api/game/${encodeURIComponent(gameId)}/move`, { move }),
  undo: (gameId: string) => post<Game>(`/api/game/${encodeURIComponent(gameId)}/undo`),
  gamePgnUrl: (gameId: string) => `/api/game/${encodeURIComponent(gameId)}/pgn`,

  board: (body: { fen?: string; moves?: string[] }) => post<BoardView>("/api/board", body),
  analyze: (body: { fen: string; multipv?: number }) => post<Analysis>("/api/analyze", body),

  createMatch: (body: { white: MatchProfileInput; black: MatchProfileInput }) =>
    post<Match>("/api/match", body),
  readMatch: (matchId: string) => request<Match>(`/api/match/${encodeURIComponent(matchId)}`),
  stepMatch: (matchId: string) => post<Match>(`/api/match/${encodeURIComponent(matchId)}/step`),
  matchPgnUrl: (matchId: string) => `/api/match/${encodeURIComponent(matchId)}/pgn`,
}

export const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

/** Baixa um PGN sem sair da página. */
export function downloadPgn(url: string, filename: string): void {
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
}
