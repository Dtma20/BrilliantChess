import { Link } from "react-router-dom"

import { PageHeader } from "@/components/page-header"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

const WORKFLOWS = [
  {
    to: "/jogar",
    eyebrow: "Partida",
    title: "Jogar contra o motor",
    body: "Partida completa contra o Stockfish, de iniciante a força máxima, com PGN no fim.",
  },
  {
    to: "/analise",
    eyebrow: "Posição",
    title: "Tabuleiro de análise",
    body: "Cole uma FEN ou mova as peças: o motor devolve as melhores linhas com setas e avaliação.",
  },
  {
    to: "/laboratorio",
    eyebrow: "Experimento",
    title: "Laboratório de duelo",
    body: "Dois Stockfish jogam entre si. Um lado pode usar strict_v1 e mostrar a auditoria de cada escolha.",
  },
]

export function HomePage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Três formas de usar o mesmo motor"
        lede="Busca do Stockfish, decisão por regras escritas neste projeto. Tudo roda em loopback, sem conta e sem contato com plataforma nenhuma."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {WORKFLOWS.map((item) => (
          <Link key={item.to} to={item.to} className="no-underline">
            <Card className="h-full gap-2 p-5 transition-colors hover:border-border-strong hover:bg-secondary">
              <span className="label-micro">{item.eyebrow}</span>
              <h3 className="m-0 font-sans text-base font-semibold">{item.title}</h3>
              <p className="m-0 text-[0.88rem] text-ink-3">{item.body}</p>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="gap-4 p-6">
        <h2 className="m-0 label-micro">O que strict_v1 é, e o que não é</h2>
        <p className="m-0 max-w-[74ch] text-[0.9rem] text-ink-2">
          <code className="text-brass">strict_v1</code> é o conjunto de regras deste projeto: sete
          portões obrigatórios, cada um com valor medido, limiar registrado e explicação. Uma jogada
          só é marcada como brilhante quando passa por todos. Quando nenhuma candidata passa, isso
          também fica escrito.
        </p>
        <Separator />
        <p className="m-0 max-w-[74ch] text-[0.9rem] text-ink-3">
          Não é uma reprodução do rótulo do Chess.com e não deve ser lida como tal. Os limiares são
          escolhas nossas, versionadas em <code>config/strict_v1.yaml</code>, e mudam quando a
          documentação de regras muda junto.
        </p>
        <Separator />
        <p className="m-0 max-w-[74ch] text-[0.9rem] text-ink-3">
          A avaliação do motor vira pontos esperados entre 0 e 1, sempre do ponto de vista de quem
          está a jogar. Cada candidata passa por descoberta com MultiPV e depois por uma confirmação
          individual; é a confirmação que define o ranking mostrado, não a ordem bruta do MultiPV.
        </p>
      </Card>
    </div>
  )
}
