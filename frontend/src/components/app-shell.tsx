import { Menu } from "lucide-react"
import { useEffect, useState } from "react"
import { NavLink, Outlet } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api, type Health } from "@/lib/api"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", label: "Início", end: true },
  { to: "/jogar", label: "Jogar", end: false },
  { to: "/analise", label: "Análise", end: false },
  { to: "/laboratorio", label: "Laboratório", end: false },
]

export function AppShell() {
  const [open, setOpen] = useState(false)

  return (
    <div className="min-h-dvh">
      <header className="flex flex-wrap items-baseline gap-5 border-b border-border px-4 py-3 sm:px-6">
        <NavLink to="/" className="text-[0.9rem] font-semibold tracking-tight no-underline">
          Brilliant Chess <span className="font-normal text-ink-4">· estudo local</span>
        </NavLink>

        <nav aria-label="Seções" className="ml-auto hidden gap-0.5 md:flex">
          {NAV.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
          <EngineBadge />
        </nav>

        <div className="ml-auto md:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="sm" aria-label="Abrir navegação">
                <Menu aria-hidden />
                Seções
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-72">
              <SheetHeader>
                <SheetTitle className="label-micro">Seções</SheetTitle>
              </SheetHeader>
              <nav className="grid gap-1 px-4">
                {NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={() => setOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "rounded-md px-3 py-2 text-sm no-underline",
                        isActive ? "bg-secondary text-foreground" : "text-ink-3 hover:bg-secondary",
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
              <div className="mt-auto px-4 pb-6">
                <EngineBadge />
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <FairPlayBanner />

      <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}

function NavItem({ to, label, end }: { to: string; label: string; end: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-[0.87rem] no-underline transition-colors",
          isActive
            ? "bg-secondary text-foreground shadow-[inset_0_0_0_1px_var(--border)]"
            : "text-ink-3 hover:bg-secondary hover:text-foreground",
        )
      }
    >
      {label}
    </NavLink>
  )
}

/**
 * Aviso permanente de fair play. Não é decorativo e não pode ser dispensado:
 * o projeto proíbe qualquer ponte com partidas ao vivo de terceiros.
 */
export function FairPlayBanner() {
  return (
    <div className="flex items-baseline gap-3 border-b border-border bg-destructive-wash px-4 py-2 text-ink-2 sm:px-6">
      <span className="shrink-0 text-[0.66rem] font-bold tracking-[0.1em] text-destructive uppercase">
        Fair play
      </span>
      <p className="m-0 text-[0.8rem]">
        Ferramenta local de estudo. Não use durante partidas ao vivo em nenhuma plataforma: isso é
        trapaça. O app desenha o próprio tabuleiro, não lê tela, não controla o mouse e não se
        conecta a partida alguma.
      </p>
    </div>
  )
}

function EngineBadge() {
  const [health, setHealth] = useState<Health | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setFailed(true))
  }, [])

  if (failed) {
    return (
      <span className="ml-3 self-center numeric text-[0.72rem] text-destructive">
        servidor local fora do ar
      </span>
    )
  }
  if (!health) return null

  const ready = Boolean(health.engine_binary)
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="ml-3 flex items-center gap-2 self-center numeric text-[0.72rem] text-ink-4">
          <span
            aria-hidden
            className={cn(
              "size-1.5 rounded-full",
              ready ? "bg-baize" : "bg-destructive",
            )}
          />
          {health.rule_set}
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        {ready ? `Motor encontrado em ${health.engine_binary}` : "Stockfish não encontrado no PATH"}
      </TooltipContent>
    </Tooltip>
  )
}
