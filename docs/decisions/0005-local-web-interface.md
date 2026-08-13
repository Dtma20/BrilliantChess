# 0005 — Interface web local para jogar e analisar

Data: 2026-08-12
Estado: aceita

## Contexto

A especificacao original adiava qualquer interface para a Entrega 9 e proibia
FastAPI no MVP sem necessidade demonstrada. A pessoa mantenedora pediu
explicitamente duas coisas: jogar contra o motor em tempo real e um tabuleiro de
analise com setas indicando as melhores jogadas, no estilo do Lichess e do
Chess.com. Isso demonstra a necessidade.

Ha uma tensao com o fair play: um tabuleiro de analise e, por natureza, dual-use.
A mesma tela que serve para estudar pode ser aberta ao lado de uma partida ao
vivo. Lichess e Chess.com convivem com isso oferecendo a ferramenta abertamente e
tratando o uso indevido como trapaca do lado de quem usa.

## Decisao

Existe uma interface web local, servida por `brilliant-chess serve`, com duas
paginas: `/jogar` e `/analise`.

Limites que definem o escopo e que nao devem ser afrouxados:

- o app **desenha o proprio tabuleiro**; ele nao le tela, nao captura tabuleiro
  de outro programa, nao automatiza cliques fora de si mesmo e nao cria overlay;
- nao existe cliente de nenhuma plataforma de xadrez; a posicao entra por FEN
  colada ou por lances feitos no proprio tabuleiro;
- o servidor escuta em `127.0.0.1` por padrao, e escutar fora do loopback imprime
  aviso de fair play;
- todas as paginas mostram o aviso de fair play de forma permanente.

Tecnicamente: FastAPI e uvicorn como adapters de entrada; o tabuleiro e escrito
em JavaScript e SVG sem dependencia externa, para funcionar offline e para que
as setas sejam controladas diretamente. Um unico processo Stockfish e
compartilhado pelo servidor, com acesso serializado pelo lock do proprio
`StockfishEngine` e encerramento no shutdown.

## Alternativas consideradas

- **Interface de terminal.** Rejeitado: setas sobre o tabuleiro sao o ponto do
  pedido, e ASCII nao entrega isso.
- **Aplicativo desktop.** Rejeitado: mais dependencias e empacotamento por
  sistema operacional, sem ganho para uso local.
- **Biblioteca de tabuleiro pronta via CDN.** Rejeitado: quebraria o
  funcionamento offline e adicionaria uma dependencia nao auditada.
- **Nao construir a analise por causa do risco de uso indevido.** Rejeitado: e a
  mesma funcionalidade que qualquer plataforma seria oferece publicamente, e a
  pessoa mantenedora pediu explicitamente. O risco e tratado com limites tecnicos
  e avisos, nao com ausencia da ferramenta.

## Consequencias

- FastAPI, uvicorn e httpx entram no projeto; o dominio continua sem conhece-los.
- Um novo port `ports/board.BoardService` mantem python-chess dentro de
  `adapters`, agora tambem para as regras de tabuleiro usadas pela interface.
- Forca reduzida usa `UCI_LimitStrength`/`UCI_Elo`. O adapter restaura forca
  total antes de qualquer analise, para que uma partida fraca nao contamine a
  avaliacao seguinte.
- Partidas ficam em memoria. Persistencia entra junto com o SQLite da Entrega 7.
- O estado volátil de uma partida pode ser baixado como PGN pela interface, mas
  o arquivo é uma exportação explícita e não substitui a persistência prevista
  para a Entrega 7.
