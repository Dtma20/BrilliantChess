# Exportação de partidas em PGN

Data: 2026-08-13
Estado: aprovada para planejamento

## Objetivo

Permitir que a pessoa baixe a partida local atual da tela **Jogar** como um
arquivo PGN, preservando a sequência de lances, o estado da partida e uma FEN
inicial personalizada quando houver.

## Decisão

A geração do PGN ficará no backend, em uma nova rota `GET
/api/game/{game_id}/pgn`. O frontend exibirá um botão `Exportar PGN` e fará o
download da resposta como arquivo `.pgn`.

O backend usará o `GameState` armazenado e a visão atual do tabuleiro. O
formato incluirá os cabeçalhos `Event`, `Site`, `White`, `Black` e `Result`.
Quando a partida começar de uma posição diferente da inicial, incluirá também
`SetUp "1"` e `FEN "..."`. O resultado será `1-0`, `0-1`, `1/2-1/2` ou `*`
enquanto a partida estiver em andamento.

Os nomes dos jogadores serão descritivos e locais: `Voce` para a pessoa e
`Motor (<nivel>)` para o adversário. O evento será `Brilliant Chess - Partida
local` e o site `Localhost`.

## Fluxo

1. A pessoa inicia e joga uma partida normalmente.
2. Clica em `Exportar PGN`.
3. O frontend requisita `/api/game/{id}/pgn`.
4. A API recupera a partida, calcula o resultado e devolve `application/x-chess-pgn`
   com `Content-Disposition` para download.
5. O navegador salva `brilliant-chess-<game_id>.pgn`.

O botão ficará desabilitado quando não houver partida carregada ou enquanto uma
jogada estiver sendo processada. A exportação será permitida tanto durante a
partida quanto após seu término.

## Testes e compatibilidade

- testar resposta PGN de uma partida em andamento;
- testar resultado de xeque-mate;
- testar headers `SetUp`/`FEN` para uma posição inicial personalizada;
- testar que um identificador inexistente retorna erro HTTP 400;
- manter o contrato JSON existente sem alterações incompatíveis;
- cobrir o clique/download no nível de funções do cliente somente se houver
  infraestrutura existente para JavaScript; o contrato principal será coberto
  pelo teste da API.

## Fora do escopo

- importar PGN;
- editar cabeçalhos no navegador;
- persistir partidas em banco;
- exportar análises, setas ou variantes do motor;
- integração com plataformas externas.
