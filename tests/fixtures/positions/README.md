# Fixtures golden de posicoes

Cada arquivo `position_XXXX.json` segue o schema da secao 20.5 da especificacao:

```json
{
  "id": "position_0001",
  "fen": "...",
  "candidate_uci": "...",
  "expected": "brilliant|not_brilliant|indeterminate",
  "expected_passed_gates": ["GATE_QUALITY_001"],
  "expected_failed_gates": [],
  "source": "manual|public_example|synthetic",
  "notes": "...",
  "verified_by": ["human", "stockfish_18"],
  "rule_set": "strict_v1"
}
```

Regras:

- nunca altere `expected` apenas porque a implementacao falhou;
- toda mudanca precisa de justificativa no commit e, se mudar regra, uma ADR;
- mantenha negativos dificeis, nao apenas positivos vistosos;
- registre discordancia entre versoes do motor como instabilidade.

O corpus revisado entra na Entrega 8. Ate la o diretorio fica vazio e o teste
golden reporta `skip` em vez de fingir cobertura.
