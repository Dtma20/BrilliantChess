import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { BoardView, Match } from "@/lib/api"
import { LabPage } from "@/pages/lab"

const apiMocks = vi.hoisted(() => ({
  board: vi.fn(),
  createMatch: vi.fn(),
  lab: vi.fn(),
  stepMatch: vi.fn(),
  strengths: vi.fn(),
}))

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api")
  return { ...actual, api: apiMocks }
})

const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
const AFTER_E4_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"

function board(fen: string, movesSan: string[]): BoardView {
  return {
    fen,
    side_to_move: movesSan.length % 2 === 0 ? "white" : "black",
    status: "in_progress",
    is_check: false,
    legal_moves: [],
    last_move_uci: movesSan.length === 0 ? null : movesSan.length === 1 ? "e2e4" : "e7e5",
    move_number: Math.floor(movesSan.length / 2) + 1,
    moves_san: movesSan,
  }
}

const PROFILE = { strength: { key: "maximo", label: "Máximo", elo: null }, policy: "normal" } as const

const EMPTY_MATCH: Match = {
  schema_version: "2",
  match_id: "m1",
  initial_fen: STARTING_FEN,
  white: PROFILE,
  black: PROFILE,
  board: board(STARTING_FEN, []),
  moves_uci: [],
  moves_san: [],
  moves: [],
  result_text: "Em andamento",
  can_step: true,
}

const PLAYED_MATCH: Match = {
  ...EMPTY_MATCH,
  board: board(AFTER_E4_E5, ["e4", "e5"]),
  moves_uci: ["e2e4", "e7e5"],
  moves_san: ["e4", "e5"],
  moves: [
    { color: "white", uci: "e2e4", san: "e4", selection: "normal", fallback: false, audit: null },
    { color: "black", uci: "e7e5", san: "e5", selection: "normal", fallback: false, audit: null },
  ],
}

beforeEach(() => {
  apiMocks.lab.mockResolvedValue({
    schema_version: "2",
    max_fullmoves: 100,
    max_plies: 200,
    autoplay_delay_ms: 250,
  })
  apiMocks.strengths.mockResolvedValue([
    { key: "maximo", label: "Máximo", elo: null },
    { key: "iniciante", label: "Iniciante", elo: 800 },
  ])
  apiMocks.createMatch.mockResolvedValue(EMPTY_MATCH)
  apiMocks.stepMatch.mockResolvedValue(PLAYED_MATCH)
  apiMocks.board.mockResolvedValue(board(AFTER_E4, ["e4"]))
})

describe("LabPage FEN export", () => {
  it("copies the exact position being reviewed", async () => {
    const user = userEvent.setup()
    const writeText = vi.spyOn(navigator.clipboard, "writeText")
    render(<LabPage />)

    await user.click(await screen.findByRole("button", { name: "Um lance" }))
    await user.click(await screen.findByRole("button", { name: /e4/ }))
    const copy = await screen.findByRole("button", { name: "Copiar FEN" })
    await waitFor(() => expect(copy).toBeEnabled())
    await user.click(copy)

    expect(writeText).toHaveBeenCalledWith(AFTER_E4)
  })
})

describe("LabPage command hierarchy", () => {
  it("gives the primary duel action its own row above four secondary commands", async () => {
    render(<LabPage />)

    const primary = await screen.findByRole("group", { name: "Ação principal do duelo" })
    const secondary = screen.getByRole("group", { name: "Comandos auxiliares do duelo" })

    expect(within(primary).getAllByRole("button")).toHaveLength(1)
    expect(within(primary).getByRole("button", { name: "Iniciar duelo" })).toHaveClass("w-full")
    expect(within(secondary).getAllByRole("button")).toHaveLength(4)
    expect(secondary).toHaveClass("grid-cols-4")
  })
})
