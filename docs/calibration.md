# Calibracao

## Objetivo

Ajustar limiares para aproximar julgamentos desejados **sem esconder regras**.
Nenhum limiar pode virar constante magica no codigo: tudo vive em
`config/*.yaml` e em `domain/rule_set.py`.

## Estado

Entrega 8. Ainda nao executada. Nenhum limiar atual foi calibrado com dados; sao
hipoteses iniciais.

## Dataset

Tres grupos, sem sobreposicao:

- positivos confiaveis;
- negativos confiaveis, incluindo negativos dificeis (troca equivalente, captura
  protegida, sacrificio refutado, peca ja perdida, posicao ja ganha);
- casos limitrofes.

Diversidade obrigatoria: rating, fase da partida, material, tipo de sacrificio e
resultado. Divida em ajuste, validacao e teste **por partida e por jogador**,
para nao vazar posicoes da mesma partida entre os conjuntos.

## Metricas

Prioridade em `strict_v1`: **precisao acima de recall**. E melhor chamar uma
jogada brilhante de "candidata forte" do que rotular um sacrificio incorreto
como brilhante.

- precision, recall e F1 de brilhante;
- falsos positivos e falsos negativos por categoria de sacrificio;
- taxa de indeterminados;
- estabilidade entre orcamentos (mesma decisao em discovery, confirmation e
  stability);
- concordancia humana;
- concordancia observada com exemplos publicos do Chess.com, quando
  legitimamente disponiveis, sempre reportada como observacao e nunca como
  garantia de equivalencia.

## Procedimento

1. Congele versao do motor, opcoes e orcamento em nos.
2. Rode o classificador sobre o conjunto de ajuste.
3. Analise erros por categoria antes de mexer em qualquer numero.
4. Altere um limiar por vez, registrando a justificativa.
5. Reavalie em validacao; so entao toque no conjunto de teste, uma unica vez.
6. Registre a mudanca no historico de `docs/domain-rules.md`.

## Limites conhecidos

- A formula e os limiares do Chess.com nao sao publicos; concordancia parcial e
  o maximo que se pode almejar.
- Versoes diferentes do Stockfish podem discordar em posicoes limitrofes; isso e
  registrado como instabilidade, nao corrigido apagando a fixture.
- Orcamento por tempo nao e reproduzivel e nao entra em calibracao.
