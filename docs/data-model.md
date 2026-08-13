# Modelo de dados

Persistencia entra na Entrega 7 com SQLite e migrations explicitas. Este
documento fixa o contrato desde agora.

## Tabelas conceituais

| Tabela | Conteudo |
| --- | --- |
| `analyses` | Execucao de analise, estado, orcamento, versao das regras |
| `positions` | FEN normalizada e metadados da posicao |
| `engine_runs` | Identidade do motor, opcoes, nos, NPS, duracao |
| `candidate_evaluations` | Avaliacao por candidata e por estagio |
| `sacrifice_evidence` | Evidencia, sinais, confianca e trajetoria material |
| `gate_results` | Um registro por portao, com valor medido e limiar |
| `game_analyses` | Progresso incremental por partida, permitindo retomada |
| `rule_sets` | Versoes de regra e seus limiares |

## Chave de cache

Definida em `ports/analysis_repository.AnalysisCacheKey`. Inclui:

- FEN normalizada (lado, roques, en passant e contadores relevantes);
- jogadas raiz, em ordem estavel (`root_moves_fingerprint`);
- SHA-256 do executavel do motor;
- versao do motor e identificacao da rede NNUE;
- impressao das opcoes do motor;
- impressao do orcamento;
- MultiPV;
- versao do mapeamento WDL;
- versao das regras.

Consequencia: um resultado raso **nunca** e reutilizado como analise profunda, e
mudar limiares ou o mapeamento de EP invalida o cache automaticamente.

## Estados

`pending`, `running`, `completed`, `failed`, `cancelled`
(`domain.values.AnalysisState`). Falhas guardam erro estruturado e permitem nova
tentativa. Uma analise parcial nunca aparece como final.

## Contrato JSON

`JSON_SCHEMA_VERSION` vive em `interfaces/cli/rendering.py` e comeca em `"1"`.
Todo payload publico carrega `schema_version`. Mudanca incompativel exige
incremento e atualizacao dos testes de snapshot.

## Procedencia

`ports/game_source.Game` carrega `source` e `provenance`. Qualquer importacao
externa futura precisa registrar origem e termos do dado. Importar partidas
nunca dispara analise automaticamente.
