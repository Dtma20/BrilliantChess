import { ChevronDown } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { Chessboard } from "@/components/chessboard"
import { PageHeader } from "@/components/page-header"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Label } from "@/components/ui/label"
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
  type Analysis,
  type BoardView,
  type Candidate,
  type Color,
} from "@/lib/api"
import { kingSquare } from "@/lib/chess"
import { cn } from "@/lib/utils"

export function AnalysisPage() {
  const [baseFen, setBaseFen] = useState(STARTING_FEN)
  const [moves, setMoves] = useState<string[]>([])
  const [fenDraft, setFenDraft] = useState(STARTING_FEN)
  const [view, setView] = useState<BoardView | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [lines, setLines] = useState("5")
  const [autoAnalyze, setAutoAnalyze] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [orientation, setOrientation] = useState<Color>("white")
  const [error, setError] = useState("")
  const runId = useRef(0)

  const analyze = useCallback(
    async (fen: string, multipv: number) => {
      const token = ++runId.current
      setAnalyzing(true)
      try {
        const result = await api.analyze({ fen, multipv })
        if (runId.current === token) setAnalysis(result)
      } catch (cause) {
        if (runId.current === token) setError((cause as Error).message)
      } finally {
        if (runId.current === token) setAnalyzing(false)
      }
    },
    [],
  )

  const load = useCallback(
    async (fen: string, line: string[], shouldAnalyze: boolean) => {
      setError("")
      try {
        const next = await api.board({ fen, moves: line })
        setView(next)
        setFenDraft(next.fen)
        if (shouldAnalyze) await analyze(next.fen, Number(lines))
      } catch (cause) {
        setError((cause as Error).message)
      }
    },
    [analyze, lines],
  )

  useEffect(() => {
    void load(STARTING_FEN, [], true)
    // Carga inicial apenas.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function applyMove(uci: string) {
    const line = [...moves, uci]
    setMoves(line)
    setAnalysis(null)
    void load(baseFen, line, autoAnalyze)
  }

  function goBack() {
    const line = moves.slice(0, -1)
    setMoves(line)
    setAnalysis(null)
    void load(baseFen, line, autoAnalyze)
  }

  function loadFen(fen: string) {
    const next = fen.trim() || STARTING_FEN
    setBaseFen(next)
    setMoves([])
    setAnalysis(null)
    void load(next, [], autoAnalyze)
  }

  const best = analysis?.candidates[0]

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <section className="grid gap-4">
        <PageHeader
          title="Tabuleiro de análise"
          lede="Mova as peças ou cole uma FEN. As setas seguem o ranking confirmado, não a ordem bruta do MultiPV."
        />

        <div className="mx-auto w-full max-w-[min(100%,calc(100vh-22rem))]">
          <Chessboard
            fen={view?.fen ?? STARTING_FEN}
            orientation={orientation}
            interactive
            legalMoves={view?.legal_moves ?? []}
            lastMove={view?.last_move_uci ?? null}
            checkSquare={view?.is_check ? kingSquare(view.fen, view.side_to_move) : null}
            arrows={analysis?.arrows ?? []}
            onMove={applyMove}
            label="Tabuleiro de análise"
          />
        </div>

        <Card className="gap-3 p-5">
          <h2 className="m-0 label-micro">Posição</h2>
          <div className="grid gap-1.5">
            <Label htmlFor="fen" className="sr-only">
              FEN da posição
            </Label>
            <input
              id="fen"
              value={fenDraft}
              spellCheck={false}
              onChange={(event) => setFenDraft(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && loadFen(fenDraft)}
              className="w-full rounded-md border border-input bg-inset px-3 py-2 font-mono text-[0.8rem] outline-none focus-visible:border-brass"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => loadFen(fenDraft)}>Carregar FEN</Button>
            <Button variant="outline" onClick={() => loadFen(STARTING_FEN)}>
              Posição inicial
            </Button>
            <Button variant="outline" onClick={goBack} disabled={moves.length === 0}>
              Voltar
            </Button>
            <Button
              variant="outline"
              onClick={() => setOrientation(orientation === "white" ? "black" : "white")}
            >
              Girar
            </Button>
            <Button
              variant="outline"
              onClick={() => void navigator.clipboard?.writeText(fenDraft)}
            >
              Copiar FEN
            </Button>
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </Card>
      </section>

      <aside className="grid gap-4">
        <Card className="gap-3 p-5">
          <h2 className="m-0 label-micro">Avaliação</h2>
          {analyzing && !analysis ? (
            <Skeleton className="h-12 w-full" />
          ) : (
            <>
              <div className="flex items-baseline justify-between gap-3">
                <span className="numeric text-2xl font-semibold tracking-tight">
                  {best?.evaluation_text ?? "—"}
                </span>
                <span className="text-[0.8rem] text-ink-3">
                  {analysis
                    ? `ponto de vista das ${analysis.side_to_move === "white" ? "brancas" : "pretas"}`
                    : ""}
                </span>
              </div>
              <div
                className="h-1.5 overflow-hidden rounded-full bg-elevated"
                role="img"
                aria-label={
                  analysis
                    ? `Pontos esperados: ${(analysis.expected_points_before * 100).toFixed(0)} de 100`
                    : "Sem avaliação"
                }
              >
                <span
                  className="block h-full bg-baize transition-[width] duration-300"
                  style={{ width: `${(analysis?.expected_points_before ?? 0.5) * 100}%` }}
                />
              </div>
              <p className="m-0 font-mono text-[0.72rem] text-ink-4">
                {analyzing
                  ? "Analisando…"
                  : analysis && best
                    ? `${analysis.engine_name} ${analysis.engine_version}${
                        analysis.nnue_name ? ` · ${analysis.nnue_name}` : ""
                      } · ${best.nodes.toLocaleString("pt-BR")} nós · profundidade ${best.depth}`
                    : "Motor ainda não consultado."}
              </p>
            </>
          )}
        </Card>

        <Card className="gap-3 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="m-0 mr-auto label-micro">Melhores jogadas</h2>
            <Select
              value={lines}
              onValueChange={(value) => {
                setLines(value)
                if (view) void analyze(view.fen, Number(value))
              }}
            >
              <SelectTrigger size="sm" aria-label="Número de linhas" className="w-[6.5rem]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["3", "5", "8"].map((value) => (
                  <SelectItem key={value} value={value}>
                    {value} linhas
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => view && void analyze(view.fen, Number(lines))}
              disabled={analyzing || !view}
            >
              Analisar
            </Button>
          </div>

          <label className="flex items-center gap-2 text-[0.82rem] text-ink-2">
            <input
              type="checkbox"
              checked={autoAnalyze}
              onChange={(event) => setAutoAnalyze(event.target.checked)}
              className="size-3.5 accent-brass"
            />
            Analisar a cada lance
          </label>

          {analyzing && !analysis ? (
            <div className="grid gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : analysis && analysis.candidates.length > 0 ? (
            <div className="grid">
              {analysis.candidates.map((candidate) => (
                <CandidateRow
                  key={candidate.move_uci}
                  candidate={candidate}
                  color={analysis.arrows.find((arrow) => arrow.rank === candidate.rank)?.color}
                  onPlay={() => applyMove(candidate.move_uci)}
                />
              ))}
            </div>
          ) : (
            <p className="m-0 max-w-[40ch] text-[0.84rem] text-ink-4">
              {view?.status !== "in_progress"
                ? "Posição final: não há jogadas legais para avaliar."
                : "Nenhuma análise ainda. Mova uma peça ou clique em Analisar."}
            </p>
          )}

          {analysis && analysis.warnings.length > 0 && (
            <Alert>
              <AlertTitle className="label-micro">Avisos do motor</AlertTitle>
              <AlertDescription className="font-mono text-[0.72rem]">
                {analysis.warnings.join(", ")}
              </AlertDescription>
            </Alert>
          )}
        </Card>

        <Card className="gap-2 p-5">
          <h2 className="m-0 label-micro">Linha atual</h2>
          <p className="m-0 font-mono text-[0.8rem] break-words text-ink-3">
            {view && view.moves_san.length > 0
              ? view.moves_san.join(" ")
              : "Mova as peças para explorar variantes."}
          </p>
        </Card>
      </aside>
    </div>
  )
}

function CandidateRow({
  candidate,
  color,
  onPlay,
}: {
  candidate: Candidate
  color?: string
  onPlay: () => void
}) {
  return (
    <Collapsible className="border-t border-border-soft first:border-t-0">
      <div className="flex items-baseline gap-2 py-1.5">
        <span
          aria-hidden
          className="size-2 shrink-0 self-center rounded-full"
          style={{ background: color ?? "var(--ink-4)" }}
        />
        <button
          type="button"
          onClick={onPlay}
          className={cn(
            "flex min-w-0 flex-1 items-baseline gap-2 rounded-sm px-1 text-left hover:bg-secondary",
            candidate.rank === 1 && "text-baize",
          )}
          title="Jogar esta candidata no tabuleiro"
        >
          <span className="w-4 shrink-0 numeric text-[0.72rem] text-ink-4">{candidate.rank}</span>
          <span className="shrink-0 text-[0.88rem] font-medium">{candidate.move_san}</span>
          <span className="ml-auto shrink-0 numeric text-[0.8rem]">
            {candidate.evaluation_text}
          </span>
        </button>
        <CollapsibleTrigger
          className="group shrink-0 rounded-sm p-1 text-ink-4 hover:text-foreground"
          aria-label={`Detalhes de ${candidate.move_san}`}
        >
          <ChevronDown
            aria-hidden
            className="size-3.5 transition-transform group-data-[state=open]:rotate-180"
          />
        </CollapsibleTrigger>
      </div>
      <p className="m-0 truncate pb-1.5 pl-[1.9rem] font-mono text-[0.74rem] text-ink-4">
        {candidate.pv_san.slice(0, 6).join(" ")}
      </p>
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
        <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 pb-3 pl-[1.9rem] font-mono text-[0.72rem]">
          <dt className="text-ink-4">variante</dt>
          <dd className="m-0 text-ink-2">{candidate.pv_san.join(" ")}</dd>
          <dt className="text-ink-4">EP depois</dt>
          <dd className="m-0 numeric text-ink-2">
            {candidate.expected_points_after.toFixed(4)}
          </dd>
          <dt className="text-ink-4">perda de EP</dt>
          <dd className="m-0 numeric text-ink-2">{candidate.expected_points_loss.toFixed(4)}</dd>
          <dt className="text-ink-4">profundidade</dt>
          <dd className="m-0 numeric text-ink-2">{candidate.depth}</dd>
          <dt className="text-ink-4">nós</dt>
          <dd className="m-0 numeric text-ink-2">{candidate.nodes.toLocaleString("pt-BR")}</dd>
        </dl>
      </CollapsibleContent>
    </Collapsible>
  )
}
