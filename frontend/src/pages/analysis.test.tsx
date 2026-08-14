import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { BoardView } from "@/lib/api"
import { AnalysisPage } from "@/pages/analysis"

const apiMocks = vi.hoisted(() => ({
  analyze: vi.fn(),
  board: vi.fn(),
  importPgn: vi.fn(),
}))

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api")
  return { ...actual, api: apiMocks }
})

const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
const SAN = ["e4", "e5", "Nf3"]

function boardView(moves: string[]): BoardView {
  return {
    fen: STARTING_FEN,
    side_to_move: moves.length % 2 === 0 ? "white" : "black",
    status: "in_progress",
    is_check: false,
    legal_moves: [],
    last_move_uci: moves.at(-1) ?? null,
    move_number: Math.floor(moves.length / 2) + 1,
    moves_san: SAN.slice(0, moves.length),
  }
}

beforeEach(() => {
  apiMocks.board.mockImplementation(async ({ moves = [] }: { moves?: string[] }) =>
    boardView(moves),
  )
  apiMocks.analyze.mockResolvedValue({
    schema_version: "2",
    fen: STARTING_FEN,
    side_to_move: "white",
    engine_name: "Stub",
    engine_version: "1",
    nnue_name: null,
    expected_points_before: 0.5,
    candidates: [],
    arrows: [],
    warnings: [],
    board: boardView([]),
  })
  apiMocks.importPgn.mockResolvedValue({
    initial_fen: STARTING_FEN,
    moves_uci: ["e2e4", "e7e5", "g1f3"],
    moves_san: SAN,
  })
})

describe("AnalysisPage PGN navigation", () => {
  it("opens after the first move and advances one move at a time", async () => {
    const user = userEvent.setup()
    render(<AnalysisPage />)

    await user.click(screen.getByRole("button", { name: "Importar PGN" }))
    await user.type(screen.getByLabelText("PGN da partida"), "1. e4 e5 2. Nf3 *")
    await user.click(screen.getByRole("button", { name: "Carregar PGN" }))

    expect(await screen.findByText("Lance 1 de 3 · e4")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: "Próximo" }))

    await waitFor(() => expect(screen.getByText("Lance 2 de 3 · e5")).toBeInTheDocument())
  })
})
