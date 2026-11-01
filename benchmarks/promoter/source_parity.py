"""Build synthetic both-strand source parity from the independent frozen oracle.

GPL-3.0-or-later; see NOTICE. This module never imports or runs the reconstruction.
"""

import hashlib
import json
import math
from pathlib import Path

from benchmarks.promoter import reference_oracle as oracle

ROOT = Path(__file__).parent
SOURCE_EXECUTION_SHA256 = (
    "a2934ceab65a72e15e6b96cb16fe2ddd0b1ff19fc66c8a471e313594eb739353"
)


def build_records(fixtures, parameters):
    """Return input records and independent numerical/coordinate expectations."""
    records = []
    expected = []
    renames = {"disc": "discriminator", "ITR": "itr"}
    terms = {
        "hex10": "dG_10",
        "hex35": "dG_35",
        "discriminator": "dG_disc",
        "extended10": "dG_ext10",
        "itr": "dG_ITR",
        "up": "dG_UP",
        "spacer": "dG_spacer",
        "total": "dG_total",
        "binding": "dG_bind",
        "source_apparent": "dG_apparent",
    }
    for ci, case in enumerate(fixtures["cases"]):
        seq = case["sequence"]
        t = case["tss"]
        sequence_length = len(seq)
        states = oracle.states(seq, t, parameters, case["organism"])
        frozen = [
            {
                "discriminator": s["discriminator"],
                "spacer": s["spacer"],
                "terms": s["terms"],
                "Tx_rate": s["Tx_rate"],
            }
            for s in states
        ]
        if frozen != case["expected_states"]:
            raise ValueError("Independent source fixture/parameter mismatch")
        winner = oracle.winner(states)
        for strand in ["+", "-"]:
            rid = case["id"] + ("::plus" if strand == "+" else "::minus")
            dna = (
                seq
                if strand == "+"
                else seq.translate(str.maketrans("ACGT", "TGCA"))[::-1]
            )
            f = t if strand == "+" else sequence_length - 1 - t
            sequence_strand = "+" if ci % 2 == 0 else "-"
            circular = ci % 3 != 0
            contig_length = sequence_length + 40
            origin = (
                (contig_length - 13 if sequence_strand == "+" else 12)
                if circular
                else (20 if sequence_strand == "+" else sequence_length + 19)
            )
            projection = {
                "contig": "synthetic:" + rid,
                "contig_length": contig_length,
                "origin": origin,
                "sequence_strand": sequence_strand,
                "topology": "circular" if circular else "linear",
                "origin_crossing": circular,
            }
            profile = "in_vitro" if case["organism"] == "in vitro" else "ecoli_mg1655"
            rec = {
                "id": rid,
                "sequence": dna,
                "calibration": profile,
                "scan": {
                    "mode": "positions",
                    "positions": [{"strand": strand, "tss": f}],
                },
                "projection": projection,
                "output": {"states": "all", "legacy_keys": True, "elements": True},
            }
            records.append(rec)
            direction = 1 if sequence_strand == "+" else -1

            def g(x, origin=origin, direction=direction, contig_length=contig_length):
                return (origin + direction * x) % contig_length

            def runs(points, step=1 if strand == sequence_strand else -1):
                out = []
                for point in points:
                    if out and point == out[-1][-1] + step:
                        out[-1].append(point)
                    else:
                        out.append([point])
                return [[min(run), max(run) + 1] for run in out]

            expstates = []
            for state in states:
                oriented = {renames.get(k, k): v for k, v in state["intervals"].items()}
                windows = {
                    k: (
                        [a, b]
                        if strand == "+"
                        else [sequence_length - b, sequence_length - a]
                    )
                    for k, (a, b) in oriented.items()
                }
                genomic = {
                    k: runs(
                        [
                            g(i)
                            for i in (
                                range(a, b)
                                if strand == "+"
                                else range(b - 1, a - 1, -1)
                            )
                        ]
                    )
                    for k, (a, b) in windows.items()
                }
                row = {
                    "discriminator_length": state["discriminator"],
                    "spacer_length": state["spacer"],
                    "terms": {k: state["terms"][v] for k, v in terms.items()},
                    "log_relative_transcription_score": math.log(42)
                    - state["beta"] * state["terms"]["dG_total"],
                    "relative_transcription_score": state["Tx_rate"],
                    "score_status": "ok",
                    "intervals": windows,
                    "oriented_intervals": oriented,
                    "genomic_intervals": genomic,
                    "selected": state is winner,
                }
                row["terms"]["intercept"] = parameters["intercept"]
                expstates.append(row)
            selected = None
            if winner:
                selected = {
                    k: v
                    for k, v in expstates[states.index(winner)].items()
                    if k != "selected"
                }
                selected["elements"] = {
                    renames.get(k, k): winner["features"][k]
                    for k in ("UP", "hex35", "spacer", "hex10", "disc", "ITR")
                }
            expected.append(
                {
                    "id": rid,
                    "source_case": case["id"],
                    "status": "ok" if states else "no_candidate",
                    "strand": strand,
                    "tss": {"forward_base": f, "oriented_base": t},
                    "legacy_source_key": t if strand == "+" else sequence_length - t,
                    "genomic": {
                        "contig": projection["contig"],
                        "base": g(f),
                        "strand": "+" if strand == sequence_strand else "-",
                        "sequence_strand": sequence_strand,
                    },
                    "context": {
                        "required_upstream": 67,
                        "required_downstream": 19,
                        "available_upstream": t,
                        "available_downstream": sequence_length - 1 - t,
                    },
                    "state_count": len(states),
                    "tie_count": sum(
                        s["terms"]["dG_total"] == winner["terms"]["dG_total"]
                        for s in states
                    )
                    if winner
                    else None,
                    "states": expstates,
                    "selected": selected,
                }
            )
    return records, expected


def build_panel():
    """Return deterministic input/expectation bytes from the fixed source assets."""
    fixtures = json.loads((ROOT / "reference-fixtures.json").read_bytes())
    parameters = json.loads((ROOT / "reference-parameters.json").read_bytes())
    records, expected = build_records(fixtures, parameters)
    request = {"schema_version": "1.0", "defaults": {}, "records": records}
    raw = (
        json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    result = {
        "schema_version": "promoter-source-parity-expectations-1",
        "scope": (
            "Synthetic source-equation/coordinate expectations, frozen without "
            "reconstruction output; no native accuracy evaluation. "
            "IDs/model/batch provenance must additionally bind the final receipt."
        ),
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "fixture_sha256": hashlib.sha256(
            (ROOT / "reference-fixtures.json").read_bytes()
        ).hexdigest(),
        "parameter_sha256": hashlib.sha256(
            (ROOT / "reference-parameters.json").read_bytes()
        ).hexdigest(),
        "source_execution_sha256": SOURCE_EXECUTION_SHA256,
        "tolerance": {"absolute": 1e-12, "relative": 1e-12},
        "n_records": len(expected),
        "n_states": sum(e["state_count"] for e in expected),
        "expectations": expected,
    }
    return raw, (
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
