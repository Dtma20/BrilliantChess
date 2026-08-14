# Regras do dominio — `strict_v1` e `strict_v2`

Especificacao normativa. Toda mudanca de regra passa por este arquivo, pela
configuracao, pelos testes do portao e, se alterar a definicao de brilhante, por
uma ADR.

Os limiares abaixo sao **hipoteses de engenharia** para calibracao local. Eles
**nao sao** os limiares proprietarios do Chess.com e este classificador nao e
equivalente ao Game Review do Chess.com.

## Identificadores e compatibilidade

| Identificador | Portoes | Detector de sacrificio | Nao obviedade | Estado |
| --- | --- | --- | --- | --- |
| `strict_v1` | 7 portoes | `DESTINATION_OFFER` e `LEFT_HANGING` (valor nominal) | Nao possui | Historico (imutavel) |
| `strict_v2` | 8 portoes | Troca-aware (`net_material_concession`, rejeicao de trocas limpas) | `GATE_NON_OBVIOUS_001` (busca rasa vs profunda) | Padrao do laboratorio |

`strict_v1` mantem seu comportamento e auditorias originais intocados.
`strict_v2` e o classificador padrao do laboratorio de duelos e elimina falsos
positivos em trocas de pecas menores.

## Pontos esperados

`EP` esta sempre em `[0, 1]` e sempre do ponto de vista de quem jogou.

- Com WDL: `EP = (wins + 0.5 * draws) / (wins + draws + losses)`
  (`WDL_MAPPING_VERSION = "wdl_v1"`).
- Sem WDL: `EP = 1 / (1 + 10 ** (-cp / 400))`
  (`CP_MAPPING_VERSION = "cp_logistic_400_v1"`).
- Mate: faixa reservada. `MATE_EP_EPSILON = 1e-4`, distancia limitada a 100
  lances. Mate a favor fica em `[0.9999, 1.0]`, mate contra em `[0.0, 0.0001]`,
  e scores comuns sao presos em `[0.0002, 0.9998]`. Assim mate sempre supera
  qualquer avaliacao nao-mate, e a distancia de mate serve so como desempate.
- Perda: `EP_loss = max(0, EP_melhor - EP_candidata)`. Diferenca negativa dentro
  de `EP_NOISE_TOLERANCE = 1e-6` vira zero e marca `clamped_noise`. Diferenca
  negativa maior e erro: indica confirmacao inconsistente.

## Portoes obrigatorios

Uma candidata so e brilhante se **todos** os portoes obrigatorios retornarem
`passed`. `indeterminate` ou `failed` nao aprovam.

### `GATE_LEGAL_001` — jogada legal (v1 e v2)

- Entrada: posicao e jogada.
- Saida: aprovado se a jogada e legal.
- Limiar: nao configuravel.
- Testes: `test_illegal_move_fails_the_first_gate`.

### `GATE_QUALITY_001` — melhor ou quase melhor (v1 e v2)

- Entrada: `EP_loss` da candidata e rank apos **confirmacao individual**.
- Aprovado se `EP_loss <= quality.max_expected_points_loss` **e**
  `rank <= quality.require_top_n`.
- Limiares: `0.015` e `3`.
- O rank do MultiPV de discovery nao vale: linhas de MultiPV nao recebem a mesma
  qualidade de busca.
- Exemplo positivo: `EP_loss = 0.002`, rank 1.
- Exemplo negativo: `EP_loss = 0.001` com rank 7.
- Testes: `test_quality_gate_needs_both_loss_and_rank`.

### `GATE_SACRIFICE_001` — sacrificio real de peca

#### Em `strict_v1` (`gate_sacrifice`)

- Entrada: `SacrificeEvidence`.
- Aprovado se detectado, peca oferecida e cavalo, bispo, torre ou dama,
  `nominal_value >= sacrifice.min_nominal_value` (`2.75`) e
  `confidence >= sacrifice.min_confidence` (`0.70`).
- Peao sozinho nao satisfaz o portao.

#### Em `strict_v2` (`gate_sacrifice_v2`)

- Entrada: `SacrificeEvidence` com `ExchangeEvidence`.
- Aprovado se ha concessao liquida real:
  `net_material_concession >= sacrifice.min_net_material_concession` (`1.0`),
  sem disposicoes negativas de troca (`CLEAN_EQUAL_TRADE`, `FAVORABLE_TRADE`,
  `OBVIOUS_RECAPTURE`, `TEMPORARY_OFFER` ou `DECLINED_RECAPTURE`).
- **Rejeicao de trocas limpas (Regressao Portuguesa):** Na linha `Bxc6+ bxc6`,
  o bispo capturou um cavalo (`3.2`) e foi recapturado (`3.3`). A concessao liquida
  (`0.1`) e inferior a `1.0` e a disposicao e `CLEAN_EQUAL_TRADE`. A explicacao
  emitida e:
  > *A sequência é uma troca limpa de material aproximadamente igual e, portanto, não satisfaz o portão de sacrifício.*
- Trocas equivalentes de torre ou dama e recapturas obvias sao analogamente
  rejeitadas.

### `GATE_SOUNDNESS_001` — sacrificio correto (v1 e v2)

- Entrada: `EP_loss` apos a **melhor defesa** e a marca
  `depends_on_opponent_error`.
- Aprovado se a perda continua dentro do limite de qualidade e a ideia nao
  depende de erro adversario.
- Sem avaliacao da melhor defesa, o portao retorna `indeterminate`.
- Testes: `test_soundness_is_indeterminate_without_best_defense`,
  `test_soundness_rejects_lines_that_need_an_opponent_error`.

### `GATE_NOT_BAD_AFTER_001` — posicao resultante nao ruim (v1 e v2)

- Aprovado se `EP_apos >= resulting_position.min_expected_points_after`
  (`0.45`) ou se ha empate forcado comprovado e aceito pela configuracao.
- Testes: `test_not_bad_after_accepts_forced_draw_when_configured`.

### `GATE_NOT_ALREADY_WON_001` — posicao anterior nao completamente ganha (v1 e v2)

- Aprovado se `EP_antes < prior_position.max_expected_points_before` (`0.95`).
- Usa o score da posicao **anterior**, nunca o posterior.
- Testes: `test_not_already_won_uses_the_prior_position`,
  `test_already_winning_position_is_never_declared_brilliant` (propriedade).

### `GATE_STABILITY_001` — analise estavel (v1 e v2)

- Entrada: drift de EP entre estagios, sobreposicao inicial das PVs e
  persistencia do mecanismo do sacrificio.
- Aprovado se `|drift| <= robustness.max_ep_drift_on_deeper_search` (`0.02`),
  sobreposicao `>= robustness.min_pv_overlap_plies` (`2`) e o mecanismo nao foi
  refutado.
- Sem estagio de estabilidade: `indeterminate` se a candidata esta a menos de
  `robustness.stability_threshold_margin` (`0.01`) de qualquer limiar continuo;
  caso contrario `passed`.
- Testes: `test_stability_without_budget_is_indeterminate_only_near_a_threshold`,
  `test_stability_fails_on_drift_or_refuted_mechanism`.

### `GATE_NON_OBVIOUS_001` — nao obviedade (exclusivo `strict_v2`)

- Entrada: `NonObviousnessEvidence`.
- Compara busca rasa (**5.000 nos**, **MultiPV 5**) com a confirmacao profunda.
- Aprovado se pelo menos uma condicao de surpresa for satisfeita (**semantica OU**):
  1. `EP_IMPROVEMENT`: `deep_expected_points - shallow_expected_points >= min_expected_points_improvement` (`0.03`);
  2. `RANK_IMPROVEMENT`: `shallow_rank - deep_rank >= min_rank_improvement` (`2`);
  3. `DEEP_SURPRISE`: `shallow_rank > max_obvious_shallow_rank` (`2`) e `deep_rank <= max_confirmed_rank` (`3`).
- Sem evidencia rasa valida ou se o motor falhar, o portao retorna `failed`.
- Testes: `test_v2_non_obviousness_accepts_deep_surprise`.

## Deteccao de sacrificio e trocas

Valores materiais padrao: peao `1.0`, cavalo `3.2`, bispo `3.3`, torre `5.0`,
dama `9.0`. O rei nao tem valor mensuravel.

Em `strict_v2`, `BoardService.exchange_lines` extrai a arvore deterministica de
recapturas legais na casa de destino (incluindo x-rays) e calcula:
- `net_material_concession`: diferenca entre perdas do lado que jogou e todas as
  capturas adversarias na linha;
- Tolerancia para trocas equivalentes (`equal_trade_tolerance = 0.5`);
- Disposicoes tipadas: `CLEAN_EQUAL_TRADE`, `FAVORABLE_TRADE`, `OBVIOUS_RECAPTURE`,
  `TEMPORARY_OFFER`, `DECLINED_RECAPTURE`, `DESTINATION_OFFER`, `LEFT_HANGING`,
  `EXCHANGE_SACRIFICE`, `CLEARANCE_OR_DEFLECTION`.

## Pontuacao (0 a 100)

Calculada apenas depois dos portoes. Candidatas reprovadas recebem pontuacao
diagnostica com `selectable = False`.

| Componente | Peso | Comportamento |
| --- | --- | --- |
| Qualidade | 30 | `30 * (1 - EP_loss / limite)`, monotonicamente nao crescente |
| Sacrificio | 35 | `0.40 * valor + 0.30 * concessao liquida + 0.30 * confianca`, vezes a clareza do tipo |
| Carater forcante | 15 | `0.60 * pressao sobre respostas + 0.40 * densidade forcante na PV` |
| Unicidade | 10 | `10 / (1 + alternativas equivalentes)` |
| Robustez | 10 | `0.40 * drift + 0.30 * sobreposicao + 0.30 * persistencia` |

## Selecao

Camadas, nesta ordem:

1. candidatas com `is_brilliant = True` (todos os portoes obrigatorios aprovados);
2. `near_brilliant`: candidata auditada com `EP_loss <=
   selection.safe_max_expected_points_loss` (`0.03`) e com os portoes de
   seguranca aprovados;
3. melhor jogada objetiva (fallback normal do perfil).

## Desfechos imediatos

Em xeque-mate ou empate terminal (afogamento, material insuficiente, 50 lances,
tripla repeticao):
- Empate vale `EP = 0.5` por regra do tabuleiro;
- `EP_loss = max(0, EP_antes - 0.5)`;
- Solidez e estabilidade sao aprovadas com explicacao canonica de desfecho sem
  chamar o motor.

## Exploracao de abertura

A fase de abertura no laboratorio de duelo suporta 4 modos operacionais:
- `EXPLORATORY`: combinacao de linhas da suite com transicoes amostradas via MultiPV;
- `CONTROLLED`: adesao estrita as linhas da suite;
- `CHAOTIC`: alta entropia com maior tolerancia de corte e temperatura;
- `OFF`: duelo inicia na posicao inicial sob politica de jogo regular.

Na amostragem MultiPV, candidatos com `EP loss > max_ep_loss` sao descartados,
e a selecao e feita por amostragem softmax com temperatura deterministica via semente uint64.

## Historico

| Versao | Data | Mudanca |
| --- | --- | --- |
| `strict_v1` | 2026-08-12 | Definicao inicial dos sete portoes, mapeamentos de EP e pesos de pontuacao. |
| `strict_v1` | 2026-08-13 | Fallback `near_brilliant` seguro antes da jogada normal do perfil. |
| `strict_v1` | 2026-08-13 | `LEFT_HANGING` implementado; empate imediato vale `0.5` EP por regra do tabuleiro. Ver ADR 0008. |
| `strict_v2` | 2026-08-13 | Classificador troca-aware com concessao liquida, rejeicao de trocas limpas, 8 portoes obrigatorios e portao de nao obviedade. Ver ADR 0009. |
| `opening_v1` | 2026-08-14 | Suite offline curada e amostragem MultiPV com limitacao de perda de EP e sementes deterministicas. Ver ADR 0010. |


