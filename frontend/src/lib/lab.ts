/**
 * Vocabulário do laboratório.
 *
 * As três marcas de escolha se distinguem por matiz (a política em jogo) e por
 * preenchimento (se a política achou algo), nunca só por cor. Os sete portões
 * aparecem sempre na mesma ordem, que é a ordem de `domain/gates.py`.
 */

import type { GateStatus, SelectionKind } from "@/lib/api"

export interface SelectionMeta {
  mark: string
  label: string
  short: string
  description: string
}

export const SELECTION_META: Record<SelectionKind, SelectionMeta> = {
  strict_v1: {
    mark: "◆",
    label: "strict_v1",
    short: "aprovada nos sete portões",
    description: "Candidata aprovada nos sete portões, com auditoria completa.",
  },
  fallback: {
    mark: "◇",
    label: "fallback",
    short: "nenhuma candidata passou",
    description: "Nenhuma candidata passou; o lado jogou a melhor jogada do perfil.",
  },
  normal: {
    mark: "·",
    label: "normal",
    short: "sem critério de brilhantismo",
    description: "Stockfish no perfil de força, sem nenhum critério de brilhantismo.",
  },
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

export const GATE_GLYPHS: Record<GateStatus, string> = {
  passed: "✓",
  failed: "✕",
  indeterminate: "?",
}

export const GATE_WORDS: Record<GateStatus, string> = {
  passed: "aprovado",
  failed: "reprovado",
  indeterminate: "indeterminado",
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
