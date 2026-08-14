# 0010 - Exploração de Abertura com Suíte Offline e MultiPV Amostrado

**Status:** Aceita

**Data:** 2026-08-14

## Contexto

No laboratório de duelo entre motores, partidas iniciadas a partir da posição inicial convencional (`rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`) tendiam a convergir rapidamente para as mesmas linhas principais determinísticas do Stockfish. Isso limitava a variedade de posições táticas geradas e a oportunidade de observar e auditar jogadas brilhantes em estruturas de peões e desequilíbrios materiais diversos.

Era necessário introduzir um mecanismo de exploração de aberturas imprevisível, variado e estruturado, respeitando as seguintes restrições:

1. **Determinismo e reprodutibilidade:** Toda escolha de abertura e amostragem de lances deve ser estritamente controlada por uma semente (`seed`) de 64 bits (`uint64`), sem depender de relógio de parede ou estado global não reprodutível.
2. **Suíte offline de dados puros:** Nenhuma dependência de livros de abertura binários externos volumosos ou scraping de sites externos. O catálogo de aberturas deve ser mantido localmente como um conjunto de dados imutável em JSON.
3. **Controle de qualidade e segurança material:** Os lances adicionais exploratórios amostrados após o término da linha da suíte não podem arruinar a integridade tática da partida, devendo ser limitados por perda de pontos esperados ($\text{EP loss} \le \text{max\_ep\_loss}$) através de amostragem softmax parametrizada por temperatura.
4. **Transição limpa para políticas de duelo:** Ao término da fase de abertura, o duelo deve retornar automaticamente à política configurada de cada jogador (`strict_v2`, `strict_v1` ou `normal`).
5. **Auditoria e rastreabilidade total:** Cada meio-lance jogado durante a fase de abertura carrega metadados ricos (`OpeningMoveAudit`), indicando a suíte de origem, ECO, nome, variação, rank do candidato no motor, perda de EP e semente utilizada, exportáveis no cabeçalho e comentários do PGN.

## Decisão

### 1. Modos de Exploração e Configuração

Definiu-se o enum puro `OpeningMode` com 4 modos operacionais:

- `EXPLORATORY` (`"exploratory"`, padrão): Exploração balanceada combinando linhas da suíte com transições suaves via MultiPV.
- `CONTROLLED` (`"controlled"`): Exploração conservadora, aderindo rigorosamente às linhas da suíte com desvios estritamente limitados.
- `CHAOTIC` (`"chaotic"`): Exploração de alta entropia e linhas táticas afiadas, utilizando maior temperatura e tolerância de corte.
- `OFF` (`"off"`): Desativação completa da exploração; a partida inicia a partir da FEN inicial sob a política de duelo padrão.

A configuração `OpeningConfig` aceita parâmetros ajustáveis: `mode`, `seed`, `line_id`, `min_plies`, `max_plies`, `extra_plies`, `max_ep_loss`, `temperature` e `candidate_breadth`.

### 2. Suíte de Aberturas Curada Localmente

Implementou-se um catálogo puro em `src/brilliant_chess/adapters/opening_suite/` contendo 30+ linhas de abertura clássicas e modernas cobrindo todos os grupos de ECO (A a E):

- Defesas Siciliana, Francesa, Caro-Kann, Escandinava, Pirc;
- Ruy Lopez, Italiana, Gambito do Rei, Quatro Cavalos;
- Gambito da Dama, Defesa Eslava, Defesa Índia do Rei, Defesa Nimzoíndia, Defesa Grünfeld;
- Abertura Inglesa, Reti, Bird, Ataque Índio do Rei.

Cada linha da suíte define `id`, `eco`, `name`, `variation`, `moves_san`, `moves_uci` e `tags`.

### 3. Mecanismo de Seleção com Rotação e Evitação de Repetições

O `OpeningSelector` utiliza o gerador pseudo-aleatório determinístico `PCG64` do `numpy.random` inicializado com a semente configurada:

- Quando `line_id` é fornecido, a linha correspondente é selecionada diretamente.
- Em partidas consecutivas de uma sessão web, o `OpeningSessionTracker` rastreia linhas recentemente jogadas e prioriza aberturas inéditas ou menos frequentes através de penalidades ponderadas.

### 4. Amostragem MultiPV com Limitação de Perda de EP

Quando a linha da suíte atinge `planned_exit_ply` e `extra_plies > 0`, o motor avalia a posição via MultiPV com orçamento determinístico em nós:

1. Os candidatos com $\text{EP loss} > \text{max\_ep\_loss}$ são filtrados.
2. Se nenhuma candidata satisfizer o critério de corte, joga-se a melhor jogada (rank 1) e a fase de abertura é encerrada imediatamente (`QUALITY_CUTOFF_EXCEEDED`).
3. As probabilidades são calculadas via função softmax com temperatura $T$:
   $$P(m_i) = \frac{\exp(-\text{ep\_loss}_i / T)}{\sum_j \exp(-\text{ep\_loss}_j / T)}$$
4. Um lance é amostrado deterministicamente com base na semente do motor.

### 5. Proveniência e Auditoria

- Todos os lances jogados durante a abertura recebem a marcação `SelectionKind.OPENING_EXPLORATION` (`"opening_exploration"`).
- O objeto `OpeningMoveAudit` registra: `opening_id`, `name`, `eco`, `variation`, `source` (`"suite"` ou `"multipv"`), `opening_ply`, `planned_exit_ply`, `seed`, `candidate_rank`, `candidate_ep_loss`, `quality_cutoff` e `candidates_considered`.
- O exportador PGN inclui cabeçalhos `[Opening "..."]`, `[ECO "..."]`, `[Variation "..."]`, `[OpeningMode "..."]`, `[OpeningSeed "..."]`, `[OpeningPlies "..."]` e anotações explicativas no comentário dos lances.

### 6. Integração na Interface Web e Laboratório

- A API REST local foi versionada para o esquema de contrato `3` (`API_SCHEMA_VERSION = "3"`).
- No laboratório, adicionou-se o seletor de variedade de abertura no painel de configuração da mesa, mantendo preservada a disposição dos comandos do duelo.
- O painel de auditoria exibe o componente `OpeningDetail` quando um lance de abertura é selecionado.

## Consequências

- Partidas no laboratório de duelo tornam-se dinâmicas e imprevisíveis, explorando uma grande diversidade de posições do meio-jogo.
- Reprodutibilidade 100% garantida por semente.
- Todas as restrições de fair play, ausência de scrapers externos e orçamentos determinísticos baseados em nós são estritamente mantidas.
