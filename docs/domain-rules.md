# Regras do dominio — `strict_v1`

Especificacao normativa. Toda mudanca de regra passa por este arquivo, pela
configuracao, pelos testes do portao e, se alterar a definicao de brilhante, por
uma ADR.

Os limiares abaixo sao **hipoteses de engenharia** para iniciar calibracao. Eles
nao sao os limiares proprietarios do Chess.com.

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

Uma candidata so e brilhante se **todos** os portoes retornarem `passed`.
`indeterminate` nao aprova.

### `GATE_LEGAL_001` — jogada legal

- Entrada: posicao e jogada.
- Saida: aprovado se a jogada e legal.
- Limiar: nao configuravel.
- Testes: `test_illegal_move_fails_the_first_gate`.

### `GATE_QUALITY_001` — melhor ou quase melhor

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

- Entrada: `SacrificeEvidence`.
- Aprovado se detectado, a peca oferecida e cavalo, bispo, torre ou dama,
  `nominal_value >= sacrifice.min_nominal_value` e
  `confidence >= sacrifice.min_confidence`.
- Limiares: `2.75` e `0.70`.
- Peao sozinho nao satisfaz o portao em `strict_v1`. Promocoes e subpromocoes
  ganharao regra propria depois.
- Exemplo negativo: oferta de peao; evidencia com confianca `0.2`.
- Testes: `test_sacrifice_gate_rejects_pawn_only_offer`,
  `test_sacrifice_gate_rejects_low_confidence`,
  `test_sacrifice_gate_rejects_absent_evidence`.

### `GATE_SOUNDNESS_001` — sacrificio correto

- Entrada: `EP_loss` apos a **melhor defesa** e a marca
  `depends_on_opponent_error`.
- Aprovado se a perda continua dentro do limite de qualidade e a ideia nao
  depende de erro adversario.
- Sem avaliacao da melhor defesa, o portao retorna `indeterminate`.
- Testes: `test_soundness_is_indeterminate_without_best_defense`,
  `test_soundness_rejects_lines_that_need_an_opponent_error`.

### `GATE_NOT_BAD_AFTER_001` — posicao resultante nao ruim

- Aprovado se `EP_apos >= resulting_position.min_expected_points_after`
  (`0.45`) ou se ha empate forcado comprovado e aceito pela configuracao.
- Testes: `test_not_bad_after_accepts_forced_draw_when_configured`.

### `GATE_NOT_ALREADY_WON_001` — posicao anterior nao completamente ganha

- Aprovado se `EP_antes < prior_position.max_expected_points_before` (`0.95`).
- Usa o score da posicao **anterior**, nunca o posterior.
- Testes: `test_not_already_won_uses_the_prior_position`,
  `test_already_winning_position_is_never_declared_brilliant` (propriedade).

### `GATE_STABILITY_001` — analise estavel

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

### Comparacao com a melhor defesa

O EP da candidata confirmada e o EP apos a melhor defesa vem de buscas
independentes, com raizes diferentes. Ao calcular a perda apos a melhor defesa,
`strict_v1` aceita uma melhoria negativa dentro de
`robustness.max_ep_drift_on_deeper_search` e a normaliza para zero. A margem
nao vale para o ranking dentro da mesma confirmacao, que continua usando a
tolerancia numerica global de `1e-6` e acusa inversoes reais de ordem.
Se a divergencia exceder essa margem, a candidata fica `indeterminate` em
`GATE_SOUNDNESS_001` e nao e selecionada; o laboratorio usa o fallback normal
em vez de interromper a partida.

## Deteccao de sacrificio

Valores materiais padrao: peao `1.0`, cavalo `3.2`, bispo `3.3`, torre `5.0`,
dama `9.0`. O rei nao tem valor mensuravel. Esses valores detectam concessao
material; a correcao da jogada vem sempre do motor.

Tipos previstos (`SacrificeKind`): `DESTINATION_OFFER`, `LEFT_HANGING`,
`EXCHANGE_SACRIFICE` (obrigatorios na Entrega 4), `DECLINED_RECAPTURE` e
`CLEARANCE_OR_DEFLECTION` (segunda entrega do detector).

Confianca (`sacrifice_confidence`), pesos configuraveis, cada evidencia contando
uma unica vez:

| Evidencia | Peso |
| --- | --- |
| Captura legal clara da peca oferecida | 0.35 |
| Perda material liquida minima na linha de aceitacao | 0.20 |
| Motor inclui a aceitacao entre respostas plausiveis | 0.15 |
| Mecanismo tatico verificavel na PV | 0.15 |
| Padrao persiste em analise mais profunda | 0.15 |

`persists_under_deeper_search = None` significa "estagio nao executado" e nao
contribui. Confianca nunca substitui portao.

Nao sao sacrificio valido: captura protegida que ganha material; troca
equivalente; peca ja inevitavelmente perdida; linha que so funciona apos erro
adversario; jogada que perde material e piora a posicao; oferta em posicao ja
trivialmente ganha; pseudo-sacrificio por erro de contagem em en passant,
promocao ou roque.

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

O valor do sacrificio satura em `5.0` (torre). Uma dama oferecida nao vence
automaticamente uma torre oferecida: evidencia sem valor nao pontua.

## Selecao

Camadas, nesta ordem:

1. candidatas com `is_brilliant = True`;
2. `near_brilliant`: candidata auditada com `EP_loss <=
   selection.safe_max_expected_points_loss` (`0.03`) e com os portoes de
   legalidade, solidez contra a melhor defesa, posicao resultante e estabilidade
   aprovados;
3. melhor jogada objetiva.

Uma `near_brilliant` pode falhar nos criterios de classificacao (por exemplo,
na exigencia de sacrificio), mas nunca nos criterios de seguranca. Ela e marcada
como `selection=near_brilliant` no retorno da API e no PGN, sem receber o rotulo
de brilhante. Dentro dessa camada, os desempates sao maior score diagnostico,
menor `EP_loss` e ordem UCI estavel. A primeira camada nunca e relaxada para
forcar um sacrificio.

## Perfil por rating

`strict` e o unico perfil implementado. `beginner` e `advanced` sao estrategias
de configuracao futuras. Ate haver dataset calibrado, `--rating` selecionara
configuracao documentada e a CLI deve deixar claro que o comportamento e
aproximado.

## Historico

| Versao | Data | Mudanca |
| --- | --- | --- |
| `strict_v1` | 2026-08-12 | Definicao inicial dos sete portoes, mapeamentos de EP e pesos de pontuacao. |
| `strict_v1` | 2026-08-13 | Fallback `near_brilliant` seguro antes da jogada normal do perfil. |
