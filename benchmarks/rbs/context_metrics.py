"""Summarize paired measured-TSS versus genomic-flank RBS context sensitivity.

Reads one hash-pinned context panel and one hash-pinned collection of the two
unchanged-profile native runs. The report holds aggregate counts and change
distributions only: no per-case scores, residuals or labels. No scoring module
is imported and no prediction is executed.
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from benchmarks.promoter.native_inputs import (
    MAX_ENVELOPE_BYTES,
    checked_hash,
    document_sha256,
    load_envelope,
    read_bounded,
    strict_json,
    write_exclusive,
)
from benchmarks.rbs.context_panel import (
    ANTI_SD,
    MAX_SELECTED_ROWS,
    PROFILES,
    SEED,
    STRATA,
    selection_key,
)
from benchmarks.rbs.datasets import digest

PANEL_SCHEMA = "rbs-context-panel-1"
COLLECTION_SCHEMA = "rbs-context-collection-1"
RESULT_SCHEMA = "native-rbs-result-1"
REPORT_SCHEMA = "rbs-context-metrics-1"
ANCHORS = ("current", "historical")
CONTEXTS = ("measured_tss", "genomic_flank")
STATUSES = ("ok", "no_candidate", "unsupported", "invalid_input", "failed")
NOT_COLLECTED = "not_collected"
MAX_INPUT_SCENARIOS = 4 * MAX_SELECTED_ROWS
MAX_COLLECTION_BYTES = 256 * 1024 * 1024
MAX_SECONDS_PER_RECORD = 120
MAX_SECONDS_PER_BATCH = 3600
MAX_TEXT = 1024
MAX_REASON = 4096
# Bounds every accepted value so differences and interpolation stay finite.
MAX_MAGNITUDE = 1e9
CHANGE_TOLERANCE = 1e-12
QUANTILES = (("q25", 0.25), ("median", 0.5), ("q75", 0.75))
COMMIT = re.compile(r"[0-9a-f]{40}")
COORDINATE_SPACE = "zero-based half-open reference segments in transcript order"
TASK_SCOPE = "supplied start strength"
ENERGY_TERMS = (
    "dG_mRNA",
    "dG_cofold_search",
    "dG_search_with_spacing",
    "dG_complex",
    "dG_spacing",
    "dG_start",
    "dG_standby_signed",
    "dG_accessible_complex",
    "dG_total",
)
TERMS_BY_SCHEMA = {"1.0": ENERGY_TERMS, "1.1": ENERGY_TERMS + ("dG_post_footprint",)}
# rbs-runtime.md: the historical profile emits result 1.0; context2017 emits 1.1.
PROFILE_SCHEMAS = {"historical": "1.0", "context2017": "1.1"}
AUDIT_TERMS = ("dG_mRNA_native_prediction", "dG_cofold_native_prediction")
PANEL_KEYS = (
    "schema_version",
    "source_sha256",
    "tool_sha256",
    "settings",
    "settings_sha256",
    "selected_loci",
    "counts",
    "excluded_without_locus_record_ids",
    "interpretation",
)
LOCUS_KEYS = (
    "stratum",
    "selection_key",
    "genome_id",
    "source_locus_tag",
    "record_ids",
)
COUNT_KEYS = (
    "source_rows",
    "source_gtss_rows",
    "gtss_rows_without_locus",
    "source_loci",
    "loci_by_stratum",
    "selected_loci",
    "selected_source_rows",
    "input_scenarios",
    "profile_jobs",
)
COLLECTION_KEYS = (
    "schema_version",
    "panel_sha256",
    "candidate_commit",
    "settings",
    "runs",
)
EXECUTION_KEYS = (
    "implementation_version",
    "backend",
    "seconds_per_record",
    "seconds_per_batch",
)
RUN_KEYS = ("expected_model_id", "status", "reason", "output")
OUTPUT_KEYS = (
    "schema_version",
    "batch_id",
    "mode",
    "model_id",
    "execution",
    "coordinate_space",
    "task_scope",
    "results",
)
ROW_KEYS = (
    "id",
    "status",
    "reason",
    "context",
    "prediction",
    "genomic_sites",
    "warnings",
    "evidence",
)
CONTEXT_KEYS = (
    "genome",
    "sequence",
    "sequence_sha256",
    "sequence_alphabet",
    "start",
    "path",
    "genomic_segments",
    "genomic_start_segments",
)
GENOME_KEYS = ("accession", "assembly", "annotation", "sequence_sha256", "topology")
UNCOLLECTED_ROW = {"status": NOT_COLLECTED, "reason": None, "context": None}


def _text(value, name, limit=MAX_TEXT):
    if (
        not isinstance(value, str)
        or not 0 < len(value) <= limit
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError(f"Invalid {name}")
    return value


def _exact_keys(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{name} must have exactly the keys {sorted(keys)}")


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _finite(value):
    """A non-boolean JSON number of bounded magnitude."""
    return type(value) in (int, float) and abs(value) <= MAX_MAGNITUDE


def _same_int(value, expected):
    return type(value) is int and value == expected


def panel_settings(per_stratum):
    """The only settings object the declared context-panel builder emits."""
    return {
        "seed": SEED,
        "per_stratum": per_stratum,
        "stratum_priority": list(STRATA),
        "upstream_limit_nt": 100,
        "downstream_length_nt": 100,
        "temperature_c": 37.0,
        "anti_sd": ANTI_SD,
        "profiles": list(PROFILES),
        "maximum_selected_source_rows": MAX_SELECTED_ROWS,
    }


def _scenario_source(record, genomes):
    source = _text(record.get("source_record_id"), "source_record_id", 128)
    anchor = record.get("anchor_scenario")
    context = record.get("transcript_context_scenario")
    if anchor not in ANCHORS or context not in CONTEXTS:
        raise ValueError("Unknown anchor or transcript-context scenario")
    if record["id"] != f"{source}:{anchor}:{context}":
        raise ValueError("Scenario ID differs from its declared identity")
    if not isinstance(genome := record.get("genome_id"), str) or genome not in genomes:
        raise ValueError("Scenario genome is not in the panel")
    if (
        record.get("anti_sd"),
        record.get("temperature_c"),
        record.get("upstream_limit_nt"),
        record.get("downstream_length_nt"),
    ) != (ANTI_SD, 37.0, 100, 100):
        raise ValueError("Scenario settings differ from the panel settings")
    return source


def _reconcile_loci(panel, sources, genomes, per_stratum):
    selected = panel["selected_loci"]
    if not isinstance(selected, list) or not selected:
        raise ValueError("Panel needs selected loci")
    listed, previous, chosen = [], None, dict.fromkeys(STRATA, 0)
    for item in selected:
        _exact_keys(item, LOCUS_KEYS, "selected locus")
        if item["stratum"] not in STRATA:
            raise ValueError("Unknown selected stratum")
        genome = item["genome_id"]
        locus = _text(item["source_locus_tag"], "source_locus_tag", 256)
        if (
            not isinstance(genome, str)
            or genome not in genomes
            or item["selection_key"] != selection_key(genome, locus)
        ):
            raise ValueError("Selected locus identity mismatch")
        order = (STRATA.index(item["stratum"]), item["selection_key"])
        if previous is not None and order <= previous:
            raise ValueError("Selected loci are not in declared order")
        previous = order
        chosen[item["stratum"]] += 1
        ids = item["record_ids"]
        if (
            not isinstance(ids, list)
            or not ids
            or any(not isinstance(identity, str) for identity in ids)
            or ids != sorted(set(ids))
        ):
            raise ValueError("Selected record IDs must be unique, sorted strings")
        for identity in ids:
            if any(
                row.get("genome_id") != genome or row.get("source_locus_tag") != locus
                for row in sources.get(identity, ())
            ):
                raise ValueError("Scenario locus differs from its selected locus")
        listed.extend(ids)
    if len(listed) != len(set(listed)) or set(listed) != set(sources):
        raise ValueError("Selected record IDs differ from panel scenarios")
    counts = panel["counts"]
    _exact_keys(counts, COUNT_KEYS, "panel counts")
    for key in COUNT_KEYS:
        if key != "loci_by_stratum":
            _count(counts[key], key)
    strata = counts["loci_by_stratum"]
    _exact_keys(strata, STRATA, "loci_by_stratum")
    for name in STRATA:
        if chosen[name] != min(per_stratum, _count(strata[name], name)):
            raise ValueError("Selected loci do not reconcile with stratum counts")
    excluded = panel["excluded_without_locus_record_ids"]
    if (
        not isinstance(excluded, list)
        or any(not isinstance(identity, str) for identity in excluded)
        or excluded != sorted(set(excluded))
        or set(excluded) & set(sources)
    ):
        raise ValueError("Invalid excluded record IDs")
    derived = {
        "gtss_rows_without_locus": len(excluded),
        "source_loci": sum(strata.values()),
        "selected_loci": len(selected),
        "selected_source_rows": len(sources),
        "input_scenarios": 4 * len(sources),
        "profile_jobs": 4 * len(sources) * len(PROFILES),
    }
    if (
        any(counts[key] != value for key, value in derived.items())
        or counts["source_gtss_rows"] < len(sources) + len(excluded)
        or counts["source_rows"] < counts["source_gtss_rows"]
    ):
        raise ValueError("Panel counts do not reconcile")


def load_panel(raw, expected_sha256):
    """Verify a context-panel envelope, its identities and its count arithmetic."""
    envelope = load_envelope(raw, expected_sha256)
    panel = envelope.get("panel")
    _exact_keys(panel, PANEL_KEYS, "panel")
    if panel["schema_version"] != PANEL_SCHEMA:
        raise ValueError("Panel schema must be " + PANEL_SCHEMA)
    checked_hash(panel["source_sha256"])
    checked_hash(panel["tool_sha256"])
    settings = panel["settings"]
    per_stratum = settings.get("per_stratum") if isinstance(settings, dict) else None
    if (
        type(per_stratum) is not int
        or not 1 <= per_stratum <= 4
        or settings != panel_settings(per_stratum)
        or panel["settings_sha256"] != document_sha256(settings)
    ):
        raise ValueError("Panel settings differ from the declared context panel")
    _text(panel["interpretation"], "interpretation", 4096)
    records, genomes = envelope["records"], envelope["genomes"]
    if not 4 <= len(records) <= MAX_INPUT_SCENARIOS:
        raise ValueError(f"Panel needs 4..{MAX_INPUT_SCENARIOS} input scenarios")
    sources = {}
    for record in records:
        sources.setdefault(_scenario_source(record, genomes), []).append(record)
    complete = sorted((anchor, context) for anchor in ANCHORS for context in CONTEXTS)
    for rows in sources.values():
        if (
            sorted(
                (row["anchor_scenario"], row["transcript_context_scenario"])
                for row in rows
            )
            != complete
        ):
            raise ValueError("Each source association needs exactly four scenarios")
    _reconcile_loci(panel, sources, genomes, per_stratum)
    return envelope


def _settings(settings):
    _exact_keys(settings, ("mode", "execution"), "settings")
    if settings["mode"] != "supplied_start":
        raise ValueError("Context diagnostics require supplied_start mode")
    execution = settings["execution"]
    _exact_keys(execution, EXECUTION_KEYS, "execution")
    _text(execution["implementation_version"], "implementation_version", 256)
    if not isinstance(execution["backend"], dict) or not execution["backend"]:
        raise ValueError("execution.backend must be a nonempty object")
    for key, limit in (
        ("seconds_per_record", MAX_SECONDS_PER_RECORD),
        ("seconds_per_batch", MAX_SECONDS_PER_BATCH),
    ):
        value = execution[key]
        if type(value) not in (int, float) or not 0 < value <= limit:
            raise ValueError(f"{key} must be a positive number at most {limit}")
    return settings


def _context_key(context, record, genomes, model_id, execution):
    """Prepared-calculation identity: sequence, start, scenario, model, backend."""
    _exact_keys(context, CONTEXT_KEYS, "context")
    sequence = context["sequence"]
    if (
        not isinstance(sequence, str)
        or not sequence
        or set(sequence) - set("ACGU")
        or context["sequence_alphabet"] != "RNA"
        or context["sequence_sha256"] != digest(sequence)
    ):
        raise ValueError("Context RNA sequence or hash is invalid")
    start = context["start"]
    if type(start) is not int or not 0 <= start <= len(sequence) - 3:
        raise ValueError("Context start lies outside its sequence")
    genome = genomes[record["genome_id"]]
    if context["genome"] != {key: genome[key] for key in GENOME_KEYS}:
        raise ValueError("Context genome identity differs from the panel")
    return document_sha256(
        [
            context["sequence_sha256"],
            start,
            record["anti_sd"],
            record["temperature_c"],
            model_id,
            execution,
        ]
    )


def _check_request(request, context, record):
    """A public core request must restate its prepared context and scenario."""
    sequence = request.get("oriented_sequence") if isinstance(request, dict) else None
    positions = request.get("start_positions") if isinstance(request, dict) else None
    temperature = request.get("temperature_c") if isinstance(request, dict) else None
    if (
        context is None
        or not isinstance(sequence, str)
        or sequence.replace("T", "U") != context["sequence"]
        or request.get("oriented_sha256") != digest(sequence)
        or request.get("strand") != "+"
        or not isinstance(positions, list)
        or len(positions) != 1
        or not _same_int(positions[0], context["start"])
        or type(temperature) not in (int, float)
        or temperature != record["temperature_c"]
        or request.get("anti_sd") != record["anti_sd"]
    ):
        raise ValueError("Core request differs from its prepared context or scenario")


def _score(prediction, sites, identity, context, record, run):
    model_id, execution, schema = run
    if not isinstance(prediction, dict):
        raise ValueError("A successful row needs a prediction object")
    if prediction.get("schema_version") != schema:
        raise ValueError(f"This profile's predictions must use result schema {schema}")
    _check_request(prediction.get("input"), context, record)
    model = prediction.get("model")
    start = context["start"]
    if (
        prediction.get("id") != identity
        or prediction.get("status") != "ok"
        or not isinstance(model, dict)
        or model.get("id") != model_id
        or model.get("implementation_version") != execution["implementation_version"]
        or prediction.get("backend") != execution["backend"]
    ):
        raise ValueError("Prediction identity differs from the declared run")
    checked_hash(prediction.get("prediction_id"))
    core = prediction.get("sites")
    if not isinstance(core, list) or len(core) != 1 or len(sites) != 1:
        raise ValueError("A successful supplied-start row needs exactly one site")
    site, genomic = core[0], sites[0]
    if (
        not isinstance(site, dict)
        or not isinstance(genomic, dict)
        or site.get("status") != "ok"
        or genomic.get("status") != "ok"
        or not _same_int(site.get("oriented_start"), start)
        or not _same_int(genomic.get("oriented_start"), start)
    ):
        raise ValueError("Successful site differs from the supplied start")
    energies = site.get("energies")
    terms = TERMS_BY_SCHEMA[schema]
    _exact_keys(energies, terms + AUDIT_TERMS + ("units",), "energies")
    if energies["units"] != "kcal/mol":
        raise ValueError("Energy units must be kcal/mol")
    values = {"log_tir": site.get("log_tir"), **{t: energies[t] for t in terms}}
    if any(not _finite(value) for value in values.values()):
        raise ValueError("Successful site needs finite log_tir and energy terms")
    audit = {term: energies[term] for term in AUDIT_TERMS}
    if any(v is not None and not _finite(v) for v in audit.values()):
        raise ValueError("Native prediction audit energies must be finite or null")
    return values, audit


def _row(row, record, genomes, run):
    model_id, execution, _ = run
    status, reason = row["status"], row["reason"]
    if status not in STATUSES:
        raise ValueError("Unknown result status")
    if reason is not None and (not isinstance(reason, str) or len(reason) > MAX_REASON):
        raise ValueError("Result reason must be bounded text or null")
    if not isinstance(row["warnings"], list) or any(
        not isinstance(value, str) for value in row["warnings"]
    ):
        raise ValueError("Result warnings must be strings")
    if not isinstance(row["genomic_sites"], list):
        raise ValueError("genomic_sites must be an array")
    context = row["context"]
    key = None
    if context is not None:
        key = _context_key(context, record, genomes, model_id, execution)
    parsed = {"status": status, "reason": reason, "context": key}
    prediction = row["prediction"]
    if status != "ok":
        if prediction is not None and (
            not isinstance(prediction, dict) or prediction.get("status") == "ok"
        ):
            raise ValueError("A non-ok row carries a successful or invalid prediction")
        if prediction is not None and prediction.get("input") is not None:
            _check_request(prediction["input"], context, record)
        return parsed
    if context is None:
        raise ValueError("A successful row lacks its prepared context")
    parsed["values"], parsed["audit"] = _score(
        prediction, row["genomic_sites"], row["id"], context, record, run
    )
    return parsed


def _output_rows(output, profile, model_id, settings, panel):
    """Validate one completed native output; return rows and observed schema."""
    _exact_keys(output, OUTPUT_KEYS, "native output")
    if (
        output["schema_version"] != RESULT_SCHEMA
        or output["mode"] != settings["mode"]
        or output["model_id"] != model_id
        or output["execution"] != settings["execution"]
        or output["coordinate_space"] != COORDINATE_SPACE
        or output["task_scope"] != TASK_SCOPE
    ):
        raise ValueError("Native output identity differs from the frozen settings")
    checked_hash(output["batch_id"])
    records = {record["id"]: record for record in panel["records"]}
    results = output["results"]
    if not isinstance(results, list) or len(results) != len(records):
        raise ValueError("Native output must contain every panel scenario")
    rows, run = {}, (model_id, settings["execution"], PROFILE_SCHEMAS[profile])
    for row in results:
        _exact_keys(row, ROW_KEYS, "result row")
        identity = row["id"]
        if not isinstance(identity, str) or identity not in records or identity in rows:
            raise ValueError("Result IDs must cover panel scenarios exactly once")
        if row["evidence"] != records[identity]:
            raise ValueError("Result evidence differs from its panel record")
        rows[identity] = _row(row, records[identity], panel["genomes"], run)
    observed = any(row["status"] == "ok" for row in rows.values())
    return rows, PROFILE_SCHEMAS[profile] if observed else None


def load_collection(raw, expected_sha256, panel, panel_sha256, commit, model_ids):
    """Verify the collection against caller-pinned identities and the panel."""
    if digest(raw) != checked_hash(expected_sha256):
        raise ValueError("Collection file SHA-256 mismatch")
    collection = strict_json(raw)
    _exact_keys(collection, COLLECTION_KEYS, "collection")
    if collection["schema_version"] != COLLECTION_SCHEMA:
        raise ValueError("Collection schema must be " + COLLECTION_SCHEMA)
    if collection["panel_sha256"] != panel_sha256:
        raise ValueError("Collection names a different panel")
    if collection["candidate_commit"] != commit:
        raise ValueError("Collection candidate commit differs from the expected one")
    settings = _settings(collection["settings"])
    runs = collection["runs"]
    _exact_keys(runs, panel["panel"]["settings"]["profiles"], "runs")
    parsed = {}
    for profile in PROFILES:
        run = runs[profile]
        _exact_keys(run, RUN_KEYS, f"{profile} run")
        if run["expected_model_id"] != model_ids[profile]:
            raise ValueError(f"{profile} model ID differs from the expected one")
        if run["status"] == "completed":
            if run["reason"] is not None:
                raise ValueError("A completed run has a null reason")
            parsed[profile] = _output_rows(
                run["output"], profile, model_ids[profile], settings, panel
            )
        elif run["status"] in ("failed", "not_run"):
            _text(run["reason"], f"{profile} run reason")
            if run["output"] is not None:
                raise ValueError("A failed or not_run profile has null output")
        else:
            raise ValueError("Run status must be completed, failed or not_run")
    return collection, parsed


def quantile(ordered, fraction):
    """Linear interpolation at (n-1)*fraction over ascending values."""
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def summary(values):
    """Count, extrema, quartiles and changed count; null statistics when empty."""
    ordered = sorted(values)
    result = {
        "n": len(ordered),
        "changed": sum(abs(value) > CHANGE_TOLERANCE for value in ordered),
    }
    if not ordered:
        return {
            **result,
            "min": None,
            "q25": None,
            "median": None,
            "q75": None,
            "max": None,
        }
    return {
        **result,
        "min": ordered[0],
        **{name: quantile(ordered, fraction) for name, fraction in QUANTILES},
        "max": ordered[-1],
    }


def midranks(values):
    """Rank 1 is the highest value; exact ties share their mean position."""
    order = sorted(range(len(values)), key=lambda index: -values[index])
    ranks = [0.0] * len(values)
    first = 0
    while first < len(order):
        last = first
        while last + 1 < len(order) and values[order[last + 1]] == values[order[first]]:
            last += 1
        for index in order[first : last + 1]:
            ranks[index] = (first + last) / 2 + 1
        first = last + 1
    return ranks


def _coverage(rows):
    statuses = {
        status: {"rows": 0, "with_prepared_context": 0}
        for status in STATUSES + (NOT_COLLECTED,)
    }
    reasons = Counter()
    for row in rows:
        statuses[row["status"]]["rows"] += 1
        statuses[row["status"]]["with_prepared_context"] += row["context"] is not None
        if row["status"] not in ("ok", NOT_COLLECTED):
            reasons[(row["status"], row["reason"] is not None)] += 1
    return {
        "requested": len(rows),
        "statuses": statuses,
        "reasons": [
            {"status": status, "reason_present": present, "count": count}
            for (status, present), count in sorted(reasons.items())
        ],
    }


def _anchor(sources, anchor, rows, terms):
    """Paired summaries within one (profile, anchor); flank is the reference."""
    scenario = {
        context: [rows[f"{source}:{anchor}:{context}"] for source in sources]
        for context in CONTEXTS
    }
    pairs, combinations = [], Counter()
    for measured, flank in zip(*scenario.values(), strict=True):
        combinations[(measured["status"], flank["status"])] += 1
        if measured["status"] == flank["status"] == "ok":
            pairs.append((measured, flank))
    audits = {}
    for term in AUDIT_TERMS:
        finite = [
            measured["audit"][term] - flank["audit"][term]
            for measured, flank in pairs
            if measured["audit"][term] is not None and flank["audit"][term] is not None
        ]
        audits[term] = {"missing_pairs": len(pairs) - len(finite), **summary(finite)}
    measured_ranks = midranks([m["values"]["log_tir"] for m, _ in pairs])
    flank_ranks = midranks([f["values"]["log_tir"] for _, f in pairs])
    return {
        "requested_source_associations": len(sources),
        "coverage": {
            context: _coverage(values) for context, values in scenario.items()
        },
        "pairs": {
            "eligible": len(pairs),
            "ineligible": len(sources) - len(pairs),
            "identical_prepared_context": sum(
                m["context"] == f["context"] for m, f in pairs
            ),
            "status_combinations": [
                {"measured_tss": m, "genomic_flank": f, "count": count}
                for (m, f), count in sorted(combinations.items())
            ],
        },
        "changes": {
            term: summary([m["values"][term] - f["values"][term] for m, f in pairs])
            for term in ("log_tir",) + terms
        },
        "audit_changes": audits,
        "log_tir_rank_changes": summary(
            [m - f for m, f in zip(measured_ranks, flank_ranks, strict=True)]
        ),
    }


def _repeated_contexts(rows):
    keys = Counter(row["context"] for row in rows.values() if row["context"])
    repeated = [count for count in keys.values() if count > 1]
    return {
        "rows_with_prepared_context": sum(keys.values()),
        "distinct_prepared_contexts": len(keys),
        "repeated_prepared_contexts": len(repeated),
        "rows_in_repeated_prepared_contexts": sum(repeated),
    }


def build_report(panel, panel_sha256, collection, collection_sha256, parsed):
    """Aggregate-only report; every requested scenario stays in a denominator."""
    sources = sorted({record["source_record_id"] for record in panel["records"]})
    profiles = {}
    for profile in PROFILES:
        run = collection["runs"][profile]
        rows, version = parsed.get(
            profile, ({r["id"]: UNCOLLECTED_ROW for r in panel["records"]}, None)
        )
        terms = TERMS_BY_SCHEMA[PROFILE_SCHEMAS[profile]]
        output = run["output"]
        profiles[profile] = {
            "expected_model_id": run["expected_model_id"],
            "run_status": run["status"],
            "run_reason_present": run["reason"] is not None,
            "output_sha256": None if output is None else document_sha256(output),
            "batch_id": None if output is None else output["batch_id"],
            "expected_prediction_schema_version": PROFILE_SCHEMAS[profile],
            "observed_prediction_schema_version": version,
            "requested_scenarios": len(rows),
            "collected_scenarios": len(rows) if output is not None else 0,
            "repeated_contexts": _repeated_contexts(rows),
            "anchors": {
                anchor: _anchor(sources, anchor, rows, terms) for anchor in ANCHORS
            },
        }
    meta = panel["panel"]
    return {
        "schema_version": REPORT_SCHEMA,
        "tool_sha256": digest(Path(__file__).read_bytes()),
        "panel": {
            "sha256": panel_sha256,
            **{
                key: meta[key]
                for key in (
                    "source_sha256",
                    "tool_sha256",
                    "settings",
                    "settings_sha256",
                    "counts",
                )
            },
        },
        "collection": {
            "sha256": collection_sha256,
            "candidate_commit": collection["candidate_commit"],
            "candidate_commit_status": (
                "caller assertion; checkout execution is not verifiable here"
            ),
            "settings": collection["settings"],
            "settings_sha256": document_sha256(collection["settings"]),
        },
        "profiles": profiles,
        "definitions": {
            "change": "measured_tss minus genomic_flank per source association",
            "quantiles": "ascending linear interpolation at (n-1)*p; no exclusion",
            "changed": f"count with absolute change > {CHANGE_TOLERANCE}",
            "rank": (
                "higher log_tir first with exact-tie midranks within each fixed "
                "eligible pair set; change is measured rank minus flank rank"
            ),
            NOT_COLLECTED: "requested scenario of a failed or not_run profile",
            "reason_presence": (
                "Only presence counts are emitted; reason text and reason hashes "
                "stay private. Error categories need separately reviewed claims."
            ),
        },
        "interpretation": (
            "Descriptive input sensitivity of unchanged profiles. Source "
            "associations and repeated loci are not independent samples; no "
            "significance, accuracy or translation-improvement claim. Profiles "
            "are not compared on a common scale."
        ),
    }


def summarize(panel_raw, panel_sha256, collection_raw, collection_sha256, commit, ids):
    """Verify both hash-pinned documents and build the aggregate report."""
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError("Candidate commit must be 40 lowercase hex characters")
    for profile in PROFILES:
        _text(ids[profile], f"{profile} model ID", 256)
    if len(set(ids.values())) != len(PROFILES):
        raise ValueError("Profile model IDs must differ")
    panel = load_panel(panel_raw, panel_sha256)
    collection, parsed = load_collection(
        collection_raw, collection_sha256, panel, panel_sha256, commit, ids
    )
    return build_report(panel, panel_sha256, collection, collection_sha256, parsed)


def main(argv=None):
    """Write an exclusive 0600 aggregate report; exit 1 on any rejected input."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", type=Path)
    parser.add_argument("collection", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--panel-sha256", required=True)
    parser.add_argument("--collection-sha256", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--historical-model-id", required=True)
    parser.add_argument("--context2017-model-id", required=True)
    args = parser.parse_args(argv)
    try:
        report = summarize(
            read_bounded(args.panel, MAX_ENVELOPE_BYTES),
            args.panel_sha256,
            read_bounded(args.collection, MAX_COLLECTION_BYTES),
            args.collection_sha256,
            args.candidate_commit,
            {
                "historical": args.historical_model_id,
                "context2017": args.context2017_model_id,
            },
        )
        write_exclusive(args.output, report, 0o600)
    except (OSError, ValueError, RecursionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output_sha256": document_sha256(report)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
