import type { CandidateAudit, Gate, SelectionKind } from "@/lib/api"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  GATES,
  GATE_GLYPHS,
  GATE_WORDS,
  SELECTION_META,
  formatMeasure,
  meterPositions,
} from "@/lib/lab"
import { cn } from "@/lib/utils"

/** Marca da escolha: matiz diz a política, preenchimento diz o resultado. */
export function SelectionMark({
  kind,
  className,
}: {
  kind: SelectionKind
  className?: string
}) {
  const meta = SELECTION_META[kind]
  return (
    <span
      title={`${meta.label} — ${meta.short}`}
      className={cn(
        "font-mono leading-none",
        kind === "normal" ? "text-ink-4" : "text-brass",
        className,
      )}
    >
      <span aria-hidden>{meta.mark}</span>
      <span className="sr-only">{meta.label}</span>
    </span>
  )
}

export function SelectionLegend() {
  return (
    <ul className="m-0 grid list-none gap-1.5 p-0">
      {(["strict_v1", "near_brilliant", "fallback", "normal"] as SelectionKind[]).map((kind) => (
        <li key={kind} className="flex items-baseline gap-2.5 text-[0.78rem] text-ink-3">
          <SelectionMark kind={kind} className="w-4 shrink-0 text-center" />
          <span>
            <b className="font-mono text-[0.74rem] font-semibold text-ink-2">
              {SELECTION_META[kind].label}
            </b>{" "}
            — {SELECTION_META[kind].description}
          </span>
        </li>
      ))}
    </ul>
  )
}

/**
 * Régua de portões: sete posições fixas, inicial do portão mais o glifo do
 * resultado. Lê-se de relance e não depende de cor.
 */
export function GateRail({ gates }: { gates: Gate[] }) {
  return (
    <div className="flex gap-1">
      {GATES.map((meta) => {
        const gate = gates.find((item) => item.gate_id === meta.id)
        const status = gate?.status ?? "indeterminate"
        const description = `${meta.name}: ${GATE_WORDS[status]}`
        return (
          <span
            key={meta.id}
            role="img"
            aria-label={description}
            title={description}
            className={cn(
              "grid h-5 flex-1 place-items-center rounded-sm border font-mono text-[0.68rem] tracking-[0.06em]",
              status === "passed" && "border-baize/40 bg-baize-wash text-baize",
              status === "failed" && "border-destructive/40 bg-destructive-wash text-destructive",
              status === "indeterminate" && "border-dashed border-border text-ink-3",
            )}
          >
            {meta.tile}
            {GATE_GLYPHS[status]}
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
function GateRow({ gate, name, relation }: { gate: Gate; name: string; relation: "≤" | "≥" | null }) {
  const meter = meterPositions(gate.measured, gate.threshold)
  return (
    <div className="border-b border-border-soft py-2.5 last:border-b-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[0.82rem]">{name}</span>
        <span
          className={cn(
            "font-mono text-[0.7rem]",
            gate.status === "passed" && "text-baize",
            gate.status === "failed" && "text-destructive",
            gate.status === "indeterminate" && "text-ink-3",
          )}
        >
          {GATE_GLYPHS[gate.status]} {GATE_WORDS[gate.status]}
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
            className="absolute top-[-2.5px] size-2 -translate-x-1/2 rounded-full bg-baize"
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
    <Collapsible defaultOpen={defaultOpen} className="mt-2 border-t border-border-soft pt-2">
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

export function AuditDetail({ audit }: { audit: CandidateAudit }) {
  return (
    <>
      <div className="mb-3 flex items-baseline gap-2.5">
        <span className="numeric text-[1.7rem] font-semibold tracking-tight text-brass">
          {audit.score.toFixed(1)}
        </span>
        <span className="font-mono text-[0.75rem] text-ink-4">
          / 100 pontos de brilhantismo
        </span>
      </div>

      <GateRail gates={audit.gates} />

      <Drawer title="Portões e medidas">
        {GATES.map((meta) => {
          const gate = audit.gates.find((item) => item.gate_id === meta.id)
          if (!gate) return null
          return <GateRow key={meta.id} gate={gate} name={meta.name} relation={meta.relation} />
        })}
      </Drawer>

      <Drawer title="Procedência">
        <ul className="m-0 list-none p-0 font-mono text-[0.72rem] text-ink-3">
          <li className="py-0.5">regras = {audit.rule_set_version}</li>
          <li className="py-0.5">uci = {audit.selected_uci}</li>
          {audit.reason_codes.map((reason) => (
            <li key={reason} className="py-0.5">
              {reason}
            </li>
          ))}
        </ul>
      </Drawer>
    </>
  )
}
