# Counterexamples for Boolean-network variable elimination

Prepared version 1.0.0. This package has not been released.

Deleting a variable can create a motif-avoidant attractor (MAA), even when the variable lies on no directed cycle. This package contains three counterexamples, a coordinate-transformed copy of one of them, and two published controls, with formulas, fixed expected values, and a Python checker. They provide regression inputs for implementations of asynchronous Boolean-network reduction.

## Run the checks

In a copy of this package, run:

```sh
python3 -I -B check.py
python3 -I -B selftest.py
python3 -I -B check_packet.py
```

The first command prints `PASS: 6 cases` after comparing every case. `--json` prints the full recomputed profiles. `--data DIRECTORY` reads `networks.json` and `expected.json` from another directory. The default is the script's directory, so execution does not depend on the current working directory. The second command runs 16 tests, including another algorithm for the finite dynamics. The third checks the file list, hashes, metadata, and consistency of the recorded claims; it does not rerun an exhaustive search.

Python 3.10 or later and its standard library are sufficient. After obtaining the package, no installation, download, or network access is needed to run these commands. For `check.py`, exit code 0 means all supplied fixtures match; 1 means a result or case set differs; 2 means invalid input or a read error. The checker only reads files and writes to standard output. The self-tests create and remove temporary directories beside the scripts, so their copy must be writable.

The implementation permits at most six variables per input network and 128 tokens per formula. The bundled networks have three to five variables. It enumerates all states and all coordinate subcubes, so it is intended for finite examples. [VERIFICATION-RECORD.md](VERIFICATION-RECORD.md) describes the checks and their limits. [claims.json](claims.json) separates recomputed fixture values from results of earlier computations.

## Included networks

Every table entry is an update function. `!`, `&`, and `|` mean NOT, AND, and OR, with precedence in that order. Parentheses override precedence. The parser also accepts constants `0` and `1`; it does not evaluate Python expressions. Each case declares its variable order and the variable to eliminate in [networks.json](networks.json).

| Case | a | b | c | d | e | Delete |
|---|---|---|---|---|---|---|
| E1 | b | !b & !c | !b & !c | d \| (a & c) | - | a |
| E1-canonical | !d | !b & !d | (a & c) \| (!b & c) | !b & !d | - | a |
| E2 | !c & !d | !d | !a & b | (!c & !d) \| (c & d) | - | a |
| E3 | b | !b & !c | !b & !c | a & c | d \| e | a |
| Pastva-7 | (a & c) \| (!a & !c) | (a & b) \| (!a & !b) | b | - | - | c |
| Pastva-8 | c | (a & !b & !c) \| (a & b & c) | (!a & !b & !c) \| (a & b & c) | - | - | a |

E1-canonical is E1 after a coordinate permutation and complementation: new `(a,b,c,d) = (!old a, old c, !old d, old b)`. It is a representative in the same equivalence class, rather than an additional independent construction. The two Pastva cases reproduce Examples 7 and 8 of the paper cited below.

## Definitions

A network is `F = (f_0, ..., f_(n-1))` on `{0,1}^n`. An asynchronous transition changes exactly one coordinate `i` when `f_i(x) != x_i`. Stable updates add no self-loops. An attractor is a terminal strongly connected component (SCC); a singleton is a fixed point and a larger component is a complex attractor.

A trap space is a nonempty coordinate subcube, specified by `0`, `1`, or `*` at each coordinate, that is closed under every asynchronous successor. A minimal trap space (MTS) is inclusion-minimal among trap spaces. A complex attractor is an MAA when it is not contained in any MTS. These conventions follow Pastva et al., Section 2.

The eliminated variable `v` must have **no essential self-dependency**: toggling `x_v` never changes `f_v`. Keep the other coordinates in their original order. For a remaining state `y`, insert `x_v = f_v(y)` and define `g_i(y) = f_i(y, x_v := f_v(y))` for each remaining `i`. Independence of `x_v` makes `f_v(y)` unambiguous. Projection `pi` simply drops coordinate `v`.

The checker records two predicates:

- **D1:** the original network has no MAA and the reduced network has at least one.
- **D2:** some reduced MAA is contained in the projection of **no original MAA**: `exists A' in MAA(G): forall A in MAA(F), not (A' <= pi(A))`.

The containment includes equality. D1 implies D2. **D2 is the R020 study's tracking convention**, not a definition attributed to either cited paper. Tonello–Paulevé's Lemma 3.5 says that projection preserves asynchronous trap sets; it motivates using containment without establishing this MAA matching rule. All four counterexample fixtures satisfy D1 as well as D2.

State strings read **left to right in the declared variable order**. Thus `1000` means `a=1,b=c=d=0` for E1. Truth-table integers use index `k = sum(x_i * 2^i)` and output bit `k`; coordinate `a` is bit 0. These strings are not conventional most-significant-bit-first binary encodings. Groups of states and lists of groups are sorted lexicographically in the JSON.

## Conditions refuted by the fixtures

The interaction graph has an edge `j -> i` precisely when some change in coordinate `j` changes `f_i`. Self-loops count as edges and directed cycles. Monotonicity below is per argument across all other assignments: either nondecreasing or nonincreasing is allowed. An independent argument satisfies this condition too.

- **C1 / ACYC:** the deleted variable is on no directed cycle.
- **C2:** `MED and INMON and OUTMON`. MED means no regulator `j` of `v` also regulates any target `i` of `v`, including `j=i`. INMON means `f_v` is unate. OUTMON means every target function is monotone in `x_v`.

C1 and C2 were exploratory safety candidates in R020. They are not theorems stated by the cited authors. `LMON` in the output means every update function is unate; `TNOSELF` means no target of `v` has a self-loop.

| Case | Variables | Edges | C1 | C2 | MAA before → after | D1 | D2 |
|---|---:|---:|---|---|---:|---|---|
| E1 | 4 | 8 | true | true | 0 → 1 | true | true |
| E1-canonical | 4 | 8 | true | true | 0 → 1 | true | true |
| E2 | 4 | 7 | false | true | 0 → 1 | true | true |
| E3 | 5 | 9 | true | true | 0 → 1 | true | true |
| Pastva-7 | 3 | 5 | false | false | 0 → 1 | true | true |
| Pastva-8 | 3 | 7 | false | false | 1 → 0 | false | false |

In E1 the copy `a=b` can retain an earlier value of `b`. One asynchronous path is `0000 -> 0100 -> 1100 -> 1000 -> 1010 -> 1011`. This lets `a & c` set the latch `d` even though `b` and `c` are not simultaneously 1 on their oscillator attractor. Eliminating `a` replaces the latch rule by `d | (b & c)`. The reduced attractor `{000,010,100}` in order `(b,c,d)` then remains at `d=0`, outside the sole MTS `**1`, and is an MAA. The original network's sole attractor is inside `***1`.

E3 moves the latch to `e`, so the immediate target `d` has no self-loop. E2 satisfies C2 with maximum indegree two; eliminating `a` creates a self-loop at `c` and a six-state MAA. The checker tests these concrete networks, including all their states.

## Minimality and evidence

An earlier exhaustive computation and a separate implementation found no C1 or C2 counterexample under D2 on one, two, or three variables. Together with the four-variable examples E1 and E2, these results give **minimum variable count four for each condition**. The count refers to the original network before one variable is eliminated. This package makes no edge-minimality claim and no minimality claim for E3.

The earlier enumeration records are included in [evidence/](evidence/), with their source hashes in [provenance.json](provenance.json). They are saved results, not executable certificates of enumeration coverage. The commands above check six fixtures and the consistency of those records; they do **not** repeat the exhaustive search, independently establish minimality, or classify all counterexamples. The original enumeration programs are not included. Source paths in the provenance file identify internal research records and are not runtime dependencies or public download links.

[expected.json](expected.json) was transformed from the existing R004 oracle, not generated by this checker. It contains the original and reduced truth tables, all transitions, attractors, all trap spaces, MTSs, MAAs, interaction conditions, projected original MAAs, and D1/D2. The checker recomputes these fields from the formulas and requires exact agreement, including the case set and Boolean/integer types.

The algorithms were adapted from the original study's checker: Tarjan SCCs, successor closure of coordinate subcubes, and function substitution. The self-tests additionally compute SCCs by reachability closure and trap spaces by the fixed-coordinate criterion for all twelve original/reduced profiles. They also test damaged expected values and formulas, missing cases, parsing, non-first-coordinate elimination, and the subset direction in D2.

The earlier independent implementation was written without reading the original computation code or its individual attractor outputs. Its verifier did see the aggregate `n=3` counts while extracting the definitions, so the numerical results were not blinded. The package author subsequently read both reports. Repackaging and its regression tests add no independent scientific verification. No human expert review or formal proof has been completed.

## Scope

The contribution is a set of specified counterexamples with expected finite dynamics that can be checked locally. The general fact that elimination can create or remove MAAs is already known. Novelty of these selected examples relative to all prior work has not been established.

No new safety-condition theorem, biological behaviour, or general result for networks with `n >= 5` is claimed. E3 is one five-variable example. The post hoc condition called DAGDOWN in R020 requires that neither `v` nor any descendant lies on a directed cycle. It is close to the established preprocessing idea of repeatedly pruning downstream output nodes; the package makes no novelty claim or general theorem for that condition.

## Authorship and licences

Tatsuhiko Takimoto is responsible for this package. Codex and Claude were used for implementation, computation, source checking, and drafting. AI checks are described by what they examined; they are not human peer review.

Code and the CI workflow are under Apache-2.0. Data, computation records, and original text are under CC BY 4.0; see [LICENSE](LICENSE) and the full licence texts. The published controls retain the attribution described in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). [CITATION.cff](CITATION.cff) describes this dataset. Cite the original papers for their examples and results.

## Prior work and acknowledgements

- Samuel Pastva, Kyu Hyong Park, Ondřej Huvar, Jordan C. Rozum, and Réka Albert, *An open problem: Why are motif-avoidant attractors so rare in asynchronous Boolean networks?* (2024), [arXiv:2410.03976v1](https://arxiv.org/abs/2410.03976v1), Sections 2 and 6.1. Their study supplies the MAA context and already shows both creation and removal by node deletion. The controls here reproduce their Examples 7 and 8 with lower-case variable names. That source is offered under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Elisa Tonello and Loïc Paulevé, *Phenotype control and elimination of variables in Boolean networks* (2024), [arXiv:2406.02304v3](https://arxiv.org/abs/2406.02304v3), Section 3. Their mediator condition and MTS-preservation theorem inform MED; their projection lemma informs the choice of a containment test. Theorem 3.3 preserves MTSs under MED. It does not assert that C2 prevents MAAs, so E2 does not contradict it.

We thank these authors for the questions, examples, and reduction results that made this work possible, and hope that these checkable fixtures add something useful to that line of research.
