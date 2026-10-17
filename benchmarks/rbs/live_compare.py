"""Reuse pinned private exports for uncalibrated development compatibility tests."""

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.live import validate_export
from benchmarks.rbs.metrics import summary
from benchmarks.rbs.positional_adapters import unique


def references(panel_bytes, acquisition, private_root):
    """Verify all recorded artifact bytes without consulting private job IDs."""
    if digest(panel_bytes) != acquisition["panel_sha256"]:
        raise ValueError("Live panel hash mismatch")
    panel = unique(json.loads(panel_bytes)["records"])
    jobs = unique(acquisition["jobs"])
    if set(panel) != set(jobs):
        raise ValueError("Live acquisition identity set mismatch")
    result = []
    root = Path(private_root).resolve()
    for identity, job in jobs.items():
        case = panel[identity]
        if digest(case["sequence"]) != job["input_sha256"]:
            raise ValueError("Acquired input differs from frozen sequence")
        rates = {}
        csv_count = 0
        for artifact in job["exports"]:
            path = (root / artifact["file"]).resolve()
            if root not in path.parents:
                raise ValueError("Private export path escapes its directory")
            raw = path.read_bytes()
            if len(raw) != artifact["bytes"] or digest(raw) != artifact["sha256"]:
                raise ValueError("Private live artifact hash/length mismatch")
            if path.suffix == ".csv":
                csv_count += 1
                validate_export(case, raw.decode())
                rates = {
                    int(row["start_position"]): float(row["tir"])
                    for row in csv.DictReader(io.StringIO(raw.decode()))
                }
        status = job["status"]
        if (
            status not in {"finished_exported", "finished_empty", "form_rejected"}
            or (status == "finished_exported" and (csv_count != 1 or not rates))
            or (status != "finished_exported" and csv_count != 0)
        ):
            raise ValueError("Unresolved or inconsistent live acquisition status")
        result.append({**case, "live_status": status, "live_rates": rates})
    return result


def compare(reference, predictions, settings):
    """Report raw-score agreement, every returned site and explicit empty results.

    This measures compatibility with exposed hosted predictions, not biology.
    Form rejections have no algorithm output and never enter rate denominators.
    """
    source, inferred = unique(reference), unique(predictions)
    if set(inferred) - set(source):
        raise ValueError("Unknown reconstruction diagnostic identity")
    all_rows, targets, counts = [], [], Counter()
    for identity, case in source.items():
        counts[case["live_status"]] += 1
        if case["live_status"] == "form_rejected":
            continue
        result = inferred.get(identity)
        if result is not None:
            request = result["input"]
            if (
                request["oriented_sha256"] != digest(request["oriented_sequence"])
                or request["oriented_sequence"].replace("U", "T") != case["sequence"]
                or request["strand"] != "+"
                or request["anti_sd"] != settings["rrna_displayed"]
                or request["temperature_c"] != settings["temperature_c"]
            ):
                raise ValueError("Reconstruction/live input scenario mismatch")
        sites = [] if result is None else result["sites"]
        site_map = {site["oriented_start"]: site for site in sites}
        if len(site_map) != len(sites):
            raise ValueError("Duplicate reconstruction start")
        live = case["live_rates"]
        successful = {
            start for start, site in site_map.items() if site["status"] == "ok"
        }
        counts["extra_returned_starts"] += len(set(site_map) - set(live))
        counts["returned_start_set_matches"] += result is not None and set(
            site_map
        ) == set(live)
        counts["scored_start_set_matches"] += result is not None and successful == set(
            live
        )
        if case["live_status"] == "finished_empty":
            counts["explicit_empty_agreements"] += (
                result is not None and result["status"] == "no_candidate" and not sites
            )
        for start, value in live.items():
            site = site_map.get(start, {})
            row = {
                "id": identity + ":" + str(start),
                "observed": value,
                "predicted": site.get("tir"),
                "status": site.get("status", "not_evaluated"),
            }
            all_rows.append(row)
            if start == case["selected_start_zero_based"]:
                targets.append(row)
    return {
        "comparison": "reconstruction-versus-live",
        "scope": (
            "exposed development diagnostics; no calibration "
            "and no experimental-accuracy inference"
        ),
        "counts": dict(counts),
        "all_live_candidates": summary(all_rows),
        "declared_targets": summary(targets),
        "uncertainty_limit": (
            "synthetic/shared-family diagnostic cases are not "
            "independent biological samples"
        ),
    }


def main(argv=None):
    """Write aggregate compatibility only; never copy raw service exports."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("panel", "acquisition", "private_exports", "predictions", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    panel, acquisition, predictions = (
        args.panel.read_bytes(),
        args.acquisition.read_bytes(),
        args.predictions.read_bytes(),
    )
    admitted = json.loads(acquisition)
    result = compare(
        references(panel, admitted, args.private_exports),
        json.loads(predictions)["results"],
        admitted["returned_settings"],
    )
    result.update(
        panel_sha256=digest(panel),
        acquisition_sha256=digest(acquisition),
        reconstruction_sha256=digest(predictions),
        evaluator_sha256=digest(Path(__file__).read_bytes()),
    )
    write_json(args.output, result)


if __name__ == "__main__":
    main()
