# 0003 — Licenciamento compativel com GPL e portao indeterminado

Data: 2026-08-12
Estado: aceita, com uma pendencia

## Contexto

Duas decisoes pequenas precisavam de registro antes de virarem habito.

### Licenca

`python-chess` e o Stockfish sao GPL v3. A especificacao aponta o licenciamento
compativel como a opcao de menor atrito.

### Estado dos portoes

A especificacao define `GateResult.passed: bool`, mas tambem exige que
`GATE_STABILITY_001` retorne `indeterminate` quando o estagio de estabilidade
nao rodou e a candidata esta perto de um limiar. Um booleano nao expressa isso.

## Decisao

**Licenca:** o projeto adota GNU GPL v3 ou posterior. `LICENSE` traz o aviso de
copyright e a escolha de licenca; o texto integral da GPL ainda **nao** foi
anexado e isso esta marcado como pendencia dentro do proprio arquivo, a ser
resolvido antes de qualquer distribuicao. `THIRD_PARTY_NOTICES.md` registra as
dependencias e suas licencas. Isto nao substitui analise juridica.

**Estado dos portoes:** `GateResult` carrega `status: GateStatus`
(`passed` / `failed` / `indeterminate`) e expoe `passed` como propriedade
derivada de `status is PASSED`. O contrato da especificacao continua valido: quem
le `result.passed` recebe um booleano, e `indeterminate` nunca aprova.

## Alternativas consideradas

- **Licenca permissiva (MIT).** Rejeitado: incompativel com a redistribuicao de
  codigo derivado de dependencias GPL.
- **Copiar o texto da GPL automaticamente durante o scaffold.** Nao feito:
  baixar arquivos e uma decisao da pessoa que mantem o projeto, nao do agente.
- **Representar indeterminado como `passed = False`.** Rejeitado: confundiria
  "reprovado" com "sem evidencia", exatamente a distincao que a especificacao
  exige preservar.

## Consequencias

- Distribuir o projeto exige anexar o texto completo da GPL v3.
- Relatorios podem distinguir tres estados por portao, e a CLI precisa mostrar
  `indeterminate` de forma visivel.
