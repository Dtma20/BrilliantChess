# Unpredictable opening exploration for the laboratory

Status: design approved in chat on 2026-08-13.

## Goal

Make local engine-vs-engine laboratory games explore varied, playable opening
positions while retaining deterministic replay, explicit quality limits, and
the existing audit/fair-play boundaries.

## Match contract

`OpeningMode` has `off`, `controlled`, `exploratory`, and `chaotic`. The
laboratory default is `exploratory`; omitted opening input remains backward
compatible by applying that default. The request accepts an optional integer
seed. The response exposes the resolved mode, generated/preserved seed,
selected ECO/opening/variation, current phase, exit reason, planned exit ply,
and dataset version. The API schema increments because the match contract
changes.

`MatchState` stores the immutable opening configuration, seed, selected opening
identity, opening phase state, opening audits, and session replay metadata. The
state remains in memory and the server remains loopback-only.

## Offline dataset

Add a small text-based `data/openings/suite_v1.yaml` resource. Each line has a
stable id, family, ECO, opening name, optional variation, weight, and legal UCI
sequence from the standard starting position. The suite covers 1.e4, 1.d4,
1.c4, 1.Nf3, flank lines, and gambits. The move sequences and weights are
authored for this project from ordinary chess knowledge; ECO labels and opening
names are descriptive metadata, not copied code or a copied opening book. A
nearby attribution/license document records that provenance under the
repository's GPLv3-compatible terms. No network access, Polyglot binary,
engine binary, or unlicensed repository code is added.

## Selection algorithm

The application receives an injected random source. At the HTTP boundary,
missing seeds are generated with `secrets`; all subsequent choices use
`random.Random(seed)` and fixed ordering. The selector chooses a family and
line using weighted sampling, applies a session novelty penalty to lines used
by earlier generated matches, and chooses a seeded exit ply in the configured
full-move range. A supplied seed is treated as an explicit replay request: it
does not consume a new entropy value and its choices are reproducible from the
seed, configuration, and dataset version. Generated seeds use the live session
novelty weights; the selected line and all move choices are stored in the
match/PGN so a prior game is still reproducible after a restart.

The selected line is validated against the supplied initial FEN before use.
An incompatible line is skipped in deterministic order. If no line is
compatible, opening exploration is disabled for that match with an explicit
exit reason and the normal policy takes control.

After the selected exit, the exploratory modes may run two to four additional
plies. Each position gets a cheap node-budgeted MultiPV search. Candidates
whose expected-points loss exceeds the mode cutoff are removed; the remaining
candidates are sampled with a configured temperature. An empty filtered set,
an engine failure, or a terminal board ends the opening phase safely and hands
control back to the side's configured policy. The mode limits, search budget,
temperature, exit range, MultiPV, and extra plies live in validated config.

## Move audit

`SelectionKind.OPENING_EXPLORATION` is distinct from every engine policy result
and is never labelled brilliant, near-brilliant, fallback, or normal. Each
opening audit records mode, seed, ECO/name/variation, source (`suite` or
`multipv_sampling`), opening ply and planned exit ply, candidate rank, EP loss,
sampling weight/mode, candidates considered, cutoff, and node budget. Once the
phase ends, the selected `normal`, `strict_v1`, or `strict_v2` policy uses its
unchanged thresholds.

## API, PGN, and UI

The match request gains:

```json
{
  "opening": {"mode": "exploratory", "seed": null}
}
```

The PGN adds `RuleSetWhite`, `RuleSetBlack`, `OpeningMode`, `OpeningSeed`,
`ECO`, `Opening`, `Variation`, `OpeningExitPly`, and
`OpeningDatasetVersion`. Opening comments include source, rank, EP loss, and
sampling mode; existing strict comments remain unchanged.

The Mesa section gains an “Opening variety” selector with Off, Controlled,
Exploratory, and Chaotic, defaulting to Exploratory. It displays the seed,
opening identity, active phase/exit reason, and a separate opening mark in the
move list and legend. Restart clears the old match and creates a fresh seed.
The existing full-width primary button and four-button secondary row are
preserved; no command button is added.

## Safety and failure behavior

Only legal moves are recorded. Terminal positions stop exploration immediately.
The absence of a compatible dataset line never aborts the duel. No server
worker or external integration is introduced. Randomness is local, injectable,
and never based on timing.

## Tests

Deterministic tests prove same-seed replay, multiple sequences for a fixed set
of different seeds, legal selection, EP cutoff enforcement, empty candidate
handling, terminal stopping, handoff to the configured policy, non-brilliant
opening labels, fresh generated restart seeds, supplied-seed preservation,
typed/versioned API serialization, and PGN reproduction metadata. Frontend
tests cover the selector, opening status, distinct legend mark, and preserved
button layout. No test depends on uncontrolled entropy or timing.
