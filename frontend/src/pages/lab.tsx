/**
 * Bancada de duelo entre motores.
 *
 * A página é uma mesa de análise, não um painel: o tabuleiro é o objeto
 * principal e tem tamanho garantido acima da dobra; o estado da partida fica
 * colado nele, como um relógio ao lado do tabuleiro; configuração, comandos,
 * súmula e auditoria vivem num trilho único à direita.
 *
 * O autoplay vive só nesta página. Não existe laço de partida no servidor:
 * sair daqui ou fechar a aba encerra o duelo.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { Chessboard } from "@/components/chessboard"
import {
  AuditDetail,
  SelectionLegend,
  SelectionMark,
  SideBadge,
  SideName,
  Drawer,
} from "@/components/lab-parts"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
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
  API_SCHEMA_VERSION,
  STARTING_FEN,
  api,
  downloadPgn,
  type BoardView,
  type Color,
  type LabSettings,
  type Match,
  type MatchMove,
  type MatchPolicy,
  type MatchProfileInput,
  type Strength,
} from "@/lib/api"
import { SIDE_NAMES, kingSquare } from "@/lib/chess"
import { labDefaultPolicy, plieLabel, selectionCounts, selectionMeta } from "@/lib/lab"
import { cn } from "@/lib/utils"

type DeskState = "idle" | "thinking" | "paused" | "review" | "done" | "capped" | "error"

interface SumulaRow {
  number: number
  white?: { index: number; move: MatchMove }
  black?: { index: number; move: MatchMove }
}

export function LabPage() {
  const [settings, setSettings] = useState<LabSettings | null>(null)
  const [strengths, setStrengths] = useState<Strength[] | null>(null)
  const [white, setWhite] = useState<MatchProfileInput>({
    strength_key: "maximo",
    policy: "strict_v2",
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
  const toggleRef = useRef<() => Promise<void>>(async () => {})
  const stepOnceRef = useRef<() => Promise<void>>(async () => {})
  const positions = useRef(new Map<number, BoardView>())
  const sumulaRef = useRef<HTMLTableSectionElement>(null)

  matchRef.current = match
  runningRef.current = running
  busyRef.current = busy
  delayRef.current = settings?.autoplay_delay_ms ?? 250

  useEffect(() => {
    Promise.all([api.lab(), api.strengths()])
      .then(([lab, levels]) => {
        setSettings(lab)
        setStrengths(levels)
        setWhite((current) => ({
          ...current,
          policy: labDefaultPolicy(lab.strict_policy),
        }))
      })
      .catch((cause: Error) => setError(cause.message))
  }, [])

  const stop = useCallback(() => {
    setRunning(false)
    runningRef.current = false
    if (timerRef.current) window.clearTimeout(timerRef.current)
    timerRef.current = null
  }, [])

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
  const finished = match !== null && !match.can_step
  const maxPlies = settings?.max_plies ?? 200
  const capped = finished && plies >= maxPlies
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
      const current = matchRef.current
      if (!current || index < 0 || index >= current.moves.length) return
      if (index < current.moves.length - 1) stop()
      setSelected(index === current.moves.length - 1 ? null : index)
    },
    [stop],
  )

  const toggle = useCallback(async () => {
    if (runningRef.current) {
      stop()
      return
    }
    if (!(await ensureMatch())) return
    if (!matchRef.current?.can_step) return
    setSelected(null)
    setRunning(true)
    runningRef.current = true
    void step()
  }, [ensureMatch, step, stop])

  const stepOnce = useCallback(async () => {
    stop()
    if (!(await ensureMatch())) return
    setSelected(null)
    await step()
  }, [ensureMatch, step, stop])

  toggleRef.current = toggle
  stepOnceRef.current = stepOnce

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
        void toggleRef.current()
      } else if (event.key.toLowerCase() === "n") {
        event.preventDefault()
        void stepOnceRef.current()
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [])

  const desk = useMemo((): { state: DeskState; text: string } => {
    if (error && !match) return { state: "error", text: "Servidor local não respondeu." }
    if (!match) return { state: "idle", text: "Mesa pronta. Falta iniciar." }
    if (capped) return { state: "capped", text: match.result_text }
    if (finished) return { state: "done", text: match.result_text }
    if (busy) return { state: "thinking", text: `${SIDE_NAMES[match.board.side_to_move]} analisando` }
    if (reviewing && selected !== null) {
      return { state: "review", text: `Revisando o meio-lance ${selected + 1} de ${plies}` }
    }
    if (error) return { state: "error", text: "Duelo interrompido." }
    if (running) return { state: "thinking", text: "Duelo em andamento" }
    if (plies === 0) return { state: "paused", text: "Perfis prontos. Falta iniciar." }
    return { state: "paused", text: `Em pausa após ${plieLabel(plies)}` }
  }, [busy, capped, error, finished, match, plies, reviewing, running, selected])

  const boardView = reviewing ? reviewView : match?.board
  const cadence = Math.min(1, plies / maxPlies)
  const move = match?.moves[viewedPly]
  const unknownSchema = match !== null && match.schema_version !== API_SCHEMA_VERSION

  const sumula = useMemo((): SumulaRow[] => {
    const moves = match?.moves ?? []
    const rows: SumulaRow[] = []
    for (let index = 0; index < moves.length; index += 2) {
      rows.push({
        number: index / 2 + 1,
        white: { index, move: moves[index] },
        black: moves[index + 1] ? { index: index + 1, move: moves[index + 1] } : undefined,
      })
    }
    return rows
  }, [match])

  return (
    /* O trilho tem largura fixa. Com uma faixa flexível ele encolhia quando o
       conteúdo era curto, então a mesa mudava de forma ao iniciar o duelo. */
    <div className="grid gap-4 lg:mx-auto lg:w-fit lg:grid-cols-[auto_392px] lg:items-start lg:gap-5">
      {/* O tabuleiro é orçado por dois lados. Em altura sobra exatamente o
          necessário para a barra de estado e o placar caberem na primeira tela
          de um notebook. Em largura sobra o trilho, a calha e o respiro da
          página, e o teto de 720px é o que resta do contêiner de 1180px depois do
          respiro (1180 - 48 - 392 - 20): assim a mesa preenche a tela grande em
          vez de flutuar pequena no meio dela, sem vazar do contêiner. */}
      <section className="grid gap-1.5 lg:w-[clamp(320px,min(calc(100svh-16rem),calc(100vw-29rem)),720px)]">
        <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="m-0 text-[1.05rem] leading-none font-medium">Laboratório de duelo</h1>
          <p className="m-0 text-[0.8rem] text-ink-3">Dois Stockfish, um contra o outro.</p>
        </header>

        <div className="grid gap-1.5">
          <div className="flex items-center gap-2.5">
            <StateMark state={desk.state} />
            <span role="status" aria-live="polite" className="text-[0.95rem] font-medium">
              {desk.text}
            </span>
            <span className="ml-auto shrink-0 numeric text-[0.75rem] text-ink-4">
              {plies}/{maxPlies}
            </span>
          </div>
          <div
            className="relative h-[2px] overflow-hidden rounded-full bg-elevated"
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
        </div>

        <Chessboard
          fen={boardView?.fen ?? STARTING_FEN}
          lastMove={boardView?.last_move_uci ?? null}
          checkSquare={
            boardView?.is_check ? kingSquare(boardView.fen, boardView.side_to_move) : null
          }
          label="Tabuleiro do duelo, somente leitura"
        />

        <ClockPlate
          match={match}
          setup={{ white, black }}
          strengths={strengths}
          busy={busy}
          move={move}
          ply={viewedPly}
        />
      </section>

      <aside className="grid content-start overflow-hidden rounded-lg border border-border bg-card lg:sticky lg:top-4">
        {unknownSchema && (
          <p className="m-0 border-b border-border bg-destructive-wash px-4 py-2 text-[0.76rem] text-ink-2">
            O servidor respondeu com o contrato <b className="font-mono">{match.schema_version}</b>{" "}
            e esta interface conhece o <b className="font-mono">{API_SCHEMA_VERSION}</b>. Alguns
            detalhes podem aparecer como não reconhecidos.
          </p>
        )}

        <Register title="Mesa">
          {/* Uma grade para as duas cores: rótulo, força e política ficam na
              mesma coluna nas duas linhas. */}
          {/* 1.7:1 é o que faz "Máximo (sem limite)" caber inteiro nos 392px do
              trilho; a coluna da política só precisa de "strict_v1". */}
          <div className="grid grid-cols-[auto_minmax(0,1.7fr)_minmax(0,1fr)] items-center gap-x-1.5 gap-y-1.5 max-[420px]:grid-cols-1">
            <SideSetup
              color="white"
              profile={white}
              onChange={setWhite}
              strengths={strengths}
              locked={match !== null}
            />
            <SideSetup
              color="black"
              profile={black}
              onChange={setBlack}
              strengths={strengths}
              locked={match !== null}
            />
          </div>
          <Drawer title="Como a política estrita decide">
            <p className="m-0 text-[0.78rem] leading-snug text-ink-3">
              <code className="text-ink-2">normal</code> joga a melhor jogada do perfil.{" "}
              <code className="text-brass">strict_v2</code> passa cada candidata por descoberta,
              confirmação, melhor defesa, estabilidade e não obviedade, e só chama de brilhante o que
              aprova nos oito portões. <code>strict_v1</code> continua disponível para reproduzir o
              caminho histórico.
            </p>
          </Drawer>
        </Register>

        <Register title="Comandos">
          <div className="flex flex-wrap gap-1.5">
            {/* Pausar precisa funcionar justamente enquanto o motor pensa, então
                este botão não é desabilitado por `busy`. */}
            <Button
              size="sm"
              onClick={() => void toggle()}
              disabled={finished || (busy && !match)}
              className="flex-1"
            >
              {running ? "Pausar" : match && plies > 0 ? "Continuar" : "Iniciar duelo"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void stepOnce()}
              disabled={busy || running || finished}
            >
              Um lance
            </Button>
            <Button size="sm" variant="outline" onClick={reset} disabled={busy || !match}>
              Reiniciar
            </Button>
            <Button
              size="sm"
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
          <p className="m-0 text-[0.7rem] text-ink-4">
            <Kbd>Espaço</Kbd> inicia ou pausa · <Kbd>N</Kbd> avança um lance · <Kbd>↑</Kbd>{" "}
            <Kbd>↓</Kbd> percorrem a súmula
          </p>
        </Register>

        <Register title="Auditoria">
          {!move ? (
            <p className="m-0 max-w-[44ch] text-[0.82rem] text-ink-4">
              A auditoria aparece a partir do primeiro lance e explica por que aquela jogada foi
              escolhida.
            </p>
          ) : (
            <div className="grid gap-2.5">
              <Verdict match={match} move={move} />
              {move.audit ? (
                <AuditDetail audit={move.audit} />
              ) : (
                <p className="m-0 text-[0.8rem] text-ink-4">
                  Sem auditoria: este lado joga sob a política <code>normal</code>.
                </p>
              )}
            </div>
          )}
        </Register>

        <Register title="Súmula">
          {plies === 0 ? (
            <p className="m-0 max-w-[44ch] text-[0.82rem] text-ink-4">
              Nenhum lance ainda. Ajuste a mesa e inicie o duelo.
            </p>
          ) : (
            <>
              <ScrollArea className="h-[13.5rem] rounded-sm border border-border-soft bg-inset">
                <table className="w-full border-collapse text-left">
                  <caption className="sr-only">
                    Lances da partida, com a marca de escolha de cada meio-lance
                  </caption>
                  <tbody
                    ref={sumulaRef}
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
                        sumulaRef.current
                          ?.querySelector<HTMLButtonElement>(`[data-ply="${next}"]`)
                          ?.focus(),
                      )
                    }}
                  >
                    {sumula.map((row) => (
                      <tr key={row.number} className="border-b border-border-soft last:border-b-0">
                        <th
                          scope="row"
                          className="w-8 py-px pr-1 pl-1.5 text-right align-middle numeric text-[0.72rem] font-normal text-ink-4"
                        >
                          {row.number}
                        </th>
                        <PlyCell entry={row.white} current={viewedPly} onSelect={selectPly} />
                        <PlyCell entry={row.black} current={viewedPly} onSelect={selectPly} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollArea>
              {reviewing && (
                <p className="m-0 text-[0.78rem] text-ink-3">
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
              <Drawer title="Marcas de escolha">
                <SelectionLegend />
              </Drawer>
            </>
          )}
        </Register>
      </aside>
    </div>
  )
}

/** Registro do trilho: um cabeçalho de instrumento e um corpo, sem cartões. */
function Register({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-2 border-b border-border-soft px-4 py-3 last:border-b-0">
      <h2 className="m-0 label-micro">{title}</h2>
      {children}
    </section>
  )
}

/**
 * Placar sob o tabuleiro: os dois lados de frente um para o outro, o lado a
 * jogar aceso e o lance em foco com sua marca. É o relógio da mesa.
 */
function ClockPlate({
  match,
  setup,
  strengths,
  busy,
  move,
  ply,
}: {
  match: Match | null
  setup: { white: MatchProfileInput; black: MatchProfileInput }
  strengths: Strength[] | null
  busy: boolean
  move: MatchMove | undefined
  ply: number
}) {
  const active = match?.can_step ? match.board.side_to_move : null
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-1.5 rounded-md border border-border-soft bg-secondary px-2.5 py-1.5">
      <SidePlate
        color="white"
        match={match}
        setup={setup.white}
        strengths={strengths}
        active={active === "white"}
        busy={busy}
      />
      <div className="flex flex-col items-center justify-center gap-1 px-1">
        {move ? (
          <>
            <span className="flex items-baseline gap-1.5">
              <b className="numeric text-[0.9rem] font-semibold">{move.san}</b>
              <SelectionMark kind={move.selection} className="text-[0.78rem]" />
            </span>
            <span className="numeric text-[0.66rem] text-ink-4">
              meio-lance {ply + 1} · {selectionMeta(move.selection).label}
            </span>
          </>
        ) : (
          <span className="text-[0.72rem] text-ink-4">sem lances</span>
        )}
      </div>
      <SidePlate
        color="black"
        match={match}
        setup={setup.black}
        strengths={strengths}
        active={active === "black"}
        busy={busy}
        align="end"
      />
    </div>
  )
}

/** Rótulo curto de uma força: só o nome, sem o rating entre parênteses. */
function shortStrength(key: string, strengths: Strength[] | null): string {
  return (strengths?.find((level) => level.key === key)?.label ?? key).split(" (")[0]
}

function SidePlate({
  color,
  match,
  setup,
  strengths,
  active,
  busy,
  align = "start",
}: {
  color: Color
  match: Match | null
  setup: MatchProfileInput
  strengths: Strength[] | null
  active: boolean
  busy: boolean
  align?: "start" | "end"
}) {
  // Antes de iniciar, o placar mostra o que está configurado na mesa. Um "não
  // iniciado" repetido nos dois lados não informa nada a quem vai começar.
  const profile = match ? (color === "white" ? match.white : match.black) : null
  const strengthLabel = profile
    ? profile.strength.label.split(" (")[0]
    : shortStrength(setup.strength_key, strengths)
  const policy = profile ? profile.policy : setup.policy
  const counts = selectionCounts((match?.moves ?? []).filter((item) => item.color === color))
  const played = counts.reduce((sum, item) => sum + item.total, 0)
  return (
    <div
      className={cn(
        "grid content-center gap-0.5 rounded-sm px-1.5 py-1",
        align === "end" ? "justify-items-end text-right" : "justify-items-start",
        active && "bg-brass-wash shadow-[inset_0_0_0_1px_var(--brass-wash)]",
      )}
    >
      <span className="flex items-center gap-1.5">
        {align === "end" && active && <Thinking busy={busy} />}
        <SideBadge color={color} />
        <SideName color={color} />
        {align === "start" && active && <Thinking busy={busy} />}
      </span>
      {/* Perfil e talhos na mesma linha: o placar tem sempre duas alturas, então
          o tabuleiro nunca é empurrado quando a contagem começa. */}
      <span
        className={cn(
          "flex items-baseline gap-x-2 gap-y-0.5 numeric text-[0.68rem] text-ink-4",
          align === "end" ? "flex-row-reverse flex-wrap-reverse" : "flex-wrap",
        )}
      >
        <span className={cn(!profile && "text-ink-4/80")}>
          {strengthLabel} · {policy}
        </span>
        {played > 0 &&
          counts
            .filter((item) => item.total > 0)
            .map((item) => (
              <span
                key={String(item.kind)}
                className="flex items-baseline gap-1 text-ink-3"
                title={`${item.total} × ${selectionMeta(item.kind).label}`}
              >
                <SelectionMark kind={item.kind} className="text-[0.7rem]" />
                {item.total}
              </span>
            ))}
      </span>
    </div>
  )
}

function Thinking({ busy }: { busy: boolean }) {
  return (
    <span
      className={cn(
        "label-micro text-[0.6rem] text-brass",
        busy ? "animate-breathe" : "opacity-70",
      )}
    >
      {busy ? "analisa" : "a jogar"}
    </span>
  )
}

function Verdict({ match, move }: { match: Match; move: MatchMove }) {
  const profile = move.color === "white" ? match.white : match.black
  const label = profile.strength.label.split(" (")[0]
  const meta = selectionMeta(move.selection)
  const san = <strong className="font-semibold text-foreground">{move.san}</strong>

  const sentence = () => {
    switch (move.selection) {
      case "strict_v1":
        return <>{san} passou pelos sete portões e teve a maior pontuação entre as elegíveis.</>
      case "near_brilliant":
        return (
          <>
            {san} é segura e auditada, mas não recebe o selo de brilhante: reprovou em pelo menos um
            portão de classificação.
          </>
        )
      case "fallback":
        return (
          <>
            Nenhuma candidata sobreviveu à auditoria aqui. {SIDE_NAMES[move.color]} jogaram {san}, a
            melhor jogada do perfil {label}.
          </>
        )
      case "normal":
        return (
          <>
            {san} veio do Stockfish no perfil {label}. A política <code>normal</code> não aplica
            critério de brilhantismo.
          </>
        )
      default:
        return (
          <>
            {san} chegou com a seleção <code>{move.selection}</code>, que esta interface ainda não
            conhece. O lance foi jogado; a classificação não pode ser afirmada.
          </>
        )
    }
  }

  return (
    <div className="grid gap-1">
      <span className="flex items-center gap-2">
        <SelectionMark kind={move.selection} />
        <span className="font-mono text-[0.74rem] font-semibold tracking-[0.02em] text-ink-2">
          {meta.label}
        </span>
        <span className="text-[0.72rem] text-ink-4">{meta.short}</span>
      </span>
      <p className="m-0 text-[0.86rem] leading-snug text-ink-2">{sentence()}</p>
    </div>
  )
}

function PlyCell({
  entry,
  current,
  onSelect,
}: {
  entry: { index: number; move: MatchMove } | undefined
  current: number
  onSelect: (index: number) => void
}) {
  if (!entry) return <td className="p-0" />
  const active = entry.index === current
  return (
    <td className="p-0">
      <button
        type="button"
        data-ply={entry.index}
        tabIndex={active ? 0 : -1}
        aria-current={active || undefined}
        onClick={() => onSelect(entry.index)}
        className={cn(
          "flex w-full items-baseline justify-between gap-1.5 px-1.5 py-[3px] text-left text-[0.84rem] text-ink-2",
          active
            ? "bg-elevated text-foreground shadow-[inset_2px_0_0_0_var(--brass)]"
            : "hover:bg-secondary",
        )}
        title={`${SIDE_NAMES[entry.move.color]} · ${selectionMeta(entry.move.selection).label}`}
      >
        <span className="font-medium">{entry.move.san}</span>
        <SelectionMark kind={entry.move.selection} className="text-[0.78rem]" />
      </button>
    </td>
  )
}

function SideSetup({
  color,
  profile,
  onChange,
  strengths,
  locked,
}: {
  color: Color
  profile: MatchProfileInput
  onChange: (next: MatchProfileInput) => void
  strengths: Strength[] | null
  locked: boolean
}) {
  const side = SIDE_NAMES[color].toLowerCase()
  // Fragmento, não `div`: as duas cores dividem a grade do pai, então a coluna
  // do rótulo mede uma vez só. Em grades separadas, `auto` resolvia 74px para
  // "Brancas" e 65px para "Pretas" e as linhas saíam desalinhadas.
  return (
    <>
      <span className="flex items-center gap-1.5 pr-1">
        <SideBadge color={color} />
        <span className="text-[0.78rem] font-medium">{SIDE_NAMES[color]}</span>
      </span>
      {strengths ? (
        <Select
          value={profile.strength_key}
          onValueChange={(value) => onChange({ ...profile, strength_key: value })}
          disabled={locked}
        >
          {/* `SelectTrigger` nasce com `w-fit` e `whitespace-nowrap`: sem
              `w-full min-w-0` ele mede pelo texto e transborda a trilha da
              grade por cima do vizinho. */}
          <SelectTrigger size="sm" className="w-full min-w-0" aria-label={`Força das ${side}`}>
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
        <Skeleton className="h-7 w-full" />
      )}
      <Select
        value={profile.policy}
        onValueChange={(value) => onChange({ ...profile, policy: value as MatchPolicy })}
        disabled={locked}
      >
        <SelectTrigger size="sm" className="w-full min-w-0" aria-label={`Política das ${side}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="strict_v2">strict_v2</SelectItem>
          <SelectItem value="strict_v1">strict_v1</SelectItem>
          <SelectItem value="normal">normal</SelectItem>
        </SelectContent>
      </Select>
    </>
  )
}

function StateMark({ state }: { state: DeskState }) {
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
    <kbd className="rounded-sm border border-border bg-secondary px-1 text-[0.68rem] text-ink-2">
      {children}
    </kbd>
  )
}
