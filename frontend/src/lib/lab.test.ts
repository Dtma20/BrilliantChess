import { describe, expect, it } from "vitest"

import type { CandidateAudit, Gate, MatchMove } from "@/lib/api"
import {
  GATES,
  SELECTION_META,
  SELECTION_ORDER,
  UNKNOWN_SELECTION_META,
  evidenceSentences,
  formatMeasure,
  gateGlyph,
  gateTone,
  gateWord,
  meterPositions,
  pieceLabel,
  plieLabel,
  sacrificeKindLabel,
  selectionCounts,
  selectionMeta,
  terminalLabel,
} from "@/lib/lab"

function gate(id: string, status: Gate["status"]): Gate {
  return { gate_id: id, status, measured: null, threshold: null, explanation: "" }
}

function audit(overrides: Partial<CandidateAudit> = {}): CandidateAudit {
  return {
    selected_uci: "e2e3",
    selected_san: "e3",
    score: 41.2,
    rule_set_version: "strict_v1",
    gates: [gate("GATE_LEGAL_001", "passed"), gate("GATE_SACRIFICE_001", "failed")],
    reason_codes: [],
    sacrifice: null,
    best_defense_san: null,
    terminal_status: null,
    ...overrides,
  }
}

describe("GATES", () => {
  it("keeps the eight mandatory gates in the domain order", () => {
    expect(GATES.map((gate) => gate.id)).toEqual([
      "GATE_LEGAL_001",
      "GATE_QUALITY_001",
      "GATE_SACRIFICE_001",
      "GATE_SOUNDNESS_001",
      "GATE_NOT_BAD_AFTER_001",
      "GATE_NOT_ALREADY_WON_001",
      "GATE_STABILITY_001",
      "GATE_NON_OBVIOUS_001",
    ])
  })

  /* Estes operadores são copiados de `domain/gates.py`. Só `not_already_won`
     compara com `<` estrito; mostrar `≤` faz "1.0000 ≤ 0.9500 reprovado"
     parecer contradição na tela. */
  it("shows the exact comparison each gate applies in the domain", () => {
    expect(Object.fromEntries(GATES.map((gate) => [gate.id, gate.relation]))).toEqual({
      GATE_LEGAL_001: null,
      GATE_QUALITY_001: "≤",
      GATE_SACRIFICE_001: "≥",
      GATE_SOUNDNESS_001: "≤",
      GATE_NOT_BAD_AFTER_001: "≥",
      GATE_NOT_ALREADY_WON_001: "<",
      GATE_STABILITY_001: "≤",
      GATE_NON_OBVIOUS_001: null,
    })
  })
})

describe("SELECTION_META", () => {
  it("describes the safe near-brilliant selection returned by the API", () => {
    expect(SELECTION_META).toHaveProperty("near_brilliant")
  })

  it("gives every selection a distinct mark, so colour is never the only cue", () => {
    const marks = Object.values(SELECTION_META).map((meta) => meta.mark)
    expect(new Set(marks).size).toBe(marks.length)
  })
})

describe("formatMeasure", () => {
  it("keeps four decimals below one and two above", () => {
    expect(formatMeasure(0.0031)).toBe("0.0031")
    expect(formatMeasure(3.3)).toBe("3.30")
  })

  it("spells out booleans and missing measurements", () => {
    expect(formatMeasure(true)).toBe("sim")
    expect(formatMeasure(false)).toBe("não")
    expect(formatMeasure(null)).toBe("não medido")
  })
})

describe("meterPositions", () => {
  it("places a measurement below its threshold to the left of the tick", () => {
    const meter = meterPositions(0.0031, 0.015)
    expect(meter).not.toBeNull()
    expect(meter!.measured).toBeLessThan(meter!.threshold)
  })

  it("returns nothing when either side is not numeric", () => {
    expect(meterPositions(true, true)).toBeNull()
    expect(meterPositions(null, 0.015)).toBeNull()
  })
})

describe("plieLabel", () => {
  it("agrees in number", () => {
    expect(plieLabel(1)).toBe("1 meio-lance")
    expect(plieLabel(9)).toBe("9 meios-lances")
  })
})

describe("selectionMeta", () => {
  it("covers every selection the API can return", () => {
    for (const kind of SELECTION_ORDER) {
      expect(selectionMeta(kind)).toBe(SELECTION_META[kind])
    }
  })

  it("never implies that a near-brilliant move is brilliant", () => {
    expect(SELECTION_META.near_brilliant.description).not.toMatch(/brilhante\b/i)
    expect(SELECTION_META.near_brilliant.tone).toBe("safe")
  })

  it("falls back instead of crashing on an unknown value", () => {
    expect(selectionMeta("teleport_v9")).toBe(UNKNOWN_SELECTION_META)
    expect(selectionMeta("")).toBe(UNKNOWN_SELECTION_META)
  })
})

describe("gate vocabulary", () => {
  it("names the three known statuses", () => {
    expect([gateGlyph("passed"), gateGlyph("failed"), gateGlyph("indeterminate")]).toEqual([
      "✓",
      "✕",
      "?",
    ])
    expect(gateWord("failed")).toBe("reprovado")
  })

  it("treats anything it does not know as not approved", () => {
    expect(gateTone("quantum")).toBe("open")
    expect(gateWord("quantum")).toBe("não reconhecido")
    expect(gateGlyph("quantum")).toBe("?")
  })
})

describe("evidenceSentences", () => {
  it("names the offered piece, the square and the accepting move", () => {
    const lines = evidenceSentences(
      audit({
        sacrifice: {
          kind: "left_hanging",
          offered_square: "b1",
          offered_piece: "rook",
          nominal_value: 5,
          confidence: 0.35,
          acceptance_san: ["Bxb1"],
          accepted_by_best_defense: true,
          material_conceded: 5,
        },
      }),
    )

    expect(lines[0]).toBe("Torre em b1 ficou capturável por Bxb1 (peça deixada pendurada).")
    expect(lines[1]).toContain("A melhor defesa aceitou a oferta")
    expect(lines[1]).toContain("5,0")
  })

  it("says plainly when no piece was left capturable", () => {
    expect(evidenceSentences(audit())[0]).toBe(
      "Nenhuma peça foi deixada capturável por este lance.",
    )
  })

  it("leads with the board-confirmed mate instead of a missing search", () => {
    const lines = evidenceSentences(audit({ terminal_status: "checkmate" }))
    expect(lines[0]).toBe("Mate confirmado pelas regras do tabuleiro: não existe defesa legal.")
  })

  it("states an immediate draw as an outcome, not as missing evidence", () => {
    const lines = evidenceSentences(audit({ terminal_status: "draw_threefold_repetition" }))
    expect(lines[0]).toContain("Empate por tripla repetição confirmado pelo tabuleiro")
  })

  it("reports the measured best defense when the offer was declined", () => {
    const lines = evidenceSentences(audit({ best_defense_san: "Kg8" }))
    expect(lines).toContain("Melhor defesa medida: Kg8.")
  })
})

describe("domain vocabulary fallbacks", () => {
  it("translates the kinds and pieces the backend can send", () => {
    expect(sacrificeKindLabel("destination_offer")).toBe("oferta na casa de destino")
    expect(pieceLabel("queen")).toBe("Dama")
    expect(terminalLabel("stalemate")).toBe("Empate por afogamento")
  })

  it("degrades gracefully on unknown values", () => {
    expect(sacrificeKindLabel("wormhole")).toBe("tipo não reconhecido")
    expect(pieceLabel("dragon")).toBe("Peça")
    expect(terminalLabel("abandoned")).toBe("Desfecho não reconhecido")
  })
})

describe("selectionCounts", () => {
  it("keeps the five known kinds and adds whatever else arrived", () => {
    const moves = [
      { selection: "strict_v1" },
      { selection: "strict_v1" },
      { selection: "teleport_v9" },
    ] as MatchMove[]

    expect(selectionCounts(moves)).toEqual([
      { kind: "strict_v2", total: 0 },
      { kind: "strict_v1", total: 2 },
      { kind: "near_brilliant", total: 0 },
      { kind: "fallback", total: 0 },
      { kind: "normal", total: 0 },
      { kind: "teleport_v9", total: 1 },
    ])
  })
})
