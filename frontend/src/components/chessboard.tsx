import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import type { Arrow, Color } from "@/lib/api"
import {
  FILES,
  PIECE_GLYPHS,
  PIECE_NAMES,
  PROMOTION_ORDER,
  type PieceType,
  isLightSquare,
  orderedSquares,
  parseFen,
  squareCenter,
} from "@/lib/chess"
import { cn } from "@/lib/utils"

interface ChessboardProps {
  fen: string
  orientation?: Color
  interactive?: boolean
  legalMoves?: string[]
  lastMove?: string | null
  checkSquare?: string | null
  arrows?: Arrow[]
  onMove?: (uci: string) => void
  className?: string
  label?: string
}

interface DragState {
  from: string
  x: number
  y: number
}

interface PromotionState {
  to: string
  color: Color
  options: string[]
}

export function Chessboard({
  fen,
  orientation = "white",
  interactive = false,
  legalMoves = [],
  lastMove = null,
  checkSquare = null,
  arrows = [],
  onMove,
  className,
  label = "Tabuleiro",
}: ChessboardProps) {
  const [selected, setSelected] = useState<string | null>(null)
  const [focused, setFocused] = useState<string>(orientation === "white" ? "e2" : "e7")
  const [drag, setDrag] = useState<DragState | null>(null)
  const [promotion, setPromotion] = useState<PromotionState | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  const { pieces } = useMemo(() => parseFen(fen), [fen])
  const squares = useMemo(() => orderedSquares(orientation), [orientation])
  const lastMoveSquares = useMemo(
    () => (lastMove ? [lastMove.slice(0, 2), lastMove.slice(2, 4)] : []),
    [lastMove],
  )

  useEffect(() => {
    if (!interactive) setSelected(null)
  }, [interactive])

  useEffect(() => {
    setSelected(null)
    setPromotion(null)
  }, [fen])

  const targetsFrom = useCallback(
    (from: string) =>
      legalMoves.filter((uci) => uci.startsWith(from)).map((uci) => uci.slice(2, 4)),
    [legalMoves],
  )

  const attempt = useCallback(
    (from: string, to: string) => {
      const matches = legalMoves.filter((uci) => uci.slice(0, 4) === from + to)
      if (matches.length === 0) return false
      setSelected(null)
      if (matches.length > 1 && matches.every((uci) => uci.length === 5)) {
        setPromotion({ to, color: pieces[from]?.color ?? "white", options: matches })
        return true
      }
      onMove?.(matches[0])
      return true
    },
    [legalMoves, onMove, pieces],
  )

  const activate = useCallback(
    (square: string) => {
      if (!interactive) return
      if (selected && attempt(selected, square)) return
      if (!pieces[square] || targetsFrom(square).length === 0) {
        setSelected(null)
        return
      }
      setSelected(square)
    },
    [attempt, interactive, pieces, selected, targetsFrom],
  )

  function onPointerDown(event: React.PointerEvent, square: string) {
    if (!interactive || event.button !== 0) return
    const hadSelection = selected
    activate(square)
    if (hadSelection && hadSelection !== square) return
    if (!pieces[square] || targetsFrom(square).length === 0) return
    setDrag({ from: square, x: event.clientX, y: event.clientY })
    rootRef.current?.setPointerCapture?.(event.pointerId)
  }

  function onPointerMove(event: React.PointerEvent) {
    if (!drag) return
    setDrag({ ...drag, x: event.clientX, y: event.clientY })
  }

  function onPointerUp(event: React.PointerEvent) {
    if (!drag) return
    const { from } = drag
    setDrag(null)
    rootRef.current?.releasePointerCapture?.(event.pointerId)
    const element = document.elementFromPoint(event.clientX, event.clientY)
    const target = element?.closest<HTMLElement>("[data-square]")?.dataset.square
    if (target && target !== from) attempt(from, target)
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (!interactive) return
    // A casa corrente vem do DOM: teclas em sequencia rapida nao podem depender
    // de um estado que so chega no proximo render.
    const active = (document.activeElement as HTMLElement | null)?.dataset?.square
    const current = active && active.length === 2 ? active : focused
    const deltas: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, 1],
      ArrowDown: [0, -1],
    }
    if (event.key in deltas) {
      event.preventDefault()
      const flip = orientation === "white" ? 1 : -1
      const [dx, dy] = deltas[event.key]
      const file = Math.min(7, Math.max(0, FILES.indexOf(current[0]) + dx * flip))
      const rank = Math.min(8, Math.max(1, Number(current[1]) + dy * flip))
      const next = FILES[file] + rank
      setFocused(next)
      rootRef.current?.querySelector<HTMLElement>(`[data-square="${next}"]`)?.focus()
      return
    }
    // O gesto de mouse comeca no pointerdown, entao Enter e Espaco precisam
    // acionar a casa explicitamente e cancelar o clique sintetico do botao.
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      activate(current)
      return
    }
    if (event.key === "Escape" && selected) {
      event.preventDefault()
      setSelected(null)
    }
  }

  const hints = selected ? new Set(targetsFrom(selected)) : new Set<string>()
  const Square = interactive ? "button" : "div"

  return (
    <div className={cn("relative w-full", className)}>
      <div
        ref={rootRef}
        role={interactive ? "grid" : "img"}
        aria-label={label}
        className="relative aspect-square w-full touch-none overflow-hidden rounded-md shadow-[0_0_0_1px_var(--border-strong)] select-none [container-type:inline-size]"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => setDrag(null)}
        onLostPointerCapture={() => setDrag(null)}
        onKeyDown={onKeyDown}
        onContextMenu={(event) => event.preventDefault()}
      >
        <div className="grid h-full w-full grid-cols-8 grid-rows-8">
          {squares.map((square) => {
            const piece = pieces[square]
            const light = isLightSquare(square)
            const isTarget = hints.has(square)
            const bottomRank = orientation === "white" ? 1 : 8
            const leftFile = orientation === "white" ? "a" : "h"
            return (
              <Square
                key={square}
                data-square={square}
                {...(interactive
                  ? {
                      type: "button" as const,
                      role: "gridcell",
                      tabIndex: square === focused ? 0 : -1,
                      onFocus: () => setFocused(square),
                      onPointerDown: (event: React.PointerEvent) => onPointerDown(event, square),
                      "aria-label": describeSquare(square, piece?.type, piece?.color, isTarget),
                      "aria-pressed": selected === square,
                    }
                  : {})}
                className={cn(
                  "relative flex items-center justify-center p-0",
                  light ? "bg-board-light" : "bg-board-dark",
                  interactive && "cursor-pointer focus-visible:z-10",
                )}
              >
                {lastMoveSquares.includes(square) && (
                  <span className="absolute inset-0 bg-board-last-move" aria-hidden />
                )}
                {checkSquare === square && (
                  <span
                    className="absolute inset-0"
                    style={{
                      background:
                        "radial-gradient(circle, var(--board-check) 0%, transparent 72%)",
                    }}
                    aria-hidden
                  />
                )}
                {selected === square && (
                  <span className="absolute inset-0 bg-brass/40" aria-hidden />
                )}
                {Number(square[1]) === bottomRank && (
                  <span
                    className={cn(
                      "absolute right-[3px] bottom-[1px] text-[0.62rem] font-bold opacity-55",
                      light ? "text-board-dark" : "text-board-light",
                    )}
                    aria-hidden
                  >
                    {square[0]}
                  </span>
                )}
                {square[0] === leftFile && (
                  <span
                    className={cn(
                      "absolute top-[1px] left-[3px] text-[0.62rem] font-bold opacity-55",
                      light ? "text-board-dark" : "text-board-light",
                    )}
                    aria-hidden
                  >
                    {square[1]}
                  </span>
                )}
                {piece && (
                  <PieceGlyph
                    type={piece.type}
                    color={piece.color}
                    dimmed={drag?.from === square}
                  />
                )}
                {isTarget && (
                  <span
                    className={cn(
                      "pointer-events-none absolute z-[3]",
                      pieces[square]
                        ? "inset-[4%] rounded-full border-[5px] border-black/30"
                        : "h-[30%] w-[30%] rounded-full bg-black/30",
                    )}
                    aria-hidden
                  />
                )}
              </Square>
            )
          })}
        </div>

        {arrows.length > 0 && (
          <svg
            viewBox="0 0 8 8"
            preserveAspectRatio="none"
            className="pointer-events-none absolute inset-0 z-[4] h-full w-full"
            aria-hidden
          >
            {arrows.map((arrow, index) => (
              <ArrowShape
                key={`${arrow.from_square}${arrow.to_square}`}
                arrow={arrow}
                orientation={orientation}
                opacity={Math.max(0.45, 1 - index * 0.2)}
              />
            ))}
          </svg>
        )}

        {promotion && (
          <PromotionPicker
            state={promotion}
            onPick={(uci) => {
              setPromotion(null)
              onMove?.(uci)
            }}
            onCancel={() => setPromotion(null)}
          />
        )}
      </div>

      {drag && (
        <span
          className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-1/2"
          style={{ left: drag.x, top: drag.y }}
          aria-hidden
        >
          <PieceGlyph
            type={pieces[drag.from]?.type ?? "p"}
            color={pieces[drag.from]?.color ?? "white"}
            floating
          />
        </span>
      )}
    </div>
  )
}

function PieceGlyph({
  type,
  color,
  dimmed = false,
  floating = false,
}: {
  type: PieceType
  color: Color
  dimmed?: boolean
  floating?: boolean
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "pointer-events-none relative z-[2] leading-none",
        floating ? "text-[4.4rem]" : "text-[8.8cqi]",
        dimmed && "opacity-35",
        color === "white"
          ? "text-[#fdfdfd] [-webkit-text-stroke:1.4px_#22252b]"
          : "text-[#24262c] [-webkit-text-stroke:1.1px_#d9dde3]",
      )}
      style={{
        paintOrder: "stroke fill",
        textShadow: "0 1px 2px rgb(0 0 0 / 0.45)",
      }}
    >
      {PIECE_GLYPHS[type]}
    </span>
  )
}

function PromotionPicker({
  state,
  onPick,
  onCancel,
}: {
  state: PromotionState
  onPick: (uci: string) => void
  onCancel: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.querySelector("button")?.focus()
  }, [])
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Escolha a peça da promoção"
      className="absolute inset-0 z-10 flex items-center justify-center bg-[rgb(10_12_9_/_0.74)]"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel()
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel()
      }}
    >
      <div
        ref={ref}
        className="flex gap-2 rounded-lg border border-border bg-popover p-2 shadow-lg"
      >
        {PROMOTION_ORDER.map((type) => {
          const uci = state.options.find((option) => option.endsWith(type))
          if (!uci) return null
          return (
            <button
              key={type}
              type="button"
              onClick={() => onPick(uci)}
              title={`Promover a ${PIECE_NAMES[type]}`}
              className="flex h-14 w-14 items-center justify-center rounded-md border border-border bg-secondary text-3xl hover:border-brass"
            >
              <span
                aria-hidden
                className={
                  state.color === "white"
                    ? "text-[#fdfdfd] [-webkit-text-stroke:1.2px_#22252b]"
                    : "text-[#24262c] [-webkit-text-stroke:1px_#d9dde3]"
                }
                style={{ paintOrder: "stroke fill" }}
              >
                {PIECE_GLYPHS[type]}
              </span>
              <span className="sr-only">{PIECE_NAMES[type]}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function ArrowShape({
  arrow,
  orientation,
  opacity,
}: {
  arrow: Arrow
  orientation: Color
  opacity: number
}) {
  const start = squareCenter(arrow.from_square, orientation)
  const end = squareCenter(arrow.to_square, orientation)
  const dx = end.x - start.x
  const dy = end.y - start.y
  const length = Math.hypot(dx, dy) || 1
  const ux = dx / length
  const uy = dy / length
  const head = 0.3
  const halfHead = 0.19
  const tipX = end.x - ux * 0.06
  const tipY = end.y - uy * 0.06
  const baseX = tipX - ux * head
  const baseY = tipY - uy * head
  const points = [
    `${tipX},${tipY}`,
    `${baseX - uy * halfHead},${baseY + ux * halfHead}`,
    `${baseX + uy * halfHead},${baseY - ux * halfHead}`,
  ].join(" ")

  return (
    <g opacity={opacity}>
      <line
        x1={start.x + ux * 0.18}
        y1={start.y + uy * 0.18}
        x2={baseX}
        y2={baseY}
        stroke={arrow.color}
        strokeWidth={0.13}
        strokeLinecap="round"
      />
      <polygon points={points} fill={arrow.color} />
    </g>
  )
}

function describeSquare(
  square: string,
  type: PieceType | undefined,
  color: Color | undefined,
  isTarget: boolean,
): string {
  const occupant = type
    ? `${PIECE_NAMES[type]} ${color === "white" ? "branco" : "preto"}`
    : "vazia"
  return `${square}, ${occupant}${isTarget ? ", destino possível" : ""}`
}
