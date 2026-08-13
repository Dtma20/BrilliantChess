/**
 * Vocabulário do laboratório.
 *
 * As quatro marcas de escolha se distinguem por glifo, por matiz e por texto,
 * nunca só por cor. Os sete portões aparecem sempre na mesma ordem, que é a
 * ordem de `domain/gates.py`.
 *
 * Toda leitura de valor vindo do servidor passa por uma função com padrão de
 * reserva. Um servidor mais novo pode mandar um `selection` ou um `status` que
 * este cliente não conhece; a página avisa e continua desenhando.
 */

import type {
  CandidateAudit,
  GameStatus,
  GateStatus,
  MatchMove,
  PieceName,
  Sacrifice,
  SacrificeKind,
  SelectionKind,
  Wire,
} from "@/lib/api"

export interface SelectionMeta {
  mark: string
  label: string
  short: string
  description: string
  /** Papel visual: quem decidiu o lance e com quanta evidência. */
  tone: "audited" | "safe" | "engine" | "unknown"
}

export const SELECTION_ORDER: SelectionKind[] = [
  "strict_v1",
  "near_brilliant",
  "fallback",
  "normal",
]

export const SELECTION_META: Record<SelectionKind, SelectionMeta> = {
  strict_v1: {
    mark: "◆",
    label: "strict_v1",
    short: "aprovada nos sete portões",
    description: "Passou pelos sete portões obrigatórios desta política.",
    tone: "audited",
  },
  near_brilliant: {
    mark: "◈",
    label: "near_brilliant",
    short: "segura, sem o selo de brilhante",
    description: "Auditada e segura, mas reprovada em algum portão de classificação.",
    tone: "safe",
  },
  fallback: {
    mark: "◇",
    label: "fallback",
    short: "nenhuma candidata segura",
    description: "Nada passou pela auditoria; jogou-se a melhor jogada do perfil.",
    tone: "engine",
  },
  normal: {
    mark: "·",
    label: "normal",
    short: "sem política de brilhantismo",
    description: "Stockfish no perfil de força, sem nenhum critério de brilhantismo.",
    tone: "engine",
  },
}

export const UNKNOWN_SELECTION_META: SelectionMeta = {
  mark: "?",
  label: "desconhecida",
  short: "valor não reconhecido por esta versão",
  description: "O servidor informou uma seleção que esta interface ainda não conhece.",
  tone: "unknown",
}

export function isKnownSelection(kind: Wire<SelectionKind>): kind is SelectionKind {
  return Object.hasOwn(SELECTION_META, kind)
}

/** Nunca indexa direto: seleção desconhecida vira uma marca honesta. */
export function selectionMeta(kind: Wire<SelectionKind>): SelectionMeta {
  return isKnownSelection(kind) ? SELECTION_META[kind] : UNKNOWN_SELECTION_META
}

export interface GateMeta {
  id: string
  name: string
  tile: string
  /** Direção do limiar. `null` quando o portão é booleano. */
  relation: "≤" | "≥" | null
}

export const GATES: GateMeta[] = [
  { id: "GATE_LEGAL_001", name: "Legalidade", tile: "L", relation: null },
  { id: "GATE_QUALITY_001", name: "Qualidade", tile: "Q", relation: "≤" },
  { id: "GATE_SACRIFICE_001", name: "Sacrifício", tile: "S", relation: "≥" },
  { id: "GATE_SOUNDNESS_001", name: "Solidez", tile: "D", relation: "≤" },
  { id: "GATE_NOT_BAD_AFTER_001", name: "Posição depois", tile: "P", relation: "≥" },
  { id: "GATE_NOT_ALREADY_WON_001", name: "Não era ganho", tile: "G", relation: "≤" },
  { id: "GATE_STABILITY_001", name: "Estabilidade", tile: "E", relation: "≤" },
]

const GATE_GLYPHS: Record<GateStatus, string> = {
  passed: "✓",
  failed: "✕",
  indeterminate: "?",
}

const GATE_WORDS: Record<GateStatus, string> = {
  passed: "aprovado",
  failed: "reprovado",
  indeterminate: "indeterminado",
}

export function gateGlyph(status: Wire<GateStatus>): string {
  return Object.hasOwn(GATE_GLYPHS, status) ? GATE_GLYPHS[status as GateStatus] : "?"
}

export function gateWord(status: Wire<GateStatus>): string {
  return Object.hasOwn(GATE_WORDS, status) ? GATE_WORDS[status as GateStatus] : "não reconhecido"
}

/** Só `passed` conta como aprovado; qualquer outro valor não aprova. */
export function gateTone(status: Wire<GateStatus>): "passed" | "failed" | "open" {
  if (status === "passed") return "passed"
  if (status === "failed") return "failed"
  return "open"
}

const SACRIFICE_KINDS: Record<SacrificeKind, string> = {
  destination_offer: "oferta na casa de destino",
  left_hanging: "peça deixada pendurada",
  exchange_sacrifice: "sacrifício de qualidade",
  declined_recapture: "recaptura recusada",
  clearance_or_deflection: "desimpedimento ou desvio",
}

const PIECE_NAMES: Record<PieceName, string> = {
  pawn: "Peão",
  knight: "Cavalo",
  bishop: "Bispo",
  rook: "Torre",
  queen: "Dama",
  king: "Rei",
}

const TERMINAL_TEXTS: Record<GameStatus, string> = {
  in_progress: "Partida em andamento",
  checkmate: "Xeque-mate",
  stalemate: "Empate por afogamento",
  draw_insufficient_material: "Empate por material insuficiente",
  draw_fifty_moves: "Empate pela regra dos cinquenta lances",
  draw_threefold_repetition: "Empate por tripla repetição",
}

export function sacrificeKindLabel(kind: Wire<SacrificeKind>): string {
  return Object.hasOwn(SACRIFICE_KINDS, kind)
    ? SACRIFICE_KINDS[kind as SacrificeKind]
    : "tipo não reconhecido"
}

export function pieceLabel(piece: Wire<PieceName>): string {
  return Object.hasOwn(PIECE_NAMES, piece) ? PIECE_NAMES[piece as PieceName] : "Peça"
}

export function terminalLabel(status: Wire<GameStatus>): string {
  return Object.hasOwn(TERMINAL_TEXTS, status)
    ? TERMINAL_TEXTS[status as GameStatus]
    : "Desfecho não reconhecido"
}

/**
 * Frases de evidência, na ordem em que a auditoria as mede. Cada uma diz o que
 * foi observado no tabuleiro, não o que a política sentiu.
 */
export function evidenceSentences(audit: CandidateAudit): string[] {
  const lines: string[] = []
  if (audit.terminal_status && audit.terminal_status !== "in_progress") {
    lines.push(
      audit.terminal_status === "checkmate"
        ? "Mate confirmado pelas regras do tabuleiro: não existe defesa legal."
        : `${terminalLabel(audit.terminal_status)} confirmado pelo tabuleiro: a partida termina aqui.`,
    )
  }
  if (audit.sacrifice) lines.push(...sacrificeSentences(audit.sacrifice))
  else lines.push("Nenhuma peça foi deixada capturável por este lance.")

  if (audit.best_defense_san && !audit.sacrifice?.accepted_by_best_defense) {
    lines.push(`Melhor defesa medida: ${audit.best_defense_san}.`)
  }
  if (audit.sacrifice && !passed(audit, "GATE_SACRIFICE_001")) {
    lines.push("A oferta foi detectada, mas a evidência reunida não bastou para o portão.")
  }
  return lines
}

function sacrificeSentences(sacrifice: Sacrifice): string[] {
  const piece = pieceLabel(sacrifice.offered_piece)
  const accepting = sacrifice.acceptance_san[0]
  const where = `${piece} em ${sacrifice.offered_square}`
  const lines = [
    accepting
      ? `${where} ficou capturável por ${accepting} (${sacrificeKindLabel(sacrifice.kind)}).`
      : `${where} foi oferecida (${sacrificeKindLabel(sacrifice.kind)}).`,
  ]
  if (sacrifice.accepted_by_best_defense) {
    lines.push(
      `A melhor defesa aceitou a oferta e ganhou ${formatMaterial(sacrifice.material_conceded)} de material.`,
    )
  } else {
    lines.push("A melhor defesa não aceitou a oferta.")
  }
  return lines
}

function passed(audit: CandidateAudit, gateId: string): boolean {
  return audit.gates.some((gate) => gate.gate_id === gateId && gate.status === "passed")
}

export function formatMaterial(value: number): string {
  return value.toFixed(1).replace(".", ",")
}

export function formatMeasure(value: number | string | boolean | null): string {
  if (value === null || value === undefined) return "não medido"
  if (typeof value === "boolean") return value ? "sim" : "não"
  if (typeof value !== "number") return String(value)
  return Math.abs(value) < 1 ? value.toFixed(4) : value.toFixed(2)
}

/** Posição do limiar e do valor medido numa escala comum, em porcentagem. */
export function meterPositions(
  measured: number | string | boolean | null,
  threshold: number | string | boolean | null,
): { measured: number; threshold: number } | null {
  if (typeof measured !== "number" || typeof threshold !== "number") return null
  const span = Math.max(Math.abs(measured), Math.abs(threshold)) * 1.35 || 1
  return {
    measured: Math.min(100, (Math.abs(measured) / span) * 100),
    threshold: Math.min(100, (Math.abs(threshold) / span) * 100),
  }
}

export function plieLabel(count: number): string {
  return count === 1 ? "1 meio-lance" : `${count} meios-lances`
}

/** Contagem por tipo de seleção de um lado, incluindo valores desconhecidos. */
export function selectionCounts(
  moves: MatchMove[],
): { kind: Wire<SelectionKind>; total: number }[] {
  const totals = new Map<Wire<SelectionKind>, number>(
    SELECTION_ORDER.map((kind) => [kind as Wire<SelectionKind>, 0]),
  )
  for (const move of moves) {
    totals.set(move.selection, (totals.get(move.selection) ?? 0) + 1)
  }
  return [...totals].map(([kind, total]) => ({ kind, total }))
}
