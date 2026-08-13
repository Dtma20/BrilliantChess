import { describe, expect, it } from "vitest"

import { GATES, SELECTION_META, formatMeasure, meterPositions, plieLabel } from "@/lib/lab"

describe("GATES", () => {
  it("keeps the seven mandatory gates in the domain order", () => {
    expect(GATES.map((gate) => gate.id)).toEqual([
      "GATE_LEGAL_001",
      "GATE_QUALITY_001",
      "GATE_SACRIFICE_001",
      "GATE_SOUNDNESS_001",
      "GATE_NOT_BAD_AFTER_001",
      "GATE_NOT_ALREADY_WON_001",
      "GATE_STABILITY_001",
    ])
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
