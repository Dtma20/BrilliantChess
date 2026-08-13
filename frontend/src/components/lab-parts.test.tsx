import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AuditDetail, GateRail, SelectionLegend } from "@/components/lab-parts"
import type { CandidateAudit, Gate } from "@/lib/api"

const GATES: Gate[] = [
  { gate_id: "GATE_LEGAL_001", status: "passed", measured: true, threshold: true, explanation: "ok" },
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
})

describe("SelectionLegend", () => {
  it("explains the three marks in words", () => {
    render(<SelectionLegend />)
    const items = screen.getAllByRole("listitem")

    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent("strict_v1")
    expect(items[1]).toHaveTextContent("Nenhuma candidata passou")
    expect(items[2]).toHaveTextContent("sem nenhum critério de brilhantismo")
  })
})

describe("AuditDetail", () => {
  it("leads with the score and keeps the gate table collapsed", () => {
    render(<AuditDetail audit={AUDIT} />)

    expect(screen.getByText("72.4")).toBeInTheDocument()
    expect(screen.getByText("Portões e medidas")).toBeInTheDocument()
    expect(screen.queryByText("EP_loss=0.0031")).not.toBeInTheDocument()
  })
})
