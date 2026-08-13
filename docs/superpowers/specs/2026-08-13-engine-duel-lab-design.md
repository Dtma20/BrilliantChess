# Laboratório de duelo Stockfish com seleção strict_v1

Data: 2026-08-13

Estado: aprovado para especificação; aguardando revisão antes do planejamento.

## Objetivo

Adicionar uma página local de laboratório em que dois processos do mesmo
Stockfish jogam um contra o outro. Cada lado poderá escolher um perfil de
força. Cada lado também terá uma política de escolha: normal ou \`strict_v1\`.

O perfil \`strict_v1\` deve escolher a candidata brilhante elegível com maior
pontuação. Se não houver candidata elegível, deve jogar a melhor jogada normal
e registrar explicitamente esse fallback. O objetivo é tornar observável se os
critérios de brilhantismo produzem comportamento útil quando comparados com um
Stockfish mais fraco sem critérios.

## Limites de escopo

- Os dois lados usam o mesmo executável Stockfish já configurado para o app;
  não haverá seleção de outro binário UCI.
- O laboratório é local e servido apenas em loopback, preservando os avisos e
  os limites de fair play da interface existente.
- O autoplay ocorre somente enquanto a página do laboratório está aberta.
- Uma partida termina após 100 lances completos (200 meios-lances) se não
  houver resultado normal pelas regras de xadrez. Esse resultado é exibido
  como \`Empate por limite experimental\`, distinto de empate oficial.
- A funcionalidade não adiciona integração com plataformas externas, leitura de
  tela, automação de cliques, persistência em banco ou importação de partidas.

## Conceitos

Cada cor terá um \`MatchProfile\`:

- \`strength_key\`: um nível Stockfish existente, de \`iniciante\` a \`maximo\`;
- \`policy\`: \`normal\` ou \`strict_v1\`.

O padrão inicial será:

| Cor | Força | Política |
| --- | --- | --- |
| Brancas | \`maximo\` | \`strict_v1\` |
| Pretas | \`iniciante\` | \`normal\` |

Uma \`MatchState\` será independente de \`GameState\`, pois uma partida de
laboratório não tem pessoa jogadora. Ela armazenará FEN inicial, sequência
UCI/SAN, os dois perfis, status do laboratório, número máximo de meios-lances
e registros de decisão por jogada.

Cada registro de decisão conterá a jogada escolhida, a política usada, o
perfil do lado, se houve fallback, a decisão \`strict_v1\` completa quando
aplicável, os portões e valores medidos, as linhas principais e a versão do
conjunto de regras.

## Arquitetura

### Ciclo de vida das engines

\`EnginePairSession\` será criado pela aplicação web ao lado da \`EngineSession\`
existente. Ele abrirá duas instâncias independentes de \`StockfishEngine\`, uma
para as brancas e outra para as pretas, ambas a partir do mesmo caminho de
binário. As duas instâncias serão lazy e fechadas no shutdown do FastAPI.

Os recursos configurados do motor serão divididos entre os dois processos:

- \`threads = max(1, configurado // 2)\` por processo;
- \`hash_mb = max(16, configurado // 2)\` por processo.

Isso limita a sobrecarga do laboratório em máquinas que já executam análise ou
partidas humanas. Cada processo mantém seu próprio lock UCI e pode aplicar o
perfil de força correspondente sem compartilhar estado de \`UCI_Elo\` com o
outro lado.

### Escolha de jogada

O caso de uso \`choose_brilliant_move\` será a única fronteira que transforma
análise em uma escolha \`strict_v1\`. Ele receberá \`ChessEngine\`,
\`BoardService\`, posição, \`RuleSet\` e orçamentos determinísticos.

Para cada lado com política \`strict_v1\`, o fluxo será:

1. descoberta MultiPV e confirmação individual das candidatas;
2. cálculo da evidência de sacrifício, incluindo os detectores concretos
   necessários a esta entrega;
3. avaliação de melhor defesa e estabilidade;
4. execução dos sete portões obrigatórios de \`strict_v1\`;
5. cálculo de \`BrilliantDecision\` e \`brilliance_score\`;
6. escolha da candidata elegível de maior score, com desempate estável por
   menor perda de pontos esperados e UCI;
7. selecao `near_brilliant` para a melhor candidata auditada que continue
   objetivamente segura, caso nenhuma passe todos os portões;
8. fallback para a melhor jogada normal do perfil do lado somente se tambem nao
   existir candidata `near_brilliant` segura.

Evidência ausente torna o portão correspondente \`indeterminate\` e impede a
elegibilidade. Nenhuma heurística parcial será apresentada como brilhantismo
\`strict_v1\`.

O nível de força selecionado controla a jogada normal e o fallback. A análise
que confirma a elegibilidade continua em força total, seguindo o contrato
atual de \`StockfishEngine.analyze\` para análises objetivas.

### Autoplay e API

O servidor não terá worker de fundo. A página agenda o próximo pedido somente
quando ainda está aberta, portanto fechar a aba interrompe o autoplay sem
deixar um processo de partida rodando.

Rotas locais propostas:

- \`POST /api/match\`: cria uma partida de laboratório com os perfis e a FEN
  opcional;
- \`GET /api/match/{match_id}\`: recupera o estado em memória;
- \`POST /api/match/{match_id}/step\`: executa exatamente um meio-lance e
  devolve o estado e o registro de decisão;
- \`GET /api/match/{match_id}/pgn\`: baixa a partida com comentários PGN para os
  registros de decisão.

O frontend chama \`step\` com \`setTimeout\` após cada resposta. Pausar cancela
o próximo agendamento no navegador; retomar agenda o próximo meio-lance. A API
rejeita passos depois de resultado normal ou limite experimental.

## Interface

Uma página \`/laboratorio\` será adicionada à navegação existente. Ela exibirá:

- seleção de força e política para brancas e pretas;
- iniciar, pausar, reiniciar e exportar PGN;
- tabuleiro somente de leitura;
- indicação de qual lado está analisando;
- lista de lances com etiquetas \`strict_v1\`, \`fallback\` e \`normal\`;
- painel de auditoria para o lance selecionado, incluindo candidata escolhida,
  score, portões, evidência de sacrifício, linhas principais e versão das
  regras.

Partidas concluídas por 200 meios-lances exibem \`Empate por limite
experimental (100 lances)\`. O PGN usa resultado \`1/2-1/2\` nesse caso e inclui
comentários que distinguem a decisão experimental dos resultados oficiais do
tabuleiro.

## Configuração

Uma seção \`web.lab\` definirá no mínimo:

- \`max_fullmoves: 100\`;
- os orçamentos em nós para descoberta, confirmação, melhor defesa e
  estabilidade;
- o atraso entre meios-lances usado pelo autoplay do frontend.

Os testes usarão orçamentos pequenos e determinísticos. A configuração padrão
do laboratório usará nós, não tempo, para que as decisões \`strict_v1\` sejam
reproduzíveis. A interface informará que a política estrita é mais lenta por
executar confirmação e estabilidade.

## Testes e aceitação

- testes puros para \`choose_brilliant_move\`: candidata elegível, desempate,
  evidência ausente e fallback;
- testes do detector de sacrifício e dos portões necessários à seleção;
- testes de \`MatchState\`: alternância de cor, término normal, limite de 200
  meios-lances e bloqueio após término;
- testes de API com duas engines falsas independentes: perfis, passo único,
  autoplay observável por chamadas sucessivas, pausa no cliente e erro após o
  término;
- teste de fechamento das duas engines durante o shutdown;
- testes do PGN: perfis, resultado por limite experimental e comentários de
  auditoria;
- \`pytest\`, \`ruff check .\`, \`ruff format --check .\` e \`mypy src\` limpos;
- atualização de \`docs/domain-rules.md\`, configuração, documentação da
  interface e uma ADR, conforme as regras do repositório para qualquer mudança
  da definição prática de brilhante.

## Alternativas rejeitadas

- Reutilizar uma única \`EngineSession\` para os dois lados: reduziria consumo,
  mas compartilharia estado de força e tornaria o experimento menos isolado.
- Selecionar apenas por qualidade/top-N: seria mais rápido, mas é uma
  heurística e não pode ser chamada de \`strict_v1\`.
- Jogar normalmente e rotular depois: útil para auditoria, mas não testa o
  comportamento de seleção pedido.
- Worker de fundo no servidor: permitiria continuar após fechar a aba, mas
  adicionaria concorrência e ciclo de vida que não são necessários para este
  laboratório local.
