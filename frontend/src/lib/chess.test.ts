import { describe, expect, it } from "vitest"

import { STARTING_FEN } from "@/lib/api"
import { isLightSquare, kingSquare, orderedSquares, parseFen, toFullMoves } from "@/lib/chess"

describe("parseFen", () => {
  it("reads both colours from the starting position", () => {
    const { pieces, turn } = parseFen(STARTING_FEN)

    expect(turn).toBe("white")
    expect(pieces.a1).toEqual({ type: "r", color: "white" })
    expect(pieces.a7).toEqual({ type: "p", color: "black" })
    expect(pieces.e8).toEqual({ type: "k", color: "black" })
    expect(pieces.d4).toBeUndefined()
  })

  it("reports the side to move from the FEN", () => {
    expect(parseFen("8/8/8/8/8/8/8/K6k b - - 0 1").turn).toBe("black")
  })
})

describe("isLightSquare", () => {
  it("keeps a1 dark and h1 light, as on a real board", () => {
    expect(isLightSquare("a1")).toBe(false)
    expect(isLightSquare("h1")).toBe(true)
    expect(isLightSquare("a8")).toBe(true)
    expect(isLightSquare("h8")).toBe(false)
  })
})

describe("orderedSquares", () => {
  it("puts a8 first for white and h1 first for black", () => {
    expect(orderedSquares("white")[0]).toBe("a8")
    expect(orderedSquares("black")[0]).toBe("h1")
    expect(orderedSquares("white")).toHaveLength(64)
  })
})

describe("kingSquare", () => {
  it("finds each king", () => {
    expect(kingSquare(STARTING_FEN, "white")).toBe("e1")
    expect(kingSquare(STARTING_FEN, "black")).toBe("e8")
  })
})

describe("toFullMoves", () => {
  it("pairs plies into numbered full moves", () => {
    expect(toFullMoves(["e4", "e5", "Nf3"])).toEqual([
      { number: 1, white: "e4", black: "e5" },
      { number: 2, white: "Nf3", black: undefined },
    ])
  })
})
