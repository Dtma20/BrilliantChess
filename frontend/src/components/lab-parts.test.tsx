import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
  AuditDetail,
  EvidenceList,
  GateRail,
  SelectionLegend,
  SelectionMark,
} from "@/components/lab-parts"
import type { CandidateAudit, Gate, SelectionKind } from "@/lib/api"
import { SELECTION_ORDER } from "@/lib/lab"

const GATES: Gate[] = [
  {
    gate_id: "GATE_LEGAL_001",
    status: "passed",
    measured: true,
    threshold: true,
    explanation: "ok",
  },
  {
    gate_id: "GATE_QUALITY_001",
    status: "passed",
    measured: 0.0031,
    threshold: 0.015,
    explanation: "EP_loss=0.0031",
  },
  {
    gate_id: "GATE_SACRIFICE_001",
    status: "failed",
    measured: 1.0,
    threshold: 2.75,
    explanation: "sem sacrificio",
  },
  {
    gate_id: "GATE_STABILITY_001",
    status: "indeterminate",
    measured: null,
    threshold: 0.02,
    explanation: "nao executado",
  },
]

const AUDIT: CandidateAudit = {
  selected_uci: "c4f7",
  selected_san: "Bxf7+",
  score: 72.4,
  rule_set_version: "strict_v1",
  gates: GATES,
  reason_codes: ["GATE_LEGAL_001"],
  sacrifice: null,
  best_defense_san: null,
  terminal_status: null,
}

describe("GateRail", () => {
  it("always shows the seven slots, in order", () => {
    render(<GateRail gates={GATES} />)

    expect(screen.getAllByRole("img")).toHaveLength(7)
  })

  it("names each outcome in text, not only in colour", () => {
    render(<GateRail gates={GATES} />)

    expect(screen.getByLabelText("Qualidade: aprovado")).toBeInTheDocument()
    expect(screen.getByLabelText("Sacrifício: reprovado")).toBeInTheDocument()
    expect(screen.getByLabelText("Estabilidade: indeterminado")).toBeInTheDocument()
    expect(screen.getByLabelText("Solidez: indeterminado")).toBeInTheDocument()
  })

  it("does not approve a status it cannot recognise", () => {
    render(
      <GateRail
        gates={[
          { ...GATES[0], status: "quantum" },
          ...GATES.slice(1),
        ]}
      />,
    )

    expect(screen.getByLabelText("Legalidade: não reconhecido")).toBeInTheDocument()
  })
})

describe("SelectionMark", () => {
  it.each(SELECTION_ORDER)("names %s for screen readers", (kind: SelectionKind) => {
    render(<SelectionMark kind={kind} />)

    expect(screen.getByText(kind)).toBeInTheDocument()
  })

  it("renders an unknown selection without crashing", () => {
    render(<SelectionMark kind="teleport_v9" />)

    expect(screen.getByText("desconhecida")).toBeInTheDocument()
  })

  it("reserves the brass mark for strict_v1 alone", () => {
    const { container: strict } = render(<SelectionMark kind="strict_v1" />)
    const { container: near } = render(<SelectionMark kind="near_brilliant" />)

    expect(strict.firstElementChild?.className).toContain("text-brass")
    expect(near.firstElementChild?.className).not.toContain("text-brass")
  })
})

describe("SelectionLegend", () => {
  it("explains the four marks in words", () => {
    render(<SelectionLegend />)
    const items = screen.getAllByRole("listitem")

    expect(items).toHaveLength(4)
    expect(items[0]).toHaveTextContent("strict_v1")
    expect(items[1]).toHaveTextContent("reprovada em algum portão de classificação")
    expect(items[2]).toHaveTextContent("Nada passou pela auditoria")
    expect(items[3]).toHaveTextContent("sem nenhum critério de brilhantismo")
  })
})

describe("EvidenceList", () => {
  it("spells out the offered piece, the accepting move and what the defence did", () => {
    render(
      <EvidenceList
        audit={{
          ...AUDIT,
          sacrifice: {
            kind: "left_hanging",
            offered_square: "b1",
            offered_piece: "rook",
            nominal_value: 5,
            confidence: 0.5,
            acceptance_san: ["Bxb1"],
            accepted_by_best_defense: true,
            material_conceded: 5,
          },
        }}
      />,
    )

    expect(
      screen.getByText("Torre em b1 ficou capturável por Bxb1 (peça deixada pendurada)."),
    ).toBeInTheDocument()
    expect(screen.getByText(/A melhor defesa aceitou a oferta/)).toBeInTheDocument()
  })

  it("states a board-confirmed mate instead of missing evidence", () => {
    render(<EvidenceList audit={{ ...AUDIT, terminal_status: "checkmate" }} />)

    expect(
      screen.getByText("Mate confirmado pelas regras do tabuleiro: não existe defesa legal."),
    ).toBeInTheDocument()
  })
})

describe("AuditDetail", () => {
  it("leads with the score and keeps the gate table collapsed", () => {
    render(<AuditDetail audit={AUDIT} />)

    expect(screen.getByText("72.4")).toBeInTheDocument()
    expect(screen.getByText("Portões e medidas")).toBeInTheDocument()
    expect(screen.queryByText("EP_loss=0.0031")).not.toBeInTheDocument()
  })

  it("shows the measured evidence above the collapsed technical detail", () => {
    render(<AuditDetail audit={AUDIT} />)

    expect(
      screen.getByText("Nenhuma peça foi deixada capturável por este lance."),
    ).toBeInTheDocument()
  })
})
