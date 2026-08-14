/**
 * Peças da bancada de auditoria.
 *
 * Três regras valem para tudo aqui:
 *
 * 1. Nenhuma informação depende só de cor. Cada estado tem glifo, palavra e
 *    posição fixa.
 * 2. Só `strict_v1` usa o latão. `near_brilliant` usa o verde do pano, que
 *    quer dizer "seguro", nunca "brilhante".
 * 3. Nada é indexado direto a partir do que o servidor mandou.
 */

import type { CandidateAudit, Color, Gate, MatchMove, SelectionKind, Wire } from "@/lib/api"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { PIECE_GLYPHS, SIDE_NAMES } from "@/lib/chess"
import {
  gatesForRuleSet,
  SELECTION_ORDER,
  evidenceSentences,
  formatMeasure,
  gateGlyph,
  gateTone,
  gateWord,
  meterPositions,
  selectionMeta,
  type GateMeta,
  type SelectionMeta,
} from "@/lib/lab"
import { cn } from "@/lib/utils"

const TONE_INK: Record<SelectionMeta["tone"], string> = {
  audited: "text-brass",
  safe: "text-baize",
  engine: "text-ink-4",
  unknown: "text-destructive",
}

/** Marca da escolha: o glifo diz o quê, a cor só reforça. */
export function SelectionMark({
  kind,
  className,
}: {
  kind: Wire<SelectionKind>
  className?: string
}) {
  const meta = selectionMeta(kind)
  return (
    <span
      title={`${meta.label} — ${meta.short}`}
      className={cn("font-mono leading-none", TONE_INK[meta.tone], className)}
    >
      <span aria-hidden>{meta.mark}</span>
      <span className="sr-only">{meta.label}</span>
    </span>
  )
}

/**
 * Identidade do lado com a mesma pista que o tabuleiro usa: a silhueta do rei,
 * clara ou escura, com o mesmo contorno das peças. Texto acompanha sempre.
 */
export function SideBadge({
  color,
  size = "sm",
}: {
  color: Color
  size?: "sm" | "md"
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid shrink-0 place-items-center rounded-[3px] leading-none",
        size === "sm" ? "size-[18px] text-[0.86rem]" : "size-6 text-[1.05rem]",
        color === "white"
          ? "bg-board-light/12 text-[#fdfdfd] [-webkit-text-stroke:0.9px_#22252b]"
          : "bg-inset text-[#24262c] [-webkit-text-stroke:0.9px_#d9dde3]",
      )}
      style={{ paintOrder: "stroke fill" }}
    >
      {PIECE_GLYPHS.k}
    </span>
  )
}

export function SideName({ color }: { color: Color }) {
  return <span className="text-[0.82rem] font-semibold">{SIDE_NAMES[color]}</span>
}

/** Legenda em linha: cabe sob a súmula sem virar um cartão próprio. */
export function SelectionLegend() {
  return (
    <ul className="m-0 grid list-none gap-1 p-0">
      {SELECTION_ORDER.map((kind) => {
        const meta = selectionMeta(kind)
        return (
          <li key={kind} className="flex items-baseline gap-2 text-[0.76rem] text-ink-3">
            <SelectionMark kind={kind} className="w-3 shrink-0 text-center" />
            <span>
              <b className="font-mono text-[0.72rem] font-semibold text-ink-2">{meta.label}</b> —{" "}
              {meta.description}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * Régua de portões: uma célula por portão da regra, inicial do portão mais o
 * glifo do resultado. É o carimbo de inspeção desta política e fica sempre à vista.
 */
export function GateRail({
  gates,
  ruleSetVersion = "strict_v2",
}: {
  gates: Gate[]
  ruleSetVersion?: string
}) {
  const catalog = gatesForRuleSet(ruleSetVersion)
  return (
    <div className="flex gap-[3px]">
      {catalog.map((meta) => {
        const gate = gates.find((item) => item.gate_id === meta.id)
        const status = gate?.status ?? "indeterminate"
        const tone = gateTone(status)
        const description = `${meta.name}: ${gateWord(status)}`
        return (
          <span
            key={meta.id}
            role="img"
            aria-label={description}
            title={description}
            className={cn(
              "grid h-[22px] flex-1 place-items-center rounded-[3px] border font-mono text-[0.68rem] tracking-[0.04em]",
              tone === "passed" && "border-baize/40 bg-baize-wash text-baize",
              tone === "failed" && "border-destructive/40 bg-destructive-wash text-destructive",
              tone === "open" && "border-dashed border-border text-ink-3",
            )}
          >
            {meta.tile}
            {gateGlyph(status)}
          </span>
        )
      })}
    </div>
  )
}

/**
 * Medidor de folga: um traço marca o limiar, um ponto marca o valor medido.
 * O operador (≤ ou ≥) carrega a direção, então a leitura não depende de cor.
 */
function GateRow({
  gate,
  name,
  relation,
}: {
  gate: Gate
  name: string
  relation: GateMeta["relation"]
}) {
  const meter = meterPositions(gate.measured, gate.threshold)
  const tone = gateTone(gate.status)
  return (
    <div className="border-b border-border-soft py-2 last:border-b-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[0.82rem]">{name}</span>
        <span
          className={cn(
            "font-mono text-[0.7rem]",
            tone === "passed" && "text-baize",
            tone === "failed" && "text-destructive",
            tone === "open" && "text-ink-3",
          )}
        >
          {gateGlyph(gate.status)} {gateWord(gate.status)}
        </span>
      </div>
      <p className="mt-1 mb-0 numeric text-[0.75rem] text-ink-2">
        {relation
          ? `${formatMeasure(gate.measured)} ${relation} ${formatMeasure(gate.threshold)}`
          : formatMeasure(gate.measured)}
      </p>
      {meter && (
        <div className="relative mt-1.5 h-[3px] rounded-full bg-elevated">
          <i
            aria-hidden
            className="absolute top-[-3px] h-[9px] w-px -translate-x-1/2 bg-ink-3"
            style={{ left: `${meter.threshold}%` }}
          />
          <b
            aria-hidden
            className={cn(
              "absolute top-[-2.5px] size-2 -translate-x-1/2 rounded-full",
              tone === "failed" ? "bg-destructive" : "bg-baize",
            )}
            style={{ left: `${meter.measured}%` }}
          />
        </div>
      )}
      <p className="mt-1.5 mb-0 font-mono text-[0.71rem] leading-relaxed text-ink-4">
        {gate.explanation}
      </p>
    </div>
  )
}

export function Drawer({
  title,
  children,
  defaultOpen = false,
}: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  return (
    <Collapsible defaultOpen={defaultOpen} className="border-t border-border-soft pt-1.5">
      <CollapsibleTrigger className="group flex w-full items-center gap-1.5 label-micro hover:text-foreground">
        <span aria-hidden className="font-mono text-ink-4 group-data-[state=open]:hidden">
          +
        </span>
        <span aria-hidden className="hidden font-mono text-ink-4 group-data-[state=open]:inline">
          −
        </span>
        {title}
      </CollapsibleTrigger>
      <CollapsibleContent className="data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down overflow-hidden">
        <div className="pt-1">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  )
}

/**
 * Evidência em frases: a peça oferecida, a casa, o lance que aceita e o que a
 * melhor defesa fez de fato. Sem isso a auditoria só repetiria os limiares.
 */
export function EvidenceList({ audit }: { audit: CandidateAudit }) {
  const lines = evidenceSentences(audit)
  return (
    <ul className="m-0 grid list-none gap-1 p-0">
      {lines.map((line) => (
        <li key={line} className="flex gap-2 text-[0.82rem] leading-snug text-ink-2">
          <span aria-hidden className="mt-[0.42em] size-1 shrink-0 rounded-full bg-ink-4" />
          <span>{line}</span>
        </li>
      ))}
    </ul>
  )
}

export function AuditDetail({ audit }: { audit: CandidateAudit }) {
  const catalog = gatesForRuleSet(audit.rule_set_version)
  return (
    <div className="grid gap-3">
      <div className="flex items-end gap-2.5">
        <span className="numeric text-[1.55rem] leading-none font-semibold tracking-tight text-brass">
          {audit.score.toFixed(1)}
        </span>
        <span className="font-mono text-[0.72rem] text-ink-4">/ 100 diagnóstico</span>
        {audit.sacrifice && (
          <span className="ml-auto numeric text-[0.72rem] text-ink-3">
            confiança {audit.sacrifice.confidence.toFixed(2)}
          </span>
        )}
      </div>

      <GateRail gates={audit.gates} ruleSetVersion={audit.rule_set_version} />

      <EvidenceList audit={audit} />

      <Drawer title="Portões e medidas">
        {catalog.map((meta) => {
          const gate = audit.gates.find((item) => item.gate_id === meta.id)
          if (!gate) return null
          return <GateRow key={meta.id} gate={gate} name={meta.name} relation={meta.relation} />
        })}
      </Drawer>

      <Drawer title="Procedência">
        <ul className="m-0 list-none p-0 font-mono text-[0.72rem] text-ink-3">
          <li className="py-0.5">regras = {audit.rule_set_version}</li>
          <li className="py-0.5">uci = {audit.selected_uci}</li>
          {audit.sacrifice && (
            <li className="py-0.5">
              sacrificio = {audit.sacrifice.kind}@{audit.sacrifice.offered_square}
            </li>
          )}
          {audit.reason_codes.map((reason) => (
            <li key={reason} className="py-0.5">
              {reason}
            </li>
          ))}
        </ul>
      </Drawer>
    </div>
  )
}

export function OpeningDetail({ move }: { move: MatchMove }) {
  const audit = move.opening_audit
  if (!audit) {
    return (
      <div className="grid gap-2 text-[0.82rem] text-ink-3">
        <p>Lance realizado durante a fase de abertura.</p>
      </div>
    )
  }
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between border-b border-border-soft pb-2">
        <span className="font-mono text-[0.78rem] font-semibold text-foreground">
          {audit.eco} — {audit.name}
        </span>
        <span className="rounded bg-elevated px-1.5 py-0.5 font-mono text-[0.7rem] text-ink-3">
          {audit.source === "suite" ? "Suíte offline" : "MultiPV"}
        </span>
      </div>

      {audit.variation && (
        <p className="text-[0.8rem] text-ink-2">
          Variação: <span className="font-medium text-foreground">{audit.variation}</span>
        </p>
      )}

      <ul className="m-0 list-none p-0 font-mono text-[0.74rem] text-ink-3">
        <li className="py-0.5">
          meio-lance = {audit.opening_ply} de {audit.planned_exit_ply} planejados
        </li>
        <li className="py-0.5">modo = {audit.opening_mode}</li>
        <li className="py-0.5">semente = {audit.seed}</li>
        {audit.candidate_rank !== null && audit.candidate_rank !== undefined && (
          <li className="py-0.5">rank no motor = #{audit.candidate_rank}</li>
        )}
        {audit.candidate_ep_loss !== null && audit.candidate_ep_loss !== undefined && (
          <li className="py-0.5">perda de EP = {audit.candidate_ep_loss.toFixed(4)}</li>
        )}
        {audit.quality_cutoff !== null && audit.quality_cutoff !== undefined && (
          <li className="py-0.5">limiar de corte = {audit.quality_cutoff.toFixed(4)}</li>
        )}
        {audit.candidates_considered && audit.candidates_considered.length > 0 && (
          <li className="py-0.5">
            candidatas consideradas = {audit.candidates_considered.join(", ")}
          </li>
        )}
      </ul>
    </div>
  )
}

