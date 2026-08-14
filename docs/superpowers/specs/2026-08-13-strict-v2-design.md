# `strict_v2` exchange-aware classifier

Status: design approved in chat on 2026-08-13.

## Goal

Add a separately versioned, deterministic classifier that recognizes genuine
net material concessions without treating equal exchanges as sacrifices. The
classifier remains local, explainable, and compatible with the existing audit
model.

## Compatibility

`strict_v1` remains the historical policy. Its immediate destination/left-
hanging detector, seven gates, thresholds, audit meaning, and PGN records are
not reinterpreted. `normal` continues to ask the selected Stockfish strength to
play normally. `strict_v2` is a new policy and is the laboratory's default
strict policy; it is never inferred from an old `strict_v1` record.

The application resolves a rule set by policy. The existing default container
rule set remains available for old callers, while the container also loads the
shipped `strict_v2` rule set. Custom test configurations continue to work by
falling back to the shipped v2 file when it is not beside the temporary config.

## Exchange evidence boundary

`BoardService` gains a typed exchange-trace operation. The port exposes domain
types only: a candidate move, the before/after `PositionSnapshot`s, and every
deterministically ordered legal capture line on the candidate's target square
up to the configured horizon. The adapter is the only place that traverses a
`python-chess` board. At each ply it considers legal captures on the target
square, so a newly unblocked attacker is included as an x-ray recapture. The
adapter records UCI, SAN, mover color, captured piece and the resulting
snapshot; it never returns a chess-library object.

The pure evaluator consumes those typed traces and the configured material
values. For the mover's point of view it records:

- material balance before the candidate;
- material balance immediately after it;
- material balance after the best defensive acceptance line;
- value captured by the candidate;
- value lost by the mover during the accepted exchange;
- value captured later in the same exchange line;
- net material concession after all relevant captures;
- UCI and SAN sequence, clean-trade flag, obvious-recapture flag, and whether
  the offered material was recovered.

The best acceptance line is selected deterministically as the legal line that
maximizes the defender's material result, then by shortest line and UCI order.
The net concession is never the nominal value of the disappearing piece. Equal
knight/bishop values use the configured 3.2/3.3 values and the configured
equality tolerance, so both directions are approximately equal. Rook and queen
trades use the same rule.

The evaluator classifies recognized evidence as destination offer, left
hanging, exchange sacrifice, declined recapture, clearance/deflection, clean
equal trade, favorable trade, obvious recapture, or temporary/recovered offer.
The classification is a separate typed disposition from the existing
`SacrificeKind`: rejected clean trades still carry full evidence with
`detected=false`, a disposition, and a nullable sacrifice kind. If the caller
does not provide position history, `declined_recapture` is not guessed and the
evidence records that the history-dependent classification was unavailable.
Only a positive net concession above the v2 threshold can feed the sacrifice
gate. Clean, favorable, obvious, and fully recovered exchanges are explicit
negative evidence and are rejected.

## `strict_v2` gates

The existing objective gates keep their identifiers and semantics. v2 adds
`GATE_NON_OBVIOUS_001`, so its mandatory sequence is:

1. legal move;
2. objective quality;
3. genuine net sacrifice;
4. soundness after best defense;
5. acceptable resulting expected points;
6. the prior position was not already trivially won;
7. stability under deeper analysis;
8. non-obviousness.

The non-obviousness stage runs a 5,000-node, MultiPV-5 shallow search and
compares it with the existing deep confirmation budget. The configured gate
passes if at least one condition is true: the confirmed rank improves by the
configured amount, expected points improve by at least 0.03, or the move was
outside the shallow top two and reaches the confirmed top three. It records
shallow/deep rank, shallow/deep expected points, improvement, budgets, and the
exact condition. Missing shallow evidence fails the v2 gate; a score can never
rescue a failed mandatory gate.

The seven-gate `strict_v1` evaluator remains a separate path. v2's additional
gate is not silently appended to historical v1 decisions.

## Audit and API data

`CandidateAudit` and its wire representation carry the exchange evidence,
non-obviousness evidence, detector version, engine identity including NNUE,
and all node budgets. The exchange object is serialized even when it rejects a
clean trade, so the regression is explainable rather than represented as
absence of evidence. The Portuguese explanation for the supplied regression
contains the equivalent of:

> A sequência é uma troca limpa de material aproximadamente igual e, portanto,
> não satisfaz o portão de sacrifício.

PGN comments retain the existing strict audit fields and add compact exchange
and non-obviousness measurements. Every v2 audit identifies `strict_v2`, the
detector version, engine/NNUE identity, and budgets.

## Failure behavior

Illegal candidates remain domain errors. An unavailable exchange trace or
shallow/deep measurement is represented as indeterminate evidence and cannot
make a candidate selectable. Terminal positions retain the existing board-rule
handling. A malformed FEN or PGN continues to produce an explicit domain error.

## Tests

Unit tests cover the supplied `Bxc6+ bxc6` regression, configured equal
minor-piece/rook/queen trades, capture-plus-recapture, x-ray recaptures, a
rook-for-minor exchange sacrifice, a compensated piece sacrifice, unsound
sacrifices, obvious recaptures, shallow-obvious and deep-surprise moves, and
the mandatory-gate/score invariant. Adapter contract tests verify no
`python-chess` type crosses the port. API and PGN tests verify the complete
provenance payload. All engine fixtures use fixed node budgets.
