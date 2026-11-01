"""Freeze outcome-blind RBS inputs, then extract source outcomes privately.

Uses only the standard library. No runtime model imports, calibration, outcome
selection, or inference. Source values and missingness are never repaired.
"""

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import os
import statistics
import zipfile
from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
from pathlib import Path

from benchmarks.rbs.datasets import digest, dna

MEAN_TOLERANCE = {"Cambray2018": 1e-6, "Kuo2020": 0.001}


def checked(root, asset):
    """Verify the complete source before parsing; stream large archive hashes."""
    path = root / asset["path"]
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != asset["sha256"]:
        raise ValueError(f"source hash mismatch: {asset['path']}")
    return path


@contextmanager
def cambray_rows(path, member):
    """Read one named archive member; never extract paths from the archive."""
    with ExitStack() as stack:
        archive = stack.enter_context(zipfile.ZipFile(path))
        raw = stack.enter_context(archive.open(member))
        text = stack.enter_context(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
        yield csv.DictReader(text)


def cambray_input(row, spec):
    """Read input fields only; design replicate is not a measurement replicate."""
    variable = dna(row["gs.sequence"])
    identity, seed, combi, replicate = (row[k] for k in ("", "seed", "combi", "rep"))
    if (
        len(variable) != spec["variable_length"]
        or not seed.isdigit()
        or not combi
        or replicate not in {"1", "2", "3"}
        or identity != f"{seed}_{combi}_{replicate}"
    ):
        raise ValueError("invalid Cambray design identity/sequence")
    sequence = dna(spec["prefix"]) + variable
    start = spec["start"]
    if sequence[start : start + 3] != "ATG" or start + 3 != len(spec["prefix"]):
        raise ValueError("Cambray prefix/start contract")
    return {
        "id": "cambray2018:" + identity,
        "study": "Cambray2018",
        "source_id": identity,
        "group": "cambray2018:" + seed,
        "design_family": seed + ":" + combi,
        "design_replicate": replicate,
        "sequence": sequence,
        "sequence_sha256": digest(sequence),
        "start": start,
        "partition": spec["partition"],
    }


def select_cambray(rows, spec, seed):
    """Hash-rank combinatorial families within each seed; include all members."""
    groups = defaultdict(lambda: defaultdict(list))
    identities, sequences = set(), set()
    for row in rows:
        record = cambray_input(row, spec)
        if record["id"] in identities or record["sequence_sha256"] in sequences:
            raise ValueError("duplicate Cambray identity or sequence")
        identities.add(record["id"])
        sequences.add(record["sequence_sha256"])
        groups[record["group"]][record["design_family"]].append(record)
    if len(identities) != spec["rows"]:
        raise ValueError("Cambray source universe size changed")
    selected = []
    for families in groups.values():
        order = sorted(families, key=lambda key: (digest(seed + ":" + key), key))
        for family in order[: spec["families_per_seed"]]:
            selected.extend(families[family])
    return sorted(selected, key=lambda r: r["id"]), {
        "rows": len(identities),
        "unique_sequences": len(sequences),
        "seeds": len(groups),
        "universe_id_sha256": digest("\n".join(sorted(identities))),
        "universe_sequence_sha256": digest("\n".join(sorted(sequences))),
    }


def select_kuo(spec, seed):
    """Choose generated 9-mers by GC stratum before reading outcome tables."""
    groups = defaultdict(list)
    for bases in itertools.product("ACGT", repeat=9):
        sequence = "".join(bases)
        groups[sum(base in "GC" for base in sequence)].append(sequence)
    selected = {base * 9 for base in "ACGT"}
    selected.update(context["parent"] for context in spec["contexts"].values())
    for sequences in groups.values():
        selected.update(
            sorted(sequences, key=lambda s: (digest(seed + ":kuo:" + s), s))[
                : spec["genotypes_per_gc_count"]
            ]
        )
    if digest(spec["cds_prefix"]) != spec["cds_prefix_sha256"]:
        raise ValueError("Kuo coding-prefix hash changed")
    records = []
    for context, settings in sorted(spec["contexts"].items()):
        for genotype in sorted(selected):
            leader = dna(settings["prefix"] + genotype + settings["suffix"])
            sequence = leader + dna(spec["cds_prefix"])
            if len(leader) != spec["start"] or sequence[30:33] != "ATG":
                raise ValueError("Kuo leader/start contract")
            records.append(
                {
                    "id": "kuo2020:" + context + ":" + genotype,
                    "study": "Kuo2020",
                    "context": context,
                    "genotype": genotype,
                    "group": "kuo2020:complete-nine-mer-family",
                    "sequence": sequence,
                    "sequence_sha256": digest(sequence),
                    "start": spec["start"],
                    "partition": spec["partition"],
                }
            )
    return records


def freeze(root, manifest):
    """Produce input-only records; source outcomes cannot affect selection."""
    spec = manifest["cambray2018"]
    with cambray_rows(checked(root, spec), spec["member"]) as rows:
        records, audit = select_cambray(rows, spec, manifest["selection_seed"])
    records.extend(select_kuo(manifest["kuo2020"], manifest["selection_seed"]))
    return {
        "schema_version": "rbs-new-inputs-1",
        "manifest_sha256": digest(json.dumps(manifest, sort_keys=True)),
        "selection_seed": manifest["selection_seed"],
        "selection_uses_outcomes": False,
        "cambray_universe": audit,
        "partition_counts": dict(Counter(r["partition"] for r in records)),
        "records": records,
    }


def public_split(frozen):
    """Publish identities, groups and hashes without source sequences or labels."""
    fields = (
        "id",
        "study",
        "group",
        "design_family",
        "partition",
        "sequence_sha256",
        "start",
    )
    return {
        "schema_version": "rbs-new-split-1",
        "input_envelope_sha256": digest(json.dumps(frozen, sort_keys=True)),
        "manifest_sha256": frozen["manifest_sha256"],
        "selection_seed": frozen["selection_seed"],
        "selection_uses_outcomes": False,
        "cambray_universe": frozen["cambray_universe"],
        "partition_counts": frozen["partition_counts"],
        "records": [
            {key: row[key] for key in fields if key in row} for row in frozen["records"]
        ],
    }


def measurement(text):
    """Keep absent values explicit and reject silent nonnumeric/nonfinite cells."""
    if text in ("", "NA"):
        return None
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("nonfinite source measurement")
    return value


def edit_distance(left, right):
    """Exact unit-cost Levenshtein distance with bit-vector dynamic programming.

    Implements the recurrence of Myers (1999), doi:10.1145/316542.316550.
    Exhaustive short-string tests compare an independent matrix recurrence.
    This is sequence overlap arithmetic, not an RNA scoring model.
    """
    if not left:
        return len(right)
    masks = defaultdict(int)
    for index, base in enumerate(left):
        masks[base] |= 1 << index
    positive, negative, distance = (1 << len(left)) - 1, 0, len(left)
    high = 1 << (len(left) - 1)
    for base in right:
        equal = masks[base]
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        plus = negative | ~(horizontal | positive)
        minus = positive & horizontal
        distance += bool(plus & high) - bool(minus & high)
        plus, minus = (plus << 1) | 1, minus << 1
        positive, negative = minus | ~(vertical | plus), plus & vertical
    return distance


def overlap(records, previous):
    """Compare matched available windows, avoiding false separation by truncation.

    Each pair uses the common available portion of [-35,+70). Kuo's shorter
    recovered context therefore uses [-30,+43) on BOTH sequences. These are
    sequence-proxy flags, not claims of independent homologous families.
    """
    hits = []
    for new in records:
        for old in previous:
            before = min(35, new["start"], old["start"])
            after = min(
                70,
                len(new["sequence"]) - new["start"],
                len(old["sequence"]) - old["start"],
            )
            if before < 1 or after < 3:
                raise ValueError("overlap requires usable flanks and start context")
            left = new["sequence"][new["start"] - before : new["start"] + after]
            right = old["sequence"][old["start"] - before : old["start"] + after]
            distance = edit_distance(left, right)
            # Integer comparison fixes the threshold exactly at similarity>=0.85.
            if 20 * distance <= 3 * len(left):
                hits.append(
                    {
                        "new_id": new["id"],
                        "previous_id": old["id"],
                        "window": [-before, after],
                        "edit_distance": distance,
                        "length": len(left),
                    }
                )
    return hits


def previous_inputs(root, asset):
    """Normalize a pinned input envelope using an explicit source field map."""
    envelope = json.loads(checked(root, asset).read_text())
    rows = envelope if asset["records_key"] is None else envelope[asset["records_key"]]
    result, missing = [], 0
    for row in rows:
        if not row["sequence"]:
            missing += 1
            continue
        sequence = dna(row["sequence"])
        start = (
            asset["start_value"]
            if asset["start_field"] is None
            else row[asset["start_field"]]
        )
        if isinstance(start, list):
            if len(start) != 1:
                raise ValueError("prior site requires one designated start")
            start = start[0]
        if type(start) is not int or not 0 < start <= len(sequence) - 3:
            raise ValueError("invalid prior site coordinate")
        result.append({"id": row["id"], "sequence": sequence, "start": start})
    if len({r["id"] for r in result}) != len(result):
        raise ValueError("duplicate prior input identity")
    return result, {
        "source_rows": len(rows),
        "usable_rows": len(result),
        "missing_sequence": missing,
    }


def kuo_outcomes(rows, spec):
    """Validate the full source universe, means and replicate missingness."""
    preamble = [next(rows) for _ in range(5)]
    if preamble[3] != ["Genotype", "Fitness (Log(GFP))", "", "", "Mean Fitness"]:
        raise ValueError("Kuo header changed")
    seen = set()
    for row in rows:
        if len(row) != 5 or len(row[0]) != 9 or set(row[0]) - set("ACGU"):
            raise ValueError("Kuo genotype/columns changed")
        genotype = dna(row[0])
        if genotype in seen:
            raise ValueError("duplicate Kuo genotype")
        seen.add(genotype)
        values = [measurement(text) for text in row[1:]]
        available = [v for v in values[:3] if v is not None]
        if (values[3] is None) != (not available):
            raise ValueError("Kuo mean missingness mismatch")
        if available and abs(statistics.mean(available) - values[3]) > 0.001:
            raise ValueError("Kuo mean exceeds source rounding tolerance")
        yield genotype, values
    if len(seen) != spec["rows_per_context"]:
        raise ValueError("Kuo source universe size changed")


def extract(root, manifest, frozen):
    """Return private selected outcomes and aggregate source completeness only."""
    if frozen != freeze(root, manifest):
        raise ValueError("inputs differ from the frozen outcome-blind selection")
    selected = {row["id"] for row in frozen["records"]}
    outcomes, audit = [], {}
    spec = manifest["cambray2018"]
    coverage = Counter()
    with cambray_rows(checked(root, spec), spec["member"]) as rows:
        for row in rows:
            values = [measurement(row[k]) for k in spec["primary_replicates"]]
            mean = measurement(row[spec["primary_quantity"]])
            coverage[sum(v is not None for v in values)] += 1
            identity = "cambray2018:" + row[""]
            if identity in selected:
                outcomes.append(
                    {
                        "id": identity,
                        "quantity": spec["unit"],
                        "observed": mean,
                        "replicates": values,
                        "facilitated_observed": measurement(
                            row[spec["secondary_quantity"]]
                        ),
                        "source_id": row[""],
                        "source_sha256": spec["sha256"],
                    }
                )
    audit["cambray2018"] = {"source_replicate_coverage": dict(sorted(coverage.items()))}
    spec = manifest["kuo2020"]
    for context, asset in sorted(spec["contexts"].items()):
        coverage = Counter()
        with checked(root, asset).open(newline="") as stream:
            for genotype, values in kuo_outcomes(iter(csv.reader(stream)), spec):
                coverage[sum(v is not None for v in values[:3])] += 1
                identity = "kuo2020:" + context + ":" + genotype
                if identity in selected:
                    outcomes.append(
                        {
                            "id": identity,
                            "quantity": spec["unit"],
                            "observed": values[3],
                            "replicates": values[:3],
                            "log_base": None,
                            "source_sha256": asset["sha256"],
                        }
                    )
        audit["kuo2020:" + context] = {
            "source_replicate_coverage": dict(sorted(coverage.items()))
        }
    if {r["id"] for r in outcomes} != selected or len(outcomes) != len(selected):
        raise ValueError("selected outcome identity set mismatch")
    return sorted(outcomes, key=lambda r: r["id"]), audit


def private_write(directory, outcomes, audit):
    """Refuse existing output; create private files without a permissive window."""
    directory.mkdir(mode=0o700)
    for name, data in (("outcomes.json", outcomes), ("source-audit.json", audit)):
        with os.fdopen(
            os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")


def selected_completeness(outcomes, frozen):
    """Summarize extracted source quality without returning individual outcomes.

    Kuo uses a published-rounding tolerance; Cambray uses an explicit numerical
    check tolerance. Neither tolerance changes observations or panel membership.
    Call with the validated private output of extract().
    """
    index = {row["id"]: row for row in frozen["records"]}
    if len(outcomes) != len(index) or {r["id"] for r in outcomes} != set(index):
        raise ValueError("selected completeness identity mismatch")
    result = defaultdict(Counter)
    for row in outcomes:
        study = index[row["id"]]["study"]
        counts = result[study]
        observed = row["observed"]
        available = [v for v in row["replicates"] if v is not None]
        counts["selected_inputs"] += 1
        counts["observed_mean_present"] += observed is not None
        counts["mean_missing"] += observed is None
        counts["mean_nonpositive"] += observed is not None and observed <= 0
        counts["replicate_count_" + str(len(available))] += 1
        counts["mean_rounding_mismatch"] += bool(
            available
            and observed is not None
            and abs(statistics.mean(available) - observed) > MEAN_TOLERANCE[study]
        )
    return dict(result)


def write_new_outputs(outputs):
    """Reserve every destination exclusively before writing; clean up failures.

    Filesystem exclusivity also detects case/Unicode aliases and dangling
    symlinks that lexical path comparison cannot reliably identify.
    """
    created = []
    try:
        with ExitStack() as stack:
            for path, value in outputs:
                path.parent.mkdir(parents=True, exist_ok=True)
                stream = stack.enter_context(path.open("x", encoding="utf-8"))
                created.append((path, stream, value))
            for _, stream, value in created:
                json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
    except BaseException:
        for path, _, _ in created:
            path.unlink()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "extract"))
    parser.add_argument("source_root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("--private-output", type=Path)
    parser.add_argument("--split-output", type=Path)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    if args.mode == "freeze":
        if (
            args.split_output is not None
            and args.inputs.resolve() == args.split_output.resolve()
        ):
            raise ValueError("input and split output paths must be distinct")
        if args.inputs.exists() or (
            args.split_output is not None and args.split_output.exists()
        ):
            raise FileExistsError("frozen input/split target already exists")
        frozen = freeze(args.source_root, manifest)
        outputs = [(args.inputs, frozen)]
        if args.split_output is not None:
            outputs.append((args.split_output, public_split(frozen)))
        write_new_outputs(outputs)
    else:
        if args.private_output is None:
            raise ValueError("extract requires --private-output")
        outcomes, audit = extract(
            args.source_root, manifest, json.loads(args.inputs.read_text())
        )
        private_write(args.private_output, outcomes, audit)


if __name__ == "__main__":
    main()
