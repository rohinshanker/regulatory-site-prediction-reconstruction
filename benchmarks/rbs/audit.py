"""Reproduce selected historical metrics from pinned source workbooks.

Never run a reconstruction, fit its parameters, or inspect held-out outcomes here.
The 2020 audit uses the separate flow-seq workbook, not the reserved 2017 study.
"""

import math
import statistics
from collections import Counter, defaultdict

from benchmarks.rbs.datasets import PINS, source_path, standby_records
from benchmarks.rbs.metrics import correlation, summary


def squared_correlation(left, right):
    """Square Pearson r while preserving undefined results."""
    value = correlation(left, right)
    return value * value if value is not None else None


def salis_metrics(rows):
    """Recompute 2009 Figure 2B/2E from fixed labelled source row ranges."""
    result = {}
    for name, header, start, end in [("existing_2B", "Reverse engineered", 18, 46),
                                      ("designed_2E", "Forward engineered", 48, 77)]:
        if not rows[start - 1][0].startswith(header):
            raise ValueError("Unexpected 2009 figure-group schema")
        selected = rows[start:end]
        energy, log_mean = [r[2] for r in selected], [math.log(r[3]) for r in selected]
        result[name] = {"n": len(selected), "source_excel_rows": [start + 1, end],
                        "pearson_r2_energy_vs_ln_fluorescence": squared_correlation(energy, log_mean)}
    return result


def standby_metrics(records):
    """Recompute 2014 all-case and explicitly source-labelled figure subsets."""
    result = {}
    groups = {"all_136": records,
              "figure_2G": [r for r in records if "2-G" in [s.strip() for s in r["figure_labels"].split(",")]],
              "figure_5A": [r for r in records if "5-A" in [s.strip() for s in r["figure_labels"].split(",")]]}
    for name, selected in groups.items():
        result[name] = {
            "n": len(selected),
            "pearson_r2_energy_vs_ln_fluorescence": squared_correlation(
                [r["published_dg_total"] for r in selected], [math.log(r["observed"]) for r in selected]),
            "pearson_r2_standby": squared_correlation(
                [r["published_dg_standby"] for r in selected], [r["apparent_dg_standby"] for r in selected]),
            "standby_mae_kcal_mol": statistics.mean(
                abs(r["published_dg_standby"] - r["apparent_dg_standby"]) for r in selected),
        }
    cvs = [r["observed_sd"] / r["observed"] for r in records]
    result["measurement_noise"] = {"n": len(cvs), "median_cv": statistics.median(cvs),
                                   "max_cv": max(cvs), "n_cv_over_half": sum(v > 0.5 for v in cvs),
                                   "replicate_counts": dict(Counter(r["replicates"] for r in records))}
    return result


def flowseq_metrics(measurements, predictions, statistics_rows):
    """Audit cached v2.1 predictions without rerunning or fitting the original model."""
    prediction_ids = [row[0] for row in predictions[1:]]
    measurement_ids = [row[0] for row in measurements[1:]]
    if (len(prediction_ids) != len(set(prediction_ids))
            or len(measurement_ids) != len(set(measurement_ids))
            or set(prediction_ids) != set(measurement_ids)):
        raise ValueError("Flow-seq IDs must be unique and match exactly")
    predictions = {row[0]: row for row in predictions[1:]}
    groups, source_groups = defaultdict(list), defaultdict(list)
    for row in measurements[1:]:
        prediction = predictions[row[0]]
        groups[row[1]].append({"id": str(row[0]), "observed": row[46],
                               "predicted": prediction[20], "status": "ok",
                               "cached_ratio": prediction[21]})
        source_groups[row[1]].append(row)
    # Exact model title is a machine-readable worksheet section, not a semantic classifier.
    start = next(i for i, row in enumerate(statistics_rows) if row[0] == "RBS Calculator v2.1")
    reported = {row[0].split("+")[0]: row for row in statistics_rows[start + 2:start + 4]}
    result = {}
    for name, rows in sorted(groups.items()):
        metrics = summary(rows)
        errors = [max(row["observed"] / row["predicted"], row["predicted"] / row["observed"]) for row in rows]
        cache_residual = max(abs(row["cached_ratio"] - row["observed"] / row["predicted"]) for row in rows)
        original = reported[name]
        metrics["source_table"] = {
            "pearson_r2": original[1], "labelled_spearman_r2": original[3],
            "outlier_count_used_in_refit": original[6], "slope": original[8], "intercept": original[9],
            "labelled_2fold": original[10], "labelled_5fold": original[11], "labelled_10fold": original[12],
        }
        metrics["reproduced_mislabelled_fractions"] = {
            "below_3fold": sum(e < 3 for e in errors) / len(errors),
            "below_6fold": sum(e < 6 for e in errors) / len(errors),
            "below_20fold": sum(e < 20 for e in errors) / len(errors),
        }
        metrics["max_cached_ratio_residual"] = cache_residual
        original_rows = source_groups[name]
        metrics["sequence_redundancy"] = {
            "unique_full_sequences": len({r[18] for r in original_rows}),
            "unique_rbs_sequences": len({r[11] for r in original_rows}),
            "unique_rbs_ids": len({r[12] for r in original_rows}),
            "unique_promoter_ids": len({r[8] for r in original_rows}),
            "unique_cds_sequences": len({r[16] for r in original_rows}),
        }
        result[name] = metrics
    return result


def audit(source_root):
    """Read validated bytes and produce aggregate reproduction results."""
    import openpyxl
    import xlrd

    workbook = xlrd.open_workbook(source_path(source_root, "salis2009"))
    sheet = workbook.sheet_by_name("Sheet1")
    salis = salis_metrics([sheet.row_values(i) for i in range(sheet.nrows)])
    sheet = xlrd.open_workbook(source_path(source_root, "standby2014")).sheet_by_index(0)
    standby = standby_metrics(standby_records([sheet.row_values(i) for i in range(sheet.nrows)]))
    workbook = openpyxl.load_workbook(source_path(source_root, "mts2020_fs"), read_only=True, data_only=True)
    flowseq = flowseq_metrics(list(workbook["FS"].values), list(workbook["RBS Calculator v2.1"].values),
                             list(workbook["Statistics"].values))
    workbook.close()
    return {"schema_version": 1, "identity": "historical-workbook-audit-v1",
            "comparison": "published_predictions_vs_experiments; never current-live accuracy",
            "source_sha256": {key: PINS[key][1] for key in ("salis2009", "standby2014", "mts2020_fs")},
            "salis2009": salis, "standby2014": standby, "mts2020_flowseq_v21": flowseq}
