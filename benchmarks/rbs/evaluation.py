"""Join independently supplied predictions without model imports or fitted scales."""

from benchmarks.rbs.metrics import cluster_mae_interval, summary


def evaluate(records, predictions, reference_id=None):
    """Count absent predictions as failures and optionally normalize by one control.

    A failed/missing normalization control makes relative evaluation undefined.
    Unknown or duplicate prediction IDs fail closed rather than changing the set.
    """
    observed = {row["id"]: row for row in records}
    predicted = {row["id"]: row for row in predictions}
    if len(observed) != len(records) or len(predicted) != len(predictions):
        raise ValueError("Duplicate evaluation IDs")
    if set(predicted) - set(observed):
        raise ValueError("Prediction IDs outside the frozen dataset")
    excluded = []
    for key, row in observed.items():
        status = row.get("measurement_status", "available")
        if status not in {"available", "not_measured"}:
            raise ValueError("Unknown measurement eligibility status")
        if status == "not_measured":
            if row["observed"] not in (None, "N/A"):
                raise ValueError("Cannot exclude an available measurement")
            excluded.append(key)
    pairs = [{"id": key, "observed": row["observed"], "group": row["family"],
              "status": predicted.get(key, {}).get("status", "not_evaluated"),
              "predicted": predicted.get(key, {}).get("predicted")}
             for key, row in observed.items() if key not in excluded]
    summary(pairs)  # Validate positive scales before dividing anything.
    if reference_id is not None:
        control = next((row for row in pairs if row["id"] == reference_id), None)
        if control is None or control["status"] != "ok":
            raise ValueError("A successful predeclared normalization control is required")
        observed_scale, predicted_scale = control["observed"], control["predicted"]
        for row in pairs:
            row["observed"] /= observed_scale
            if row["status"] == "ok":
                row["predicted"] /= predicted_scale
    result = {"n_constructs": len(records), "n_measurement_eligible": len(pairs),
              "exclusions": {"source_not_measured": excluded},
              "normalization_reference": reference_id, "metrics": summary(pairs),
              "family_bootstrap_mae_log2_95": cluster_mae_interval(pairs)}
    if reference_id is not None:
        baseline = [{**row, "predicted": 1.0, "status": "ok"} for row in pairs]
        result["constant_relative_rate_baseline"] = summary(baseline)
    return result
