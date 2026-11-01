# Coupling 0.14rc2 sequence-hash identities

- Purpose: Define both geometry hash payloads for independent saved-result checks.
- Scope: Original 0.14.0rc2, source `ebff076d14789735b56e71501ccfaa5b2b0f82fc`; outcome-free source clarification.
- Last verified: 2026-11-01

The [machine contract](../../models/coupling/0.14.0rc2/geometry-contract.json)
pins the two source files and literal transformations. This supplements the
[envelope identity contract](coupling-identity-0.14rc2.md); it does not replace
its immutable public JSON, change runtime behavior or alter numerical fixtures.
The definition was derived from source syntax without importing or executing
the candidate.

`validate_pair_geometry` in the frozen `src/regsite/coupling_geometry.py` calls
`normalize_rna`, `reverse_complement` and `sequence_hash` from the frozen
`src/regsite/sequence.py`. Normalization is exactly:

```python
normalized = "".join(value.upper().split()).replace("T", "U")
```

Python's no-argument `str.split()` removes whitespace. The caller rejects
non-string input, more than 1,000,000 original characters, empty normalized text,
more than 100,000 normalized bases, or any normalized character outside `ACGU`.
Coordinates count bases in this normalized supplied sequence.

`sequence_sha256` is SHA256 of the normalized RNA encoded as UTF-8 in the
**supplied orientation**, for either strand. It is not a raw-input, DNA or
CDS-subsequence hash. `oriented_sequence_sha256` applies the same hash to the
transcript-oriented RNA: unchanged for `+`; for `-`, replace `ACGU` with `UGCA`
and reverse the entire normalized sequence. The original sequence length is
unchanged by orientation.

Both payloads are sequence bytes only: no header, JSON encoding, length prefix,
NUL or trailing newline. Both digests are lowercase hexadecimal. All accepted
bases are ASCII, so UTF-8 and ASCII encodings give identical bytes on this
accepted domain. A supplied RNA sequence and its DNA spelling therefore have
the same normalized-input digest; raw request identity remains separately bound
by the envelope contract.

These rules apply when valid geometry is returned. A null geometry on a failed
record has no sequence-hash fields and must remain null under the existing
failure contract. Hash agreement establishes sequence identity, not biological
accuracy, complete Operon inference or host calibration.
