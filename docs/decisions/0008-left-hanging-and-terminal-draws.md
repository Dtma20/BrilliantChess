# 0008 - Peca deixada pendurada e empates terminais

**Status:** Aceita

**Data:** 2026-08-13

## Contexto

Duas lacunas apareceram na auditoria do laboratorio.

A primeira e de deteccao. O unico detector implementado era
`DESTINATION_OFFER`, que olha somente a casa de destino da candidata. Na partida
`1.Nf3 d5 2.c4 c6 3.cxd5 Nf6 4.dxc6 Nxc6 5.d4 g6 6.Nc3 Bg4 7.d5 Nb4 8.Qa4+ Bd7
9.Qxb4 a5 10.Qb3 a4 11.Qb4 e5 12.Qh4 a3 13.Rb1 Bf5 14.e3`, a torre branca de b1
fica capturavel por `...Bxb1` pela diagonal `f5-e4-d3-c2-b1`. O peao de c2 saiu
no lance 2 e foi capturado no lance 4, entao a linha esta aberta. `14.e3` nao
salva nem defende a torre. Como o destino `e3` contem um peao, o detector nao
media nada e a auditoria dizia que nenhuma peca havia sido oferecida.

A segunda e de desfecho. O motor recebe apenas a posicao, sem o caminho ate
ela. Repeticao e a regra dos cinquenta lances nao estao na FEN, entao nem o
Stockfish nem o `BoardService` conseguiam ver que uma candidata encerrava a
partida em empate. Um vaivem de torre com o motor avaliando `+9` era
apresentado como continuacao segura, e o portao de solidez ficava
`indeterminate` por "melhor defesa ainda nao avaliada" — uma explicacao falsa
para um lance que simplesmente terminava o jogo.

## Decisao

### `LEFT_HANGING`

Um novo tipo de evidencia mede pecas do lado que jogou que ficam capturaveis
**fora** da casa de destino. Cobre dois casos: peca exposta pela candidata e
peca que ja estava sob ataque e que a candidata escolheu nao salvar nem
defender. A casa de destino continua sendo territorio exclusivo de
`DESTINATION_OFFER`, entao os tipos nao se sobrepoem e nada e contado duas
vezes.

Somente lances **legais** do adversario na posicao resultante contam como
aceitacao. Isso descarta por construcao linha bloqueada, peca cravada que nao
pode capturar e ataque impossivel por xeque em curso. Peao e rei nunca sao a
peca oferecida.

Havendo mais de uma peca pendurada, a escolha e determinista: maior valor
nominal, depois a menor UCI de aceitacao, depois a casa. A ordem existe para
que a mesma posicao produza sempre a mesma auditoria.

Quando os dois tipos aparecem no mesmo lance, `DESTINATION_OFFER` vence. Nao e
uma questao de valor: uma peca colocada na casa de destino e a oferta mais
direta que existe e e a que o adversario tem de responder no lance seguinte.

Deteccao nao e brilhantismo. A compensacao continua vindo da melhor defesa, da
trajetoria material, da PV e da estabilidade. Se aceitar a peca deixa quem
jogou objetivamente pior sem compensacao medida, `GATE_SOUNDNESS_001` reprova.

### Empate imediato

O seletor passou a receber `PositionHistory` (FEN inicial mais os lances) em vez
de uma posicao solta, e a posicao raiz e derivada dela. Caminho e posicao nao
podem mais divergir, e as regras que dependem de historico ficam sempre
disponiveis.

Se a candidata encerra a partida em empate — afogamento, material
insuficiente, cinquenta lances ou tripla repeticao —, o resultado vale `0.5` de
pontos esperados por regra do jogo, e nao o que o motor achou da posicao. A
perda passa a ser `EP_antes - 0.5`, o que faz `GATE_QUALITY_001` reprovar
exatamente na medida do que foi entregue. Distancia de mate e centipawns sao
descartados, porque nao descrevem mais nada.

Os portoes de solidez e estabilidade sao aprovados com explicacao propria
("nao ha defesa", "nao ha linha posterior a estabilizar"), como no mate
terminal. Nenhum dos dois pode aprovar por ausencia de evidencia: um empate que
entrega vitoria e barrado pela qualidade, com valor medido a vista.

Um empate que nao concede nada — posicao equilibrada, `EP_antes` proximo de
`0.5` — continua selecionavel como `near_brilliant`. Isso e honesto: nao havia
vitoria a preservar.

## Consequencias

A auditoria de sacrificio deixa de depender da casa de destino e passa a
descrever a peca, a casa e o lance que a aceita, com esses dados no retorno da
API e no PGN. Cada busca de melhor defesa e de estabilidade e economizada em
posicao terminal, porque nao ha o que buscar.

O contrato da API subiu para a versao `2`. O front fixa a versao que conhece,
avisa quando o servidor responde outra e nunca indexa direto um valor vindo do
servidor.

`strict_v1` nao ficou mais permissivo: nenhum limiar mudou. A mudanca esta em
haver mais evidencia medida e menos silencio.
