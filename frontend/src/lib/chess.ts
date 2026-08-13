/**
 * Utilidades de tabuleiro puramente visuais.
 *
 * Nada aqui valida lance nem decide regra: a lista de lances legais e o estado
 * da partida vêm sempre do backend. Isto só sabe desenhar.
 */

import type { Color } from "@/lib/api"

export const FILES = "abcdefgh"

export type PieceType = "k" | "q" | "r" | "b" | "n" | "p"

export interface Piece {
  type: PieceType
  color: Color
}

/**
 * Os glifos pretos servem aos dois lados; a cor vem do CSS, então as duas
 * silhuetas são idênticas. U+FE0E força apresentação de texto onde U+265F
 * viraria emoji e ignoraria a cor.
 */
export const PIECE_GLYPHS: Record<PieceType, string> = {
  k: "♚︎",
  q: "♛︎",
  r: "♜︎",
  b: "♝︎",
  n: "♞︎",
  p: "♟︎",
}

export const PROMOTION_ORDER: PieceType[] = ["q", "r", "b", "n"]

export const PIECE_NAMES: Record<PieceType, string> = {
  k: "rei",
  q: "dama",
  r: "torre",
  b: "bispo",
  n: "cavalo",
  p: "peão",
}

export type PieceMap = Record<string, Piece>

export function parseFen(fen: string): { pieces: PieceMap; turn: Color } {
  const [placement, turn] = fen.split(" ")
  const pieces: PieceMap = {}
  placement.split("/").forEach((row, index) => {
    const rank = 8 - index
    let file = 0
    for (const symbol of row) {
      if (/\d/.test(symbol)) {
        file += Number(symbol)
        continue
      }
      pieces[FILES[file] + rank] = {
        type: symbol.toLowerCase() as PieceType,
        color: symbol === symbol.toUpperCase() ? "white" : "black",
      }
      file += 1
    }
  })
  return { pieces, turn: turn === "b" ? "black" : "white" }
}

export function allSquares(): string[] {
  const squares: string[] = []
  for (let rank = 8; rank >= 1; rank -= 1) {
    for (const file of FILES) squares.push(file + rank)
  }
  return squares
}

export function orderedSquares(orientation: Color): string[] {
  const squares = allSquares()
  return orientation === "white" ? squares : squares.reverse()
}

/** a1 e h8 são casas escuras: soma par é clara, soma ímpar é escura. */
export function isLightSquare(square: string): boolean {
  return (FILES.indexOf(square[0]) + Number(square[1])) % 2 === 0
}

export function kingSquare(fen: string, color: Color): string | null {
  const { pieces } = parseFen(fen)
  for (const [square, piece] of Object.entries(pieces)) {
    if (piece.type === "k" && piece.color === color) return square
  }
  return null
}

export function squareCenter(square: string, orientation: Color): { x: number; y: number } {
  const file = FILES.indexOf(square[0])
  const rank = Number(square[1])
  const column = orientation === "white" ? file : 7 - file
  const row = orientation === "white" ? 8 - rank : rank - 1
  return { x: column + 0.5, y: row + 0.5 }
}

/** Agrupa os SAN em lances completos, como numa súmula. */
export function toFullMoves(sanMoves: string[]): { number: number; white?: string; black?: string }[] {
  const rows: { number: number; white?: string; black?: string }[] = []
  for (let index = 0; index < sanMoves.length; index += 2) {
    rows.push({
      number: index / 2 + 1,
      white: sanMoves[index],
      black: sanMoves[index + 1],
    })
  }
  return rows
}

export const SIDE_NAMES: Record<Color, string> = { white: "Brancas", black: "Pretas" }
