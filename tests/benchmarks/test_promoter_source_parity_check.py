"""Mutation checks for a synthetic public result, never runtime inference."""

import copy
import hashlib
import json
import unittest
from unittest import mock

from benchmarks.promoter import source_parity_check as c
from tests.benchmarks.test_promoter_runtime_adapter import manifest, public_hash


def encode(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def fixture():
    receipt = manifest(host=None)
    identity = receipt["identity"]["identity_model"]
    params = json.loads(
        (c.source_parity.ROOT / "reference-parameters.json").read_bytes()
    )
    identity.update(
        source_commit=c.SOURCE_COMMIT,
        coefficient_array_sha256=params["array_sha256"]["coefficients"],
        intercept_array_sha256=params["array_sha256"]["intercept"],
    )
    request = json.loads(
        (c.source_parity.ROOT / "source-parity-request.json").read_bytes()
    )
    expected = json.loads(
        (c.source_parity.ROOT / "source-parity-expectations.json").read_bytes()
    )
    records = []
    for req, exp in zip(request["records"], expected["expectations"], strict=True):
        profile = req["calibration"]
        calibration = {
            "profile": profile,
            "K": 42,
            "beta": 1.636217004872062 if profile == "ecoli_mg1655" else 0.81632623,
            "native_host": "Escherichia coli str. K-12 substr. MG1655"
            if profile == "ecoli_mg1655"
            else None,
            "host": None,
            "host_status": "unspecified"
            if profile == "ecoli_mg1655"
            else "in_vitro_reference",
        }
        seqhash = hashlib.sha256(req["sequence"].encode()).hexdigest()
        scope = public_hash(
            {
                "schema_version": "1.0",
                "model": identity,
                "calibration": {"profile": profile, "host": None},
                "normalized_dna_sha256": seqhash,
                "projection": req["projection"],
            }
        )
        prediction = public_hash(
            {"scope_id": scope, "scan": req["scan"], "output": req["output"]}
        )
        sid = f"psite1:{scope[:32]}:{exp['strand']}:{exp['tss']['forward_base']}"
        site = copy.deepcopy(exp)
        for key in ("id", "source_case"):
            del site[key]
        count = site["state_count"]
        site.update(
            site_id=sid,
            reason=None if count else "insufficient_context",
            attempted=True,
            complete_state_set=count == 30,
        )
        for state in site["states"] + ([site["selected"]] if count else []):
            state["state_id"] = (
                f"{sid}:d{state['discriminator_length']}s{state['spacer_length']}"
            )
        records.append(
            {
                "id": req["id"],
                "status": exp["status"],
                "reasons": [] if count else ["insufficient_context"],
                "prediction_id": prediction,
                "input": {
                    "raw_sha256": seqhash,
                    "normalized_dna_sha256": seqhash,
                    "length": len(req["sequence"]),
                    "normalization": "ascii-whitespace-uppercase-u-to-t-1",
                },
                "calibration": calibration,
                "scan": req["scan"],
                "projection": req["projection"],
                "coverage": {
                    "planned_sites": 1,
                    "scored_sites": int(count > 0),
                    "partial_state_sites": int(0 < count < 30),
                    "insufficient_context_sites": int(count == 0),
                    "failed_sites": 0,
                    "unattempted_sites": 0,
                    "complete": True,
                    "complete_context": count == 30,
                    "truncation": None,
                },
                "sites": [site],
                "warnings": [
                    {"code": code, "message": "Synthetic applicability explanation"}
                    for code in (
                        ["host_unspecified"] if profile == "ecoli_mg1655" else []
                    )
                    + ["legacy_key_not_coordinate"]
                ],
                "errors": [],
                "metadata": None,
            }
        )
    settings = receipt["settings"]
    batch_id = public_hash(
        {
            "input": request,
            "model": {
                key: identity[key]
                for key in ("id", "implementation_version", "parameter_json_sha256")
            },
            "limits": settings["runtime_limits"],
            "seconds_per_record": settings["seconds_per_record"],
            "seconds_per_batch": settings["seconds_per_batch"],
            "cli_calibration": None,
            "cli_states": None,
        }
    )
    return receipt, {
        "schema_version": "1.0",
        "model": copy.deepcopy(receipt["identity"]["expected_model"]),
        "batch": {
            "batch_id": batch_id,
            "record_count": 22,
            "status_counts": {"ok": 18, "no_candidate": 4},
            "complete": True,
            "limits": copy.deepcopy(settings["runtime_limits"]),
            "seconds_per_record": settings["seconds_per_record"],
            "seconds_per_batch": settings["seconds_per_batch"],
        },
        "results": records,
    }


class SourceParityCheckTest(unittest.TestCase):
    def test_full_panel_and_small_numerical_tolerance(self):
        receipt, result = fixture()
        raw = encode(result)
        report = c.check(raw, receipt)
        self.assertEqual(
            (
                report["records_passed"],
                report["states_passed"],
                report["no_candidate_records"],
            ),
            (22, 424, 4),
        )
        self.assertEqual(report["result_sha256"], hashlib.sha256(raw).hexdigest())
        result["results"][0]["sites"][0]["selected"]["terms"]["total"] += 1e-13
        c.check(encode(result), receipt)

    def test_altered_geometry_identity_missing_partial_or_failure_never_pass(self):
        receipt, result = fixture()
        mutations = [
            lambda r: r.update(results={}),
            lambda r: r["results"].pop(),
            lambda r: r["results"].reverse(),
            lambda r: r["results"][0].update(status="failed"),
            lambda r: r["results"][0].update(prediction_id="0" * 64),
            lambda r: r["results"][0].update(warnings=[]),
            lambda r: r["results"][0].update(warnings=["legacy_key_not_coordinate"]),
            lambda r: r["results"][0].update(
                warnings=[{"code": "legacy_key_not_coordinate", "message": "x"}]
            ),
            lambda r: r["results"][0]["warnings"][0].update(message=1),
            lambda r: r["results"][0]["warnings"][0].update(message=""),
            lambda r: r["results"][0]["warnings"][0].update(code="host_extrapolation"),
            lambda r: r["results"][0]["warnings"].append(
                r["results"][0]["warnings"][0]
            ),
            lambda r: r["results"][0].update(
                warnings={"legacy_key_not_coordinate": True}
            ),
            lambda r: r["results"][0].update(reasons={}),
            lambda r: r["results"][0].update(reasons=[5]),
            lambda r: r["results"][4].update(reasons=[]),
            lambda r: r["results"][0]["sites"][0].update(tie_count=4),
            lambda r: r["results"][0]["sites"][0].update(attempted=1),
            lambda r: r["results"][0]["sites"][0].update(
                tss={"forward_base": 100.0, "oriented_base": 100}
            ),
            lambda r: r["results"][0]["sites"][0].update(genomic=None),
            lambda r: r["results"][0]["sites"][0].update(states=[]),
            lambda r: r["results"][0]["sites"][0].update(states={}),
            lambda r: r["results"][0]["sites"][0]["states"].reverse(),
            lambda r: r["results"][0]["sites"][0]["states"][0]["terms"].update(total=3),
            lambda r: r["results"][0]["sites"][0]["selected"]["terms"].update(
                total=True
            ),
            lambda r: r["results"][0]["sites"][0]["selected"]["terms"].update(
                total=10**400
            ),
            lambda r: r["results"][0]["coverage"].update(complete=False),
            lambda r: r["model"].update(id="wrong"),
            lambda r: r["batch"].update(batch_id="0" * 64),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                broken = copy.deepcopy(result)
                change(broken)
                with self.assertRaises(ValueError):
                    c.check(encode(broken), receipt)

    def test_receipt_asset_and_raw_byte_boundaries(self):
        receipt, result = fixture()
        for field in ("cli_calibration", "cli_states"):
            bad = copy.deepcopy(receipt)
            bad["settings"][field] = (
                "ecoli_mg1655" if field == "cli_calibration" else "selected"
            )
            with self.assertRaisesRegex(ValueError, "null CLI"):
                c.check(encode(result), bad)
        bad = copy.deepcopy(receipt)
        bad["identity"]["identity_model"]["source_commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source/array"):
            c.check(encode(result), bad)
        with mock.patch.object(c, "REQUEST_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "asset identity"):
                c.check(encode(result), receipt)
        assets = c._assets()
        changed = copy.deepcopy(assets[2])
        changed["parameter_sha256"] = "0" * 64
        with mock.patch.object(c, "_assets", return_value=(*assets[:2], changed)):
            with self.assertRaisesRegex(ValueError, "parameter identity"):
                c.check(encode(result), receipt)
        raw = encode(result)
        with self.assertRaisesRegex(ValueError, "wire result"):
            c.check(
                raw
                + b" " * receipt["settings"]["runtime_limits"]["max_result_json_bytes"],
                receipt,
            )
        # Set a realistic cap above compact but below authoritative; use the
        # untouched receipt/result elsewhere so identity disagreement cannot mask
        # which boundary rejected the input.
        compact = json.dumps(result, separators=(",", ":")).encode()
        bad = copy.deepcopy(receipt)
        bad["settings"]["runtime_limits"]["max_result_json_bytes"] = len(raw) - 1
        with self.assertRaisesRegex(ValueError, "authoritative"):
            c.check(compact, bad)
        # Exact received/authoritative cap is accepted after binding new limits.
        settings = receipt["settings"]
        settings["runtime_limits"]["max_result_json_bytes"] = len(raw)
        result["batch"]["limits"] = copy.deepcopy(settings["runtime_limits"])
        request = json.loads(
            (c.source_parity.ROOT / "source-parity-request.json").read_bytes()
        )
        result["batch"]["batch_id"] = c.adapter.batch_id(
            request, settings, receipt["identity"]
        )
        raw = encode(result)
        # Changing the number of cap digits changes authoritative length. Use an
        # explicit padded wire form to hit equality without changing identities.
        limit = settings["runtime_limits"]["max_result_json_bytes"]
        self.assertLessEqual(len(raw), limit)
        c.check(raw + b" " * (limit - len(raw)), receipt)

        # Bind the exact authoritative byte count too (the cap has the same
        # number of decimal digits, so this reaches a fixed point immediately).
        settings["runtime_limits"]["max_result_json_bytes"] = len(raw)
        result["batch"]["limits"] = copy.deepcopy(settings["runtime_limits"])
        result["batch"]["batch_id"] = c.adapter.batch_id(
            request, settings, receipt["identity"]
        )
        raw = encode(result)
        self.assertEqual(len(raw), settings["runtime_limits"]["max_result_json_bytes"])
        c.check(raw, receipt)
