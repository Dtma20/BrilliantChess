# 0009 - Classificador `strict_v2` com consciência de troca e não obviedade

**Status:** Aceita

**Data:** 2026-08-13

## Contexto

A auditoria de partidas no laboratório e em testes de regressão revelou duas limitações na especificação histórica `strict_v1`:

1. **Falsos positivos em trocas iguais (Regressão Portuguesa):**
   Na posição após `1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.e3 Bg4 5.h3 Bxf3 6.Qxf3 e6 7.Nc3 Nbd7 8.Bd2 Bb4`, o lance `9.Bxc6+` (seguido por `9...bxc6`) foi rotulado como sacrifício por `strict_v1`. O detector `DESTINATION_OFFER` media apenas que um bispo (valor nominal `3.3`) havia sido entregue na casa `c6` onde as pretas possuíam capturas legais. No entanto, o bispo capturou um cavalo em `c6` (valor `3.2`) e foi imediatamente recapturado por um peão (`bxc6`). Tratava-se de uma troca limpa de peças menores de valor aproximadamente igual, e não de uma concessão material real.
2. **Ausência de critério de não obviedade:**
   Em `strict_v1`, jogadas óbvias e recapturas forçadas que envolviam entrega material podiam ser consideradas brilhantes mesmo quando qualquer busca superficial de motor as identificava instantaneamente como a escolha trivial de rank 1.

Além disso, era fundamental manter o comportamento e o significado histórico de `strict_v1` rigorosamente preservados, sem reinterpretar partidas ou registros PGN antigos.

## Decisão

### 1. Separação de Identificadores e Compatibilidade Histórica

- `strict_v1` permanece como o classificador histórico imutável: 7 portões obrigatórios, detector de destino/peça pendurada e orçamentos originais.
- `strict_v2` é introduzido como um perfil e rule set separado (`id: "strict_v2"`), configurado como padrão no laboratório de duelo entre motores, mantendo `strict_v1` selecionável para comparação auditável.

### 2. Evidência de Troca e Concessão Material Líquida

`strict_v2` substitui a dependência exclusiva do valor nominal bruto pela análise de trajetórias de troca através da porta de tabuleiro (`BoardService.exchange_lines`):

- **Fronteira com `python-chess`:** O adapter de tabuleiro é o único local que manipula objetos da biblioteca de xadrez, devolvendo traços puros (`ExchangeTrace`, `ExchangePly`) ordenados deterministicamente por UCI.
- **Concessão Material Líquida:** Mede-se a perda líquida real:
  $$\text{net\_material\_concession} = \max(0, \text{mover\_losses} - \text{all\_opponent\_captures})$$
- **Rejeição de Trocas Limpas:** Trocas equivalentes de bispo por cavalo (`3.3` vs `3.2` dentro de `equal_trade_tolerance = 0.5`), trocas de torre por torre e trocas de dama por dama são classificadas como `ExchangeDisposition.CLEAN_EQUAL_TRADE` ou `OBVIOUS_RECAPTURE` e rejeitadas pelo portão de sacrifício.
- **Explicação em Português para a Regressão:** Para a troca `Bxc6+ bxc6`, o portão de sacrifício `strict_v2` emite explicitamente a explicação:
  > *A sequência é uma troca limpa de material aproximadamente igual e, portanto, não satisfaz o portão de sacrifício.*
- **Disposições Tipadas Rejeitadas:** `CLEAN_EQUAL_TRADE`, `FAVORABLE_TRADE`, `OBVIOUS_RECAPTURE`, `TEMPORARY_OFFER` e `DECLINED_RECAPTURE` (quando o histórico de lances está presente).
- **Recapturas e X-Ray:** O traço de trocas segue múltiplos plies na casa de destino, incluindo peças desobstruídas (*x-ray recaptures*). Sacrifícios de qualidade reais (ex.: torre por peça menor) com concessão líquida $\ge 1.0$ são aceitos como `SacrificeKind.EXCHANGE_SACRIFICE`.

### 3. Oito Portões Obrigatórios e Não Obviedade

`strict_v2` avalia exatamente 8 portões obrigatórios em sequência:
1. `GATE_LEGAL_001` — jogada legal
2. `GATE_QUALITY_001` — melhor ou quase melhor (EP loss $\le 0.015$, rank $\le 3$)
3. `GATE_SACRIFICE_001` — sacrifício real com consciência de troca (`gate_sacrifice_v2`)
4. `GATE_SOUNDNESS_001` — solidez contra a melhor defesa
5. `GATE_NOT_BAD_AFTER_001` — posição resultante não ruim ($\text{EP}_{\text{após}} \ge 0.45$)
6. `GATE_NOT_ALREADY_WON_001` — posição anterior não completamente ganha ($\text{EP}_{\text{antes}} < 0.95$)
7. `GATE_STABILITY_001` — análise estável em busca profunda
8. `GATE_NON_OBVIOUS_001` — não obviedade (surpresa rasa vs profunda)

#### Portão de Não Obviedade (`GATE_NON_OBVIOUS_001`)

Executa uma busca rasa preliminar com orçamento determinístico fixo de **5.000 nós** e **MultiPV 5** e compara com a confirmação profunda:
- Aprovado por semântica **OU** se qualquer condição for satisfeita:
  1. Melhoria de pontos esperados: $\text{EP}_{\text{deep}} - \text{EP}_{\text{shallow}} \ge 0.03$;
  2. Melhoria de rank: $\text{rank}_{\text{shallow}} - \text{rank}_{\text{deep}} \ge 2$;
  3. Descoberta profunda: jogada fora do top 2 raso ($\text{rank}_{\text{shallow}} > 2$ ou não presente no MultiPV raso) que atinge o top 3 confirmado ($\text{rank}_{\text{deep}} \le 3$).
- Se a evidência rasa estiver ausente ou o motor não fornecer dados, o portão falha de forma conservadora. Uma pontuação alta nunca resgata um portão obrigatório reprovado.

### 4. Proveniência e Auditoria Completa

As auditorias de candidatos em `strict_v2` expõem:
- Evidência completa de troca (`ExchangeEvidence`), mesmo em casos de rejeição;
- Evidência de não obviedade (`NonObviousnessEvidence`);
- Versão do detector (`detector_version`);
- Identidade do motor e redes neurais (`engine_identity`, incluindo versão e NNUE);
- Orçamentos em nós de todos os estágios (`shallow`, `discovery`, `confirmation`, `best_defense`, `stability`).
- Serialização em PGN preservando cabeçalhos e comentários auditáveis sem quebrar o formato histórico.

### 5. Fair Play e Limites Éticos

- O sistema roda estritamente em **loopback local** (`127.0.0.1`).
- Não há integração com partidas ao vivo externas, captura de tela, leitura de navegador ou overlays.
- Este classificador é uma construção conceitual aberta deste projeto e **não é equivalente nem afiliado ao Game Review do Chess.com**.

## Consequências

- O laboratório adota `strict_v2` como padrão, eliminando falsos positivos em trocas de peças menores e jogadas triviais.
- `strict_v1` segue disponível para testes e benchmarks comparativos.
- Todos os testes de integração e golden tests permanecem estritamente determinísticos e baseados em nós.
