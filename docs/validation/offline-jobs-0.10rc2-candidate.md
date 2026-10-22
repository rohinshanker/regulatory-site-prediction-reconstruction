# Offline jobs 0.10.0rc2 development candidate

- Purpose: Bind the reviewed job runner to a fresh, offline installed package.
- Scope: Supplied calculator jobs and software integrity; no biological accuracy or publication approval.
- Last verified: 2026-10-21

The [package receipt](../../models/integration/0.10.0rc2/package.json) binds source
`51ca353241f97bd106fb3634f7132a171a35e893`. Runner code is byte-identical to the
independently reviewed `136d6ffbcdb741776992a462c6742d892395f063`. This revision
replaces a platform-dependent process-group test; it does not change calculator
equations or job execution. The [RC1 receipt](offline-jobs-0.10-candidate.md)
remains available with its failed Linux test explicitly recorded.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 169,707 | `af1c3966d66e7b460ea8c92eed1411bb20ce1c9089a3853caaba13993884e4bc` |
| Source distribution | 5,137,174 | `7af44b9d9aa09da1c3b0541ecd95f32e2ba47430cf86c0ca687c29748bbb50ef` |

The execution-host archive root is
`/Users/Rohin/.cache/regsite-wave7-integration-20261021/jobs-0.10rc2-installed`.
Preserve `dist/`, `receipt.json` and `installed-byte-check.json` when relocating
these artifacts. All 46 installed runtime files match the recorded source bytes.
Compressed archive reproducibility is not claimed.

Use the [installation procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction)
with this exact source or wheel, and read the
[job contract](offline-calculator-jobs.md). The five fixed job kinds remain RBS,
Promoter, paired RBS, supplied transcript and conditional response. External
artifacts, verified resume and explicit backend identity remain required.
Intrinsic termination is absent from this frozen package.

The exact-source local suite passed 6,342 tests, zero skips and eight warnings,
covering all 16,623 measured statements and 6,282 branches. Ruff, formatting and
mypy passed. The fresh installed package passed 18 checks, including all five
job kinds, unchanged one-attempt resume, corruption refusal/restoration,
reinitiation single/batch, Unicode and invalid-input cases. These are software
checks, not experimental validation.

[CI at the package source](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39696040849)
passed all 6,341 applicable Linux/Python 3.14 tests, with one declared
conditional-backend skip, but failed the 100% coverage gate: two signal-error
handler lines were exercised incidentally on macOS and not Linux. Deterministic
tests now exercise both error cases without changing runtime code. The remaining
matrix and correction are not yet accepted. Main merge, tag/package publication
and consumer admission remain separate gates.
