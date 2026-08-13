import { useEffect, useState } from "react"

import { Chessboard } from "@/components/chessboard"
import { PageHeader } from "@/components/page-header"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { STARTING_FEN, api, downloadPgn, type Color, type Game, type Strength } from "@/lib/api"
import { SIDE_NAMES, kingSquare, toFullMoves } from "@/lib/chess"

export function PlayPage() {
  const [strengths, setStrengths] = useState<Strength[] | null>(null)
  const [humanColor, setHumanColor] = useState<Color>("white")
  const [strengthKey, setStrengthKey] = useState("clube")
  const [orientation, setOrientation] = useState<Color>("white")
  const [game, setGame] = useState<Game | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    api
      .strengths()
      .then(setStrengths)
      .catch((cause: Error) => setError(cause.message))
  }, [])

  const view = game?.board
  const finished = Boolean(view) && view!.status !== "in_progress"
  const myTurn = Boolean(game) && !finished && view!.side_to_move === game!.human_color

  async function run(action: () => Promise<Game>) {
    setBusy(true)
    setError("")
    try {
      setGame(await action())
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function startGame() {
    setOrientation(humanColor)
    void run(() => api.createGame({ human_color: humanColor, strength_key: strengthKey }))
  }

  function status() {
    if (!game) return "Escolha as peças e comece."
    if (busy) return "Motor pensando…"
    if (finished) return game.result_text
    const turn = myTurn ? "Sua vez" : "Vez do motor"
    return `${turn} · lance ${game.board.move_number} · ${game.strength.label}`
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section className="grid gap-4">
        <PageHeader
          title="Partida contra o motor"
          lede="O motor joga no perfil escolhido. Nada sai desta máquina."
        />
        <div className="mx-auto w-full max-w-[min(100%,calc(100vh-18rem))]">
          <Chessboard
            fen={view?.fen ?? STARTING_FEN}
            orientation={orientation}
            interactive={myTurn && !busy}
            legalMoves={myTurn ? (view?.legal_moves ?? []) : []}
            lastMove={view?.last_move_uci ?? null}
            checkSquare={
              view?.is_check ? kingSquare(view.fen, view.side_to_move) : null
            }
            onMove={(uci) => game && void run(() => api.playMove(game.game_id, uci))}
            label={game ? "Tabuleiro da partida" : "Tabuleiro na posição inicial"}
          />
        </div>
      </section>

      <aside className="grid gap-4">
        <Card className="gap-4 p-5">
          <h2 className="m-0 label-micro">Nova partida</h2>

          <div className="grid gap-1.5">
            <Label htmlFor="color">Suas peças</Label>
            <Select
              value={humanColor}
              onValueChange={(value) => setHumanColor(value as Color)}
              disabled={busy}
            >
              <SelectTrigger id="color" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="white">Brancas</SelectItem>
                <SelectItem value="black">Pretas</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="strength">Força do motor</Label>
            {strengths ? (
              <Select value={strengthKey} onValueChange={setStrengthKey} disabled={busy}>
                <SelectTrigger id="strength" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {strengths.map((level) => (
                    <SelectItem key={level.key} value={level.key}>
                      {level.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Skeleton className="h-9 w-full" />
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={startGame} disabled={busy || !strengths} className="flex-1">
              Começar
            </Button>
            <Button
              variant="outline"
              onClick={() => game && void run(() => api.undo(game.game_id))}
              disabled={busy || !game || game.moves_uci.length === 0}
            >
              Voltar lance
            </Button>
            <Button
              variant="outline"
              onClick={() => setOrientation(orientation === "white" ? "black" : "white")}
            >
              Girar
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                game &&
                downloadPgn(api.gamePgnUrl(game.game_id), `brilliant-chess-${game.game_id}.pgn`)
              }
              disabled={busy || !game || game.moves_uci.length === 0}
            >
              PGN
            </Button>
          </div>
        </Card>

        <Card className="gap-3 p-5">
          <h2 className="m-0 label-micro">Situação</h2>

          <p
            role="status"
            aria-live="polite"
            className="m-0 flex items-center gap-2.5 text-[0.92rem]"
          >
            <span
              aria-hidden
              className={
                busy
                  ? "size-2.5 shrink-0 animate-breathe rounded-full bg-brass"
                  : finished
                    ? "size-2.5 shrink-0 rounded-[1px] bg-baize"
                    : myTurn
                      ? "size-2.5 shrink-0 rounded-full border-[1.5px] border-foreground"
                      : "size-2.5 shrink-0 rounded-full border-[1.5px] border-ink-4"
              }
            />
            {status()}
          </p>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div>
            <span className="label-micro">Lances</span>
            {game && game.moves_san.length > 0 ? (
              <ScrollArea className="mt-1.5 h-44">
                <ol className="m-0 grid list-none grid-cols-[2.2rem_1fr_1fr] gap-x-1 gap-y-0.5 p-0">
                  {toFullMoves(game.moves_san).map((row) => (
                    <li key={row.number} className="contents">
                      <span className="self-center text-right numeric text-[0.74rem] text-ink-4">
                        {row.number}.
                      </span>
                      <span className="px-1 text-[0.85rem]">{row.white}</span>
                      <span className="px-1 text-[0.85rem]">{row.black ?? ""}</span>
                    </li>
                  ))}
                </ol>
              </ScrollArea>
            ) : (
              <p className="mt-1.5 mb-0 max-w-[40ch] text-[0.84rem] text-ink-4">
                Nenhum lance ainda. As {SIDE_NAMES[humanColor].toLowerCase()} são suas.
              </p>
            )}
          </div>
        </Card>
      </aside>
    </div>
  )
}
