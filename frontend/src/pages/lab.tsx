import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { Chessboard } from "@/components/chessboard"
import { AuditDetail, SelectionLegend, SelectionMark } from "@/components/lab-parts"
import { PageHeader } from "@/components/page-header"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  STARTING_FEN,
  api,
  downloadPgn,
  type BoardView,
  type Color,
  type LabSettings,
  type Match,
  type MatchPolicy,
  type MatchProfileInput,
  type SelectionKind,
  type Strength,
} from "@/lib/api"
import { SIDE_NAMES, kingSquare } from "@/lib/chess"
import { SELECTION_META, plieLabel } from "@/lib/lab"
import { cn } from "@/lib/utils"

type DeckState = "idle" | "thinking" | "paused" | "review" | "done" | "capped" | "error"

const SELECTION_ORDER: SelectionKind[] = ["strict_v1", "fallback", "normal"]

export function LabPage() {
  const [settings, setSettings] = useState<LabSettings | null>(null)
  const [strengths, setStrengths] = useState<Strength[] | null>(null)
  const [white, setWhite] = useState<MatchProfileInput>({
    strength_key: "maximo",
    policy: "strict_v1",
  })
  const [black, setBlack] = useState<MatchProfileInput>({
    strength_key: "iniciante",
    policy: "normal",
  })
  const [match, setMatch] = useState<Match | null>(null)
  const [running, setRunning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [reviewView, setReviewView] = useState<BoardView | null>(null)
  const [error, setError] = useState("")

  const matchRef = useRef<Match | null>(null)
  const runningRef = useRef(false)
  const busyRef = useRef(false)
  const delayRef = useRef(250)
  const timerRef = useRef<number | null>(null)
  const stepRef = useRef<() => Promise<void>>(async () => {})
  const positions = useRef(new Map<number, BoardView>())
  const ribbonRef = useRef<HTMLOListElement>(null)

  matchRef.current = match
  runningRef.current = running
  busyRef.current = busy
  delayRef.current = settings?.autoplay_delay_ms ?? 250

  useEffect(() => {
    Promise.all([api.lab(), api.strengths()])
      .then(([lab, levels]) => {
        setSettings(lab)
        setStrengths(levels)
      })
      .catch((cause: Error) => setError(cause.message))
  }, [])

  const stop = useCallback(() => {
    setRunning(false)
    runningRef.current = false
    if (timerRef.current) window.clearTimeout(timerRef.current)
    timerRef.current = null
  }, [])

  /* O autoplay vive só nesta página: sair dela ou fechar a aba encerra o duelo.
     Não existe laço de partida no servidor. */
  useEffect(() => stop, [stop])
  useEffect(() => {
    window.addEventListener("pagehide", stop)
    return () => window.removeEventListener("pagehide", stop)
  }, [stop])

  const schedule = useCallback(() => {
    if (!runningRef.current || busyRef.current) return
    if (!matchRef.current?.can_step) {
      setRunning(false)
      runningRef.current = false
      return
    }
    timerRef.current = window.setTimeout(() => void stepRef.current(), delayRef.current)
  }, [])

  const step = useCallback(async () => {
    const current = matchRef.current
    if (!current || busyRef.current || !current.can_step) return
    setBusy(true)
    busyRef.current = true
    try {
      // Um pedido já em voo não é cancelável: o lance chega mesmo depois da
      // pausa. A seleção de quem está revisando sobrevive a ele.
      const next = await api.stepMatch(current.match_id)
      setMatch(next)
      matchRef.current = next
      setError("")
    } catch (cause) {
      setError((cause as Error).message)
      stop()
    } finally {
      setBusy(false)
      busyRef.current = false
      schedule()
    }
  }, [schedule, stop])

  stepRef.current = step

  const ensureMatch = useCallback(async () => {
    if (matchRef.current) return true
    setBusy(true)
    busyRef.current = true
    try {
      const created = await api.createMatch({ white, black })
      positions.current.clear()
      setMatch(created)
      matchRef.current = created
      setSelected(null)
      setError("")
      return true
    } catch (cause) {
      setError((cause as Error).message)
      return false
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }, [black, white])

  const plies = match?.moves.length ?? 0
  const finished = Boolean(match) && !match!.can_step
  const capped = finished && plies >= (settings?.max_plies ?? 200)
  const reviewing = selected !== null && selected < plies - 1
  const viewedPly = selected ?? plies - 1

  useEffect(() => {
    if (!match || !reviewing || selected === null) {
      setReviewView(null)
      return
    }
    const cached = positions.current.get(selected)
    if (cached) {
      setReviewView(cached)
      return
    }
    let alive = true
    api
      .board({ fen: match.initial_fen, moves: match.moves_uci.slice(0, selected + 1) })
      .then((next) => {
        positions.current.set(selected, next)
        if (alive) setReviewView(next)
      })
      .catch((cause: Error) => setError(cause.message))
    return () => {
      alive = false
    }
  }, [match, reviewing, selected])

  const selectPly = useCallback(
    (index: number) => {
      if (!matchRef.current || index < 0 || index >= (matchRef.current.moves.length ?? 0)) return
      if (index < matchRef.current.moves.length - 1) stop()
      setSelected(index === matchRef.current.moves.length - 1 ? null : index)
    },
    [stop],
  )

  async function toggle() {
    if (running) {
      stop()
      return
    }
    if (!(await ensureMatch())) return
    if (!matchRef.current?.can_step) return
    setSelected(null)
    setRunning(true)
    runningRef.current = true
    void step()
  }

  async function stepOnce() {
    stop()
    if (!(await ensureMatch())) return
    setSelected(null)
    await step()
  }

  function reset() {
    stop()
    positions.current.clear()
    setMatch(null)
    matchRef.current = null
    setSelected(null)
    setReviewView(null)
    setError("")
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const tag = (event.target as HTMLElement | null)?.tagName ?? ""
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(tag)) return
      if (event.code === "Space") {
        event.preventDefault()
        void toggle()
      } else if (event.key.toLowerCase() === "n") {
        event.preventDefault()
        void stepOnce()
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  })

  const deck = useMemo((): { state: DeckState; text: string } => {
    if (!match) return { state: "idle", text: "Pronto para iniciar." }
    if (capped) return { state: "capped", text: match.result_text }
    if (finished) return { state: "done", text: match.result_text }
    if (busy) return { state: "thinking", text: `${SIDE_NAMES[match.board.side_to_move]} analisando…` }
    if (reviewing && selected !== null) {
      return { state: "review", text: `Revisão do meio-lance ${selected + 1} de ${plies}.` }
    }
    if (error) return { state: "error", text: "Duelo interrompido." }
    if (running) return { state: "thinking", text: "Duelo em andamento." }
    if (plies === 0) return { state: "paused", text: "Perfis prontos. Falta iniciar." }
    return { state: "paused", text: `Em pausa após ${plieLabel(plies)}.` }
  }, [busy, capped, error, finished, match, plies, reviewing, running, selected])

  const boardView = reviewing ? reviewView : match?.board
  const maxPlies = settings?.max_plies ?? 200
  const cadence = Math.min(1, plies / maxPlies)
  const move = match?.moves[viewedPly]

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
      <section className="grid gap-3.5 lg:sticky lg:top-6 lg:mx-auto lg:w-full lg:max-w-[min(100%,calc(100vh-19rem))]">
        <PageHeader
          title="Laboratório de duelo"
          lede={
            <>
              Dois processos do mesmo Stockfish, um contra o outro.{" "}
              <code className="text-ink-2">normal</code> joga a melhor jogada do perfil;{" "}
              <code className="text-brass">strict_v1</code> só aceita uma candidata que passe pelos
              sete portões.
            </>
          }
        />

        <Card className="gap-2.5 px-4 py-3.5">
          <div className="flex items-center gap-2.5">
            <StateMark state={deck.state} />
            <span role="status" aria-live="polite" className="text-[0.95rem] font-medium">
              {deck.text}
            </span>
            <span className="ml-auto shrink-0 numeric text-[0.78rem] text-ink-3">
              {plies}/{maxPlies} meios-lances
            </span>
          </div>
          <div
            className="relative h-[3px] overflow-hidden rounded-full bg-elevated"
            role="img"
            aria-label={
              plies === 0
                ? "Nenhum meio-lance jogado"
                : `${plies} de ${maxPlies} meios-lances do limite experimental`
            }
          >
            <span
              className={cn(
                "block h-full transition-[width] duration-300",
                cadence >= 0.9 ? "bg-destructive" : "bg-brass",
              )}
              style={{ width: `${cadence * 100}%` }}
            />
          </div>
        </Card>

        <Chessboard
          fen={boardView?.fen ?? STARTING_FEN}
          lastMove={boardView?.last_move_uci ?? null}
          checkSquare={
            boardView?.is_check ? kingSquare(boardView.fen, boardView.side_to_move) : null
          }
          label="Tabuleiro do duelo, somente leitura"
        />
      </section>

      <aside className="grid gap-4">
        <Card className="gap-3 p-5">
          <h2 className="m-0 label-micro">Perfis</h2>
          <div className="grid gap-2">
            <SideRow
              color="white"
              profile={white}
              onChange={setWhite}
              strengths={strengths}
              locked={Boolean(match)}
              thinking={busy && match?.board.side_to_move === "white"}
              moves={match?.moves ?? []}
            />
            <SideRow
              color="black"
              profile={black}
              onChange={setBlack}
              strengths={strengths}
              locked={Boolean(match)}
              thinking={busy && match?.board.side_to_move === "black"}
              moves={match?.moves ?? []}
            />
          </div>
          <p className="m-0 max-w-[46ch] text-[0.82rem] text-ink-3">
            A política estrita é mais lenta: cada lance passa por descoberta, confirmação, melhor
            defesa e estabilidade antes de decidir.
          </p>
        </Card>

        <Card className="gap-3 p-5">
          <h2 className="m-0 label-micro">Controles</h2>
          <div className="flex flex-wrap gap-2">
            {/* Pausar precisa funcionar justamente enquanto o motor pensa, então
                este botão não é desabilitado por `busy`. */}
            <Button
              onClick={() => void toggle()}
              disabled={finished || (busy && !match)}
              className="flex-1"
            >
              {running ? "Pausar" : match && plies > 0 ? "Continuar" : "Iniciar duelo"}
            </Button>
            <Button
              variant="outline"
              onClick={() => void stepOnce()}
              disabled={busy || running || finished}
            >
              Um lance
            </Button>
            <Button variant="outline" onClick={reset} disabled={busy || !match}>
              Reiniciar
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                match &&
                downloadPgn(
                  api.matchPgnUrl(match.match_id),
                  `brilliant-chess-lab-${match.match_id}.pgn`,
                )
              }
              disabled={busy || !match || plies === 0}
            >
              PGN
            </Button>
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <p className="m-0 text-[0.72rem] text-ink-4">
            <Kbd>Espaço</Kbd> inicia ou pausa · <Kbd>N</Kbd> avança um lance · <Kbd>↑</Kbd>{" "}
            <Kbd>↓</Kbd> percorrem a lista de lances
          </p>
        </Card>

        <Card className="gap-3 p-5">
          <h2 className="m-0 label-micro">Lances</h2>
          <SelectionLegend />
          {plies === 0 ? (
            <p className="m-0 max-w-[44ch] text-[0.84rem] text-ink-4">
              Nenhum lance ainda. Ajuste os perfis e inicie o duelo.
            </p>
          ) : (
            <>
              <ScrollArea className="h-72">
                <ol
                  ref={ribbonRef}
                  aria-label="Lances da partida"
                  className="m-0 grid list-none grid-cols-[2.2rem_1fr_1fr] gap-x-1 gap-y-0.5 p-0"
                  onKeyDown={(event) => {
                    const deltas: Record<string, number> = {
                      ArrowUp: -2,
                      ArrowDown: 2,
                      ArrowLeft: -1,
                      ArrowRight: 1,
                    }
                    let next = viewedPly
                    if (event.key === "Home") next = 0
                    else if (event.key === "End") next = plies - 1
                    else if (event.key in deltas) next = viewedPly + deltas[event.key]
                    else return
                    event.preventDefault()
                    next = Math.max(0, Math.min(plies - 1, next))
                    selectPly(next)
                    window.requestAnimationFrame(() =>
                      ribbonRef.current
                        ?.querySelector<HTMLButtonElement>(`[data-ply="${next}"]`)
                        ?.focus(),
                    )
                  }}
                >
                  {Array.from({ length: Math.ceil(plies / 2) }, (_, row) => (
                    <li key={row} className="contents">
                      <span className="self-center pr-0.5 text-right numeric text-[0.74rem] text-ink-4">
                        {row + 1}.
                      </span>
                      <PlyButton
                        index={row * 2}
                        move={match!.moves[row * 2]}
                        current={viewedPly}
                        onSelect={selectPly}
                      />
                      {match!.moves[row * 2 + 1] ? (
                        <PlyButton
                          index={row * 2 + 1}
                          move={match!.moves[row * 2 + 1]}
                          current={viewedPly}
                          onSelect={selectPly}
                        />
                      ) : (
                        <span />
                      )}
                    </li>
                  ))}
                </ol>
              </ScrollArea>
              {reviewing && (
                <p className="m-0 text-[0.8rem] text-ink-3">
                  Autoplay pausado para revisão.{" "}
                  <button
                    type="button"
                    onClick={() => setSelected(null)}
                    className="rounded-sm underline decoration-brass/60 underline-offset-2 hover:text-foreground"
                  >
                    Voltar ao lance atual
                  </button>
                </p>
              )}
            </>
          )}
        </Card>

        <Card className="gap-2 p-5">
          <h2 className="m-0 label-micro">Auditoria</h2>
          {!match ? (
            <p className="m-0 max-w-[44ch] text-[0.84rem] text-ink-4">
              Inicie o duelo para ver como cada lance foi escolhido.
            </p>
          ) : !move ? (
            <p className="m-0 max-w-[44ch] text-[0.84rem] text-ink-4">
              Ainda não há lances. A auditoria aparece a partir do primeiro.
            </p>
          ) : (
            <>
              <Verdict match={match} index={viewedPly} />
              {move.audit && <AuditDetail audit={move.audit} />}
            </>
          )}
        </Card>
      </aside>
    </div>
  )
}

function Verdict({ match, index }: { match: Match; index: number }) {
  const move = match.moves[index]
  const profile = move.color === "white" ? match.white : match.black
  const label = profile.strength.label

  if (move.selection === "strict_v1") {
    return (
      <p className="m-0 mb-2 text-[0.88rem] text-ink-2">
        <strong className="font-semibold text-foreground">{move.san}</strong> passou pelos sete
        portões obrigatórios e foi a candidata elegível de maior pontuação.
      </p>
    )
  }
  if (move.selection === "fallback") {
    return (
      <p className="m-0 mb-2 text-[0.88rem] text-ink-2">
        Nenhuma candidata passou pelos sete portões nesta posição. {SIDE_NAMES[move.color]} jogaram{" "}
        <strong className="font-semibold text-foreground">{move.san}</strong>, a melhor jogada do
        perfil {label}.
      </p>
    )
  }
  return (
    <p className="m-0 mb-2 text-[0.88rem] text-ink-2">
      <strong className="font-semibold text-foreground">{move.san}</strong> veio do Stockfish no
      perfil {label}. A política normal não aplica nenhum critério de brilhantismo.
    </p>
  )
}

function PlyButton({
  index,
  move,
  current,
  onSelect,
}: {
  index: number
  move: Match["moves"][number]
  current: number
  onSelect: (index: number) => void
}) {
  const active = index === current
  return (
    <button
      type="button"
      data-ply={index}
      tabIndex={active ? 0 : -1}
      aria-current={active || undefined}
      onClick={() => onSelect(index)}
      className={cn(
        "flex w-full items-baseline justify-between gap-2 rounded-sm border border-transparent px-1.5 py-0.5 text-left text-[0.85rem] text-ink-2",
        active
          ? "border-border-strong bg-elevated text-foreground"
          : "hover:border-border-soft hover:bg-secondary",
      )}
      title={`${SIDE_NAMES[move.color]} · ${SELECTION_META[move.selection].label}`}
    >
      <span className="font-medium">{move.san}</span>
      <SelectionMark kind={move.selection} className="text-[0.8rem]" />
    </button>
  )
}

function SideRow({
  color,
  profile,
  onChange,
  strengths,
  locked,
  thinking,
  moves,
}: {
  color: Color
  profile: MatchProfileInput
  onChange: (next: MatchProfileInput) => void
  strengths: Strength[] | null
  locked: boolean
  thinking: boolean
  moves: Match["moves"]
}) {
  const counts = SELECTION_ORDER.map((kind) => ({
    kind,
    total: moves.filter((move) => move.color === color && move.selection === kind).length,
  }))
  const played = counts.reduce((sum, item) => sum + item.total, 0)

  return (
    <div
      className={cn(
        "grid gap-2 rounded-md border border-border-soft border-l-2 bg-secondary px-3 py-2.5",
        thinking ? "border-l-brass" : "border-l-transparent",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className={cn(
            "size-3 rounded-full border-[1.5px]",
            color === "white" ? "border-foreground bg-foreground" : "border-ink-2 bg-transparent",
          )}
        />
        <span className="text-[0.82rem] font-semibold">{SIDE_NAMES[color]}</span>
        {thinking && <span className="label-micro animate-breathe">analisando</span>}
      </div>

      <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] gap-2 max-[560px]:grid-cols-1">
        {strengths ? (
          <Select
            value={profile.strength_key}
            onValueChange={(value) => onChange({ ...profile, strength_key: value })}
            disabled={locked}
          >
            <SelectTrigger size="sm" aria-label={`Força das ${SIDE_NAMES[color].toLowerCase()}`}>
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
          <Skeleton className="h-8 w-full" />
        )}
        <Select
          value={profile.policy}
          onValueChange={(value) => onChange({ ...profile, policy: value as MatchPolicy })}
          disabled={locked}
        >
          <SelectTrigger size="sm" aria-label={`Política das ${SIDE_NAMES[color].toLowerCase()}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="strict_v1">strict_v1</SelectItem>
            <SelectItem value="normal">normal</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {played > 0 && (
        <div className="flex gap-3.5 numeric text-[0.72rem] text-ink-4">
          {counts.map((item) => (
            <span key={item.kind} className="flex items-baseline gap-1">
              <b className="font-semibold text-ink-2">{item.total}</b>
              {SELECTION_META[item.kind].label}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function StateMark({ state }: { state: DeckState }) {
  return (
    <span
      aria-hidden
      className={cn(
        "size-2.5 shrink-0 rounded-full border-[1.5px]",
        state === "idle" && "border-ink-4",
        state === "thinking" && "animate-breathe border-brass bg-brass",
        state === "paused" && "rounded-[1px] border-ink-2",
        state === "done" && "border-baize bg-baize",
        state === "capped" && "rounded-[1px] border-brass bg-brass-wash",
        state === "error" && "border-destructive bg-destructive",
        state === "review" && "rotate-45 rounded-[2px] border-ink-2 bg-ink-2",
      )}
    />
  )
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded-sm border border-border bg-secondary px-1 text-[0.7rem] text-ink-2">
      {children}
    </kbd>
  )
}
