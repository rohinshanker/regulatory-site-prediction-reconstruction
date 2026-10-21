"""Frozen, offline descriptive count association; never imports a predictor.

The CLI always verifies the two immutable repository freezes. Pure functions
accept explicit synthetic settings for portable tests, never as CLI overrides.
Prepared artifacts contain source sequences/context and belong outside the repo.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import random
import re
import stat
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

PROTOCOL_SHA256 = "2aaff3b1c3b22f85590a13c6bf00b6502bb4487b05aa812cff34d6a5acb7e49e"
MANIFEST_SHA256 = "c5e67fc2845db5b45fdb508bd444d6ada13bacfefb5947222ce1e3e165699697"
MAX_BYTES = 67108864
MAX_FASTA = 8000000
CONDITIONS = ("control", "dark", "high_light", "high_temperature")
EXCLUSIONS = (
    "same_locus",
    "overlapping_window",
    "identical_or_reverse_complement_window",
    "sample_limit",
)
STATES = (
    "membership-observed",
    "source-membership-empty",
    "unresolved-source-link",
    "no-source-data",
)
TERMINATORS = (
    "observed",
    "none-in-complete-coverage",
    "coverage-incomplete",
    "not-applicable",
)
COMPLEMENT = str.maketrans("ACGT", "TGCA")
RELEASE = "GCF_000817325.1-RS_2026_05_13"
ASSEMBLY = "GCF_000817325.1"
PREPARED = "promoter-count-association-prepared-1"


def require(condition, message):
    """Fail closed on missing, malformed or contradictory evidence."""
    if not condition:
        raise ValueError(message)


def canonical(value):
    """Deterministic finite JSON, with the frozen encoding and final LF."""
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def digest(raw):
    """SHA-256 of actual bytes (or UTF-8 text)."""
    return hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()


def checked_hash(value):
    """Require the caller to supply an exact lowercase SHA-256."""
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
        "Expected lowercase SHA-256",
    )
    return value


def same(actual, expected, label):
    require(canonical(actual) == canonical(expected), f"{label}: mismatch")


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), "Unexpected keys")


def number(value, positive=False):
    """Accept finite nonnegative counts or strictly positive model rates."""
    require(
        type(value) in (int, float) and math.isfinite(value),
        "Expected finite number, not bool",
    )
    require(value > 0 if positive else value >= 0, "Number out of range")
    return value


def integer(value, minimum=0):
    """Require an integer without accepting bool as a count."""
    require(
        type(value) is int and minimum <= value <= 10**12, "Expected bounded integer"
    )
    return value


def text(value):
    require(isinstance(value, str) and bool(value), "Expected nonempty string")
    return value


def unique_strings(value):
    """Preserve explicit empty arrays while rejecting duplicate memberships."""
    require(
        type(value) is list and all(isinstance(x, str) and x for x in value),
        "Expected string array",
    )
    require(value == sorted(set(value)), "Expected sorted unique strings")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonfinite JSON constant")


def _float(value):
    result = float(value)
    require(math.isfinite(result), "Nonfinite JSON number")
    return result


def parse_json(raw):
    """Reject duplicate keys, nonfinite values, invalid UTF-8 and deep trees."""
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_float,
            parse_constant=_constant,
        )
        stack = [(value, 0)]
        while stack:
            node, depth = stack.pop()
            require(depth <= 64, "JSON exceeds nesting limit")
            if isinstance(node, dict):
                stack.extend((child, depth + 1) for child in node.values())
            elif isinstance(node, list):
                stack.extend((child, depth + 1) for child in node)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(
            "Invalid JSON (duplicate, nonfinite, malformed or deep)"
        ) from exc


def read_bytes(path, limit=MAX_BYTES):
    """Read a bounded regular nonsymlink file; reject special files before open."""
    path = Path(path)
    require(stat.S_ISREG(path.lstat().st_mode), "Expected regular nonsymlink input")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Input exceeds byte limit")
    return raw


def pinned_bytes(path, pin):
    raw = read_bytes(path)
    require(
        len(raw) == pin["bytes"] and digest(raw) == pin["sha256"],
        "Input byte identity mismatch",
    )
    return raw


def publish(path, value):
    """Atomically link a complete sibling temporary file without clobbering."""
    raw = canonical(value)
    path = Path(path)
    stream = tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=".count-association-", delete=False
    )
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink()


def freezes():
    """The production CLI has no pin/settings override or discovery fallback."""
    root = Path(__file__).parent
    protocol_raw = read_bytes(root / "count-association-protocol.json")
    manifest_raw = read_bytes(root / "count-association-inputs.json")
    same(digest(protocol_raw), PROTOCOL_SHA256, "Protocol freeze")
    same(digest(manifest_raw), MANIFEST_SHA256, "Manifest freeze")
    protocol, manifest = parse_json(protocol_raw), parse_json(manifest_raw)
    same(protocol["manifest_sha256"], MANIFEST_SHA256, "Protocol manifest")
    return protocol, manifest


def trust(protocol, manifest):
    """Record bytes read separately from opaque referenced model identities."""
    return {
        "protocol_sha256": digest(canonical(protocol)),
        "manifest_sha256": digest(canonical(manifest)),
        "preparation_verified_input_bytes": manifest["inputs"],
    }


def table(raw, required):
    """Parse a rectangular UTF-8 TSV with distinct required headers."""
    reader = csv.DictReader(
        io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t"
    )
    fields = reader.fieldnames
    require(
        fields and len(set(fields)) == len(fields) and set(required) <= set(fields),
        "Missing or duplicate TSV headers",
    )
    rows = list(reader)
    require(bool(rows), "Empty TSV")
    require(
        all(
            None not in row and all(isinstance(v, str) for v in row.values())
            for row in rows
        ),
        "Malformed TSV row",
    )
    return rows


def fasta(raw, lengths):
    """Bound gzip expansion before decoding, then validate exact native roster."""
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded = stream.read(MAX_FASTA + 1)
    require(len(decoded) <= MAX_FASTA, "Decoded FASTA exceeds limit")
    sequences, accession = {}, None
    for line in decoded.decode("ascii").splitlines():
        if line.startswith(">"):
            accession = line[1:].split()[0]
            require(accession not in sequences, "Duplicate FASTA accession")
            sequences[accession] = ""
        else:
            require(
                accession is not None and line and not set(line) - set("ACGT"),
                "Invalid FASTA sequence",
            )
            sequences[accession] += line
    validate_genomes(sequences, lengths)
    return sequences


def validate_genomes(sequences, lengths):
    """Check the exact frozen replicon roster, lengths and normalized bases."""
    require(type(sequences) is dict, "Invalid genomes")
    same(
        {key: len(text(value)) for key, value in sequences.items()},
        lengths,
        "Replicon lengths",
    )
    require(
        all(not set(seq) - set("ACGT") for seq in sequences.values()),
        "Invalid genome bases",
    )


def release(receipt, pin, kind):
    """Check accepted release receipts without opening any provenance reference."""
    tu = kind == "tu"
    contract = "biocyc-utex-tu-membership-1" if tu else "regulatory-transterm-payload-1"
    schema = (
        "biocyc-utex-tu-membership-release-1"
        if tu
        else "regulatory-transterm-release-1"
    )
    scope = (
        "non-positional-source-membership"
        if tu
        else "native-intrinsic-terminator-coordinate-predictions"
    )
    same(receipt["schema"], schema, "Release schema")
    same(receipt["contract"], contract, "Release contract")
    same(receipt["scope"], scope, "Release scope")
    same(receipt["status"], "accepted-for-runtime-integration", "Release status")
    same(receipt["payload"], pin, "Release payload")
    require(
        re.fullmatch(r"[0-9a-f]{40}", receipt["reviewedImplementation"]),
        "Invalid reviewed commit",
    )
    roles = set()
    for review in receipt["reviews"]:
        text(review["id"])
        same(review["result"], "accepted", "Review result")
        roles.update([review["role"]] if tu else review["coverage"])
    require({"source-contract", "exact-patch"} <= roles, "Missing release review")
    if not tu:
        same(
            receipt["dataset"],
            {
                "annotationReleaseId": RELEASE,
                "assembly": ASSEMBLY,
                "datasetId": "utex2973-transtermhp-retained-pilot-v1",
                "schemaVersion": 1,
            },
            "Terminator release dataset",
        )


def coverage(value):
    """Validate complete, partial and absent coverage against its counts."""
    keys(value, ("status", "coveredNt", "totalNt"))
    total = integer(value["totalNt"], 1)
    covered = integer(value["coveredNt"])
    require(covered <= total, "Coverage exceeds total")
    expected = "complete" if covered == total else "none" if covered == 0 else "partial"
    same(value["status"], expected, "Coverage status")
    return expected


def terminator_state(gene, sites):
    """CDS overlap only; an observed call takes precedence over partial coverage."""
    overlap = gene["cdsOverlap"]
    eligible = gene["biotype"] == "protein_coding" and bool(gene["cdsSegments"])
    if not eligible:
        require(overlap is None, "Ineligible CDS has metrics")
        return "not-applicable"
    require(type(overlap) is dict, "Protein CDS missing overlap")
    state = coverage(overlap["coverage"])
    same_ids = unique_strings(overlap["sameStrandCallIds"])
    opposite_ids = unique_strings(overlap["oppositeStrandCallIds"])
    require(not set(same_ids) & set(opposite_ids), "Call strand lists overlap")
    for identity in same_ids + opposite_ids:
        require(identity in sites, "Unknown native terminator call")
        site = sites[identity]
        same(site["replicon"], gene["replicon"], "Terminator replicon")
        same(
            site["strand"] == gene["strand"],
            identity in same_ids,
            "Terminator strand relation",
        )
    count = len(same_ids) + len(opposite_ids)
    same(overlap["observedSourceCallCount"], count, "Observed calls")
    same(
        overlap["completeSourceCallCount"],
        count if state == "complete" else None,
        "Complete calls",
    )
    return (
        "observed"
        if same_ids
        else "none-in-complete-coverage"
        if state == "complete"
        else "coverage-incomplete"
    )


def input_context(tu, terminators, crosswalk, manifest):
    """Project only relevant admitted context; check all loci, not selected loci."""
    same(tu["schema"], "biocyc-utex-tu-membership-1", "TU schema")
    same(tu["scope"], "non-positional-source-membership", "TU scope")
    same(tu["basis"], "inferred", "TU basis")
    same(tu["localRelease"], RELEASE, "TU annotation release")
    require(manifest["inputs"]["crosswalk"] in tu["inputs"], "TU crosswalk pin")
    for field, expected in (
        ("schemaVersion", 1),
        ("annotationReleaseId", RELEASE),
        ("assembly", ASSEMBLY),
        ("method", "TransTermHP"),
        ("recordOrigin", "computed"),
        ("evidenceBasis", "proxy"),
        ("datasetId", "utex2973-transtermhp-retained-pilot-v1"),
    ):
        same(terminators[field], expected, f"Terminator {field}")
    loci = {}
    sites = {}
    for site in terminators["sites"]:
        identity = text(site["id"])
        require(
            identity.startswith("native:") and identity not in sites,
            "Invalid/duplicate native call",
        )
        require(site["strand"] in ("+", "-"), "Invalid call strand")
        sites[identity] = site
    reverse = defaultdict(list)
    for locus in tu["loci"]:
        identity = text(locus["locusTag"])
        require(identity not in loci, "Duplicate TU locus")
        gene = terminators["genes"][identity]
        same(locus["seqid"], gene["replicon"], "Context replicon")
        same(locus["featureType"], gene["featureType"], "Context feature")
        same(locus["geneBiotype"], gene["biotype"], "Context biotype")
        state, memberships = locus["state"], locus["tuIds"]
        require(state in STATES, "Unknown TU state")
        if state in STATES[:2]:
            unique_strings(memberships)
            same(bool(memberships), state == STATES[0], "TU membership state")
            require(bool(unique_strings(locus["sourceFrames"])), "Missing source frame")
            for identity_tu in memberships:
                reverse[identity_tu].append(identity)
        else:
            require(
                memberships is None and locus["sourceFrames"] == [],
                "Unknown TU membership must remain null",
            )
        loci[identity] = {
            "replicon": gene["replicon"],
            "strand": gene["strand"],
            "tu_state": state,
            "tu_ids": memberships,
            "terminator": terminator_state(gene, sites),
        }
    same(set_as_list(loci), set_as_list(terminators["genes"]), "Context locus roster")
    groups = {}
    for group in tu["groups"]:
        identity = text(group["tuId"])
        require(identity not in groups, "Duplicate TU group")
        groups[identity] = unique_strings(group["linkedLoci"])
    # Groups with only unresolved source members legitimately have no local loci.
    same(
        {k: v for k, v in groups.items() if v},
        {k: sorted(v) for k, v in reverse.items()},
        "TU reverse membership",
    )
    aliases = []
    for row in crosswalk:
        pair = row["relationship"], row["object_namespace"]
        if pair in (
            ("current_locus_tag", "RefSeq_locus_tag"),
            ("old_locus_tag", "legacy_locus_tag"),
        ):
            current = row["subject_locus_tag"]
            require(current in loci, "Crosswalk unknown current locus")
            same(row["seqid"], loci[current]["replicon"], "Crosswalk replicon")
            same(row["strand"], loci[current]["strand"], "Crosswalk strand")
            if pair[0] == "current_locus_tag":
                same(row["object_id"], current, "Current locus identity")
            aliases.append([text(row["object_id"]), current])
    require({a for a, b in aliases if a == b} == set(loci), "Missing current aliases")
    context = {"loci": loci, "aliases": sorted(set(map(tuple, aliases)))}
    context["aliases"] = [list(pair) for pair in context["aliases"]]
    return context


def set_as_list(value):
    return sorted(set(value))


def validate_context(context, lengths):
    """Check the minimal input-only context carried by prepared artifacts."""
    keys(context, ("loci", "aliases"))
    require(type(context["loci"]) is dict and bool(context["loci"]), "Missing context")
    for identity, locus in context["loci"].items():
        text(identity)
        keys(locus, ("replicon", "strand", "tu_state", "tu_ids", "terminator"))
        require(
            locus["replicon"] in lengths and locus["strand"] in ("+", "-"),
            "Invalid context geometry",
        )
        state = locus["tu_state"]
        require(
            state in STATES and locus["terminator"] in TERMINATORS,
            "Unknown context state",
        )
        if state in STATES[:2]:
            same(
                bool(unique_strings(locus["tu_ids"])),
                state == STATES[0],
                "Context TU state",
            )
        else:
            require(locus["tu_ids"] is None, "Unknown membership is not empty")
    aliases = context["aliases"]
    require(type(aliases) is list, "Invalid aliases")
    for pair in aliases:
        require(type(pair) is list and len(pair) == 2, "Invalid alias pair")
        text(pair[0])
        require(pair[1] in context["loci"], "Unknown alias target")
    same(
        aliases,
        sorted([list(pair) for pair in set(map(tuple, aliases))]),
        "Alias order/uniqueness",
    )
    require(
        {a for a, b in aliases if a == b} == set(context["loci"]),
        "Missing native current aliases",
    )


def count_token(token):
    """Parse decimal source counts; only empty and NA represent missingness."""
    require(isinstance(token, str), "Count token must be text")
    if token in ("", "NA"):
        return None
    require(
        re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token),
        "Malformed count",
    )
    return number(float(token))


def source_anchors(rows, lengths, expected):
    """Preserve every source row with unique identity and native coordinate."""
    require(
        type(rows) is list and len(rows) == expected and expected > 0,
        "Source row count mismatch",
    )
    result, ids, coordinates = [], set(), set()
    for row in rows:
        require(
            type(row) is dict and all(isinstance(v, str) for v in row.values()),
            "Malformed source row",
        )
        identity, locus = text(row["tss_id"]), text(row["locus_tag"])
        replicon = f"NZ_{row['replicon']}.1"
        position = int(row["position"])
        strand = row["strand"]
        require(
            row["type"] == "gTSS"
            and strand in ("+", "-")
            and replicon in lengths
            and 1 <= position <= lengths[replicon],
            "Invalid source anchor",
        )
        coordinate = replicon, strand, position
        require(
            identity not in ids and coordinate not in coordinates,
            "Duplicate source identity/coordinate",
        )
        ids.add(identity)
        coordinates.add(coordinate)
        counts = {
            condition: [count_token(row[f"{condition}_{i}"]) for i in (1, 2)]
            for condition in CONDITIONS
        }
        result.append(
            {
                "id": identity,
                "locus": locus,
                "replicon": replicon,
                "strand": strand,
                "position": position,
                "counts": counts,
            }
        )
    return result


def window(anchor, sequence, selection):
    """One-based circular map in transcript order, including the TSS base."""
    upstream, downstream = selection["upstream_nt"], selection["downstream_nt"]
    require(len(sequence) >= upstream + downstream + 1, "Replicon shorter than window")
    direction = 1 if anchor["strand"] == "+" else -1
    positions = [
        (anchor["position"] - 1 + direction * offset) % len(sequence) + 1
        for offset in range(-upstream, downstream + 1)
    ]
    bases = "".join(sequence[p - 1] for p in positions)
    return (bases if direction == 1 else bases.translate(COMPLEMENT)), positions


class Components:
    """Minimal deterministic disjoint sets, including unselected bridging loci."""

    def __init__(self):
        self.parents = {}

    def root(self, item):
        self.parents.setdefault(item, item)
        while self.parents[item] != item:
            item = self.parents[item]
        return item

    def union(self, left, right):
        left, right = self.root(left), self.root(right)
        self.parents[max(left, right)] = min(left, right)


def project_rows(anchors, context):
    """Map exact native aliases and group before any prediction is admitted."""
    components = Components()
    first_tu, alias_targets = {}, defaultdict(set)
    for identity, locus in sorted(context["loci"].items()):
        components.root(f"current:{identity}")
        for tu_id in locus["tu_ids"] or []:
            first = first_tu.setdefault(tu_id, f"current:{identity}")
            components.union(first, f"current:{identity}")
    for alias, current in context["aliases"]:
        alias_targets[alias].add(current)
    result = []
    for anchor in anchors:
        candidates = sorted(alias_targets[anchor["locus"]])
        mapped = None
        if not candidates:
            status = "unmatched"
        elif len(candidates) > 1:
            status = "ambiguous"
        else:
            locus = context["loci"][candidates[0]]
            if (locus["replicon"], locus["strand"]) != (
                anchor["replicon"],
                anchor["strand"],
            ):
                status = "identity_conflict"
            else:
                mapped, status = candidates[0], "unique"
                components.union(f"source:{anchor['locus']}", f"current:{mapped}")
        components.root(f"source:{anchor['locus']}")
        locus = context["loci"][mapped] if mapped else None
        result.append(
            {
                **anchor,
                "mapping_status": status,
                "candidate_loci": candidates,
                "current_locus": mapped,
                "tu_state": locus["tu_state"] if locus else "mapping-unavailable",
                "terminator": locus["terminator"] if locus else "mapping-unavailable",
            }
        )
    for row in result:
        row["group"] = components.root(f"source:{row['locus']}")
    return result


def build_prepared(protocol, manifest, genomes, source_rows, context):
    """Recompute every row, exclusion, group and selected identity from inputs."""
    selection = protocol["selection"]
    validate_genomes(genomes, selection["replicon_lengths"])
    validate_context(context, selection["replicon_lengths"])
    anchors = source_anchors(
        source_rows, selection["replicon_lengths"], selection["source_rows"]
    )
    rows = project_rows(anchors, context)
    order = sorted(rows, key=lambda row: digest(f"{selection['seed']}:{row['id']}"))
    occupied, loci, sequence_keys = defaultdict(set), set(), set()
    selected, excluded = [], Counter()
    for row in order:
        sequence, positions = window(row, genomes[row["replicon"]], selection)
        key = min(sequence, sequence.translate(COMPLEMENT)[::-1])
        if row["locus"] in loci:
            reason = EXCLUSIONS[0]
        elif occupied[row["replicon"]].intersection(positions):
            reason = EXCLUSIONS[1]
        elif key in sequence_keys:
            reason = EXCLUSIONS[2]
        elif len(selected) >= selection["max_sites"]:
            reason = EXCLUSIONS[3]
        else:
            reason = None
            loci.add(row["locus"])
            occupied[row["replicon"]].update(positions)
            sequence_keys.add(key)
            selected.append(row["id"])
        row.update(
            sequence=sequence,
            native_positions=positions,
            sequence_sha256=digest(sequence),
            exclusion=reason,
        )
        if reason is not None:
            excluded[reason] += 1
    groups = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row["id"])
    return {
        "schema": PREPARED,
        "trust": trust(protocol, manifest),
        "genomes": genomes,
        "source_rows": source_rows,
        "context": context,
        "rows": rows,
        "selected_ids": selected,
        "excluded": dict(excluded),
        "groups": {key: sorted(value) for key, value in groups.items()},
    }


def prepare(input_root, protocol, manifest):
    """Read exactly the seven explicit pinned public inputs beneath this root."""
    expected = {
        "crosswalk",
        "fasta",
        "terminators",
        "terminators_release",
        "tss",
        "tu",
        "tu_release",
    }
    keys(manifest["inputs"], expected)
    root = Path(input_root).resolve(strict=True)
    raw = {}
    for name, pin in manifest["inputs"].items():
        relative = Path(pin["path"])
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            "Disallowed manifest path",
        )
        path = root / relative
        require(path.resolve(strict=True).is_relative_to(root), "Input escapes root")
        raw[name] = pinned_bytes(path, pin)
    tu, terminators = parse_json(raw["tu"]), parse_json(raw["terminators"])
    for kind in ("tu", "terminators"):
        receipt = parse_json(raw[f"{kind}_release"])
        release(receipt, manifest["inputs"][kind], kind)
    same(
        terminators["conversion"]["builder"],
        parse_json(raw["terminators_release"])["builder"],
        "Terminator builder",
    )
    same(
        terminators["replicons"].keys()
        == protocol["selection"]["replicon_lengths"].keys(),
        True,
        "Terminator replicon roster",
    )
    for replicon, length in protocol["selection"]["replicon_lengths"].items():
        same(terminators["replicons"][replicon]["length"], length, "Terminator length")
        same(terminators["replicons"][replicon]["circular"], True, "Native circularity")
    genomes = fasta(raw["fasta"], protocol["selection"]["replicon_lengths"])
    fasta_pin = manifest["inputs"]["fasta"]
    same(
        terminators["verifiedInputs"][Path(fasta_pin["path"]).name],
        {"byteSize": fasta_pin["bytes"], "sha256": fasta_pin["sha256"]},
        "Terminator FASTA pin",
    )
    native_runs = [run for run in terminators["runs"] if run["name"] == "native"]
    require(len(native_runs) == 1, "Missing/duplicate native terminator run")
    same(
        native_runs[0]["sequenceSha256ByReplicon"],
        {key: digest(value) for key, value in genomes.items()},
        "Native genome hashes",
    )
    crosswalk = table(
        raw["crosswalk"],
        (
            "subject_locus_tag",
            "relationship",
            "object_namespace",
            "object_id",
            "seqid",
            "strand",
        ),
    )
    rows = table(
        raw["tss"],
        (
            "tss_id",
            "replicon",
            "type",
            "strand",
            "position",
            "locus_tag",
            *(f"{c}_{i}" for c in CONDITIONS for i in (1, 2)),
        ),
    )
    return build_prepared(
        protocol,
        manifest,
        genomes,
        rows,
        input_context(tu, terminators, crosswalk, manifest),
    )


def parameters(selection):
    """Construct the complete original-runner parameter admission contract."""
    return {
        "max_sites": selection["max_sites"],
        "seed": selection["seed"],
        "locus_basis": "Tan Table S1 source locus tags; no current-CDS join",
        "upstream_nt": selection["upstream_nt"],
        "downstream_nt": selection["downstream_nt"],
        "candidate_offset_range_inclusive": selection["candidate_offsets"],
        "coordinate_basis": "1-based circular native positions in transcription order",
        "layouts_per_candidate": selection["layouts_per_candidate"],
        "energy_tie_absolute_tolerance": 1e-12,
        "optimum": "minimum dG_total (maximum E. coli model Tx_rate)",
        "control": "One mononucleotide shuffle per oriented window",
    }


def admit_arm(arm, control=False):
    """Validate all 41 states and descriptive summaries; consume only offset zero."""
    fields = (
        "score_curve",
        "best_offsets_nt",
        "anchor_energy_rank_best",
        "anchor_energy_rank_worst",
        "best_distance_min_nt",
        "best_distance_max_nt",
    )
    keys(
        arm,
        (*fields, "sequence", "sequence_sha256", "kind", "identical_to_native")
        if control
        else fields,
    )
    curve = arm["score_curve"]
    require(type(curve) is list and len(curve) == 41, "Incomplete candidate curve")
    for offset, state in zip(range(-20, 21), curve, strict=True):
        keys(state, ("offset_nt", "dG_total", "ecoli_model_Tx_rate"))
        same(state["offset_nt"], offset, "Candidate offset/order")
        require(
            type(state["dG_total"]) in (int, float)
            and math.isfinite(state["dG_total"]),
            "Invalid energy",
        )
        number(state["ecoli_model_Tx_rate"], positive=True)
    best_energy = min(state["dG_total"] for state in curve)
    best = [
        state["offset_nt"]
        for state in curve
        if math.isclose(state["dG_total"], best_energy, rel_tol=0, abs_tol=1e-12)
    ]
    energy = curve[20]["dG_total"]
    tied = [
        math.isclose(state["dG_total"], energy, rel_tol=0, abs_tol=1e-12)
        for state in curve
    ]
    rank_best = 1 + sum(
        s["dG_total"] < energy and not tie for s, tie in zip(curve, tied, strict=True)
    )
    rank_worst = sum(
        s["dG_total"] < energy or tie for s, tie in zip(curve, tied, strict=True)
    )
    expected = (best, rank_best, rank_worst, min(map(abs, best)), max(map(abs, best)))
    for field, value in zip(fields[1:], expected, strict=True):
        same(arm[field], value, f"Arm {field}")
    return curve[20]["ecoli_model_Tx_rate"]


def report_summary(results):
    """Recompute the original descriptive summary from admitted full curves."""
    summary = {
        "anchors": len(results),
        "strands": dict(Counter(row["strand"] for row in results)),
        "replicons": dict(Counter(row["replicon"] for row in results)),
    }
    for arm in ("native", "control"):
        values = [row[arm] for row in results]
        summary[arm] = {
            "any_best_within_5nt": sum(
                row["best_distance_min_nt"] <= 5 for row in values
            ),
            "all_best_within_5nt": sum(
                row["best_distance_max_nt"] <= 5 for row in values
            ),
            "median_anchor_rank_best": statistics.median(
                row["anchor_energy_rank_best"] for row in values
            ),
            "median_anchor_rank_worst": statistics.median(
                row["anchor_energy_rank_worst"] for row in values
            ),
        }
    return summary


def admit_report(report, prepared, protocol, manifest):
    """Strict complete original-runner admission, without opening referenced files."""
    keys(
        report,
        (
            "schema_version",
            "scope",
            "model_host",
            "limitations",
            "inputs",
            "runtime",
            "parameters",
            "cohort",
            "summary",
            "results",
        ),
    )
    same(
        report["schema_version"], protocol["runner"]["schema_version"], "Report schema"
    )
    same(report["model_host"], protocol["runner"]["model_host"], "Model host")
    text(report["scope"])
    require(
        type(report["limitations"]) is list
        and bool(report["limitations"])
        and all(isinstance(x, str) and x for x in report["limitations"]),
        "Missing report limitations",
    )
    runner = protocol["runner"]
    expected_inputs = {
        f"{name}_sha256": manifest["inputs"][name]["sha256"]
        for name in ("fasta", "tss")
    }
    expected_inputs.update(
        upstream_commit=runner["upstream_commit"],
        prepared_files_sha256=runner["prepared_files_sha256"],
    )
    same(report["inputs"], expected_inputs, "Original report inputs")
    runtime = report["runtime"]
    keys(runtime, ("python", "producer_sha256", "numpy", "sklearn", "scipy", "Bio"))
    same(runtime["producer_sha256"], runner["producer_sha256"], "Original producer")
    for name in ("python", "numpy", "sklearn", "scipy", "Bio"):
        text(runtime[name])
    same(report["parameters"], parameters(protocol["selection"]), "Original parameters")
    same(
        report["cohort"],
        {"input_anchors": len(prepared["rows"]), "excluded": prepared["excluded"]},
        "Original exclusions",
    )
    results = report["results"]
    require(type(results) is list and bool(results), "Empty/malformed original report")
    same(
        [row["id"] for row in results],
        prepared["selected_ids"],
        "Selected roster/order",
    )
    by_id = {row["id"]: row for row in prepared["rows"]}
    scored = []
    for result in results:
        keys(
            result,
            (
                "id",
                "replicon",
                "strand",
                "position",
                "locus",
                "sequence",
                "native_positions",
                "sequence_sha256",
                "native",
                "best_native_tss_positions",
                "control",
            ),
        )
        row = by_id[result["id"]]
        for field in (
            "id",
            "replicon",
            "strand",
            "position",
            "locus",
            "sequence",
            "native_positions",
            "sequence_sha256",
        ):
            same(result[field], row[field], f"Original {field}")
        native = admit_arm(result["native"])
        shuffled = admit_arm(result["control"], control=True)
        same(
            result["best_native_tss_positions"],
            [
                row["native_positions"][protocol["selection"]["upstream_nt"] + offset]
                for offset in result["native"]["best_offsets_nt"]
            ],
            "Best native map",
        )
        sequence = list(row["sequence"])
        random.Random(f"{protocol['selection']['seed']}:{row['id']}").shuffle(sequence)
        sequence = "".join(sequence)
        expected = {
            "sequence": sequence,
            "sequence_sha256": digest(sequence),
            "kind": "mononucleotide shuffle; no native coordinates",
            "identical_to_native": sequence == row["sequence"],
        }
        for field, value in expected.items():
            same(result["control"][field], value, f"Original control {field}")
        scored.append({**row, "native_rate": native, "shuffled_rate": shuffled})
    same(report["summary"], report_summary(results), "Original summary")
    return scored


def ranks(values):
    """Average one-based ranks for all ties, including zeros."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranked = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for i in order[start:end]:
            ranked[i] = (start + 1 + end) / 2
        start = end
    return ranked


def spearman(left, right, minimum=3):
    """Return average-rank correlation or an explicit undefined reason."""
    require(len(left) == len(right), "Unpaired observations")
    if len(left) < minimum:
        return {"value": None, "reason": "fewer-than-minimum-pairs"}
    left, right = ranks(left), ranks(right)
    middle = (len(left) + 1) / 2
    x, y = [v - middle for v in left], [v - middle for v in right]
    xx, yy = sum(v * v for v in x), sum(v * v for v in y)
    if not xx or not yy:
        return {"value": None, "reason": "constant-ranks"}
    rho = sum(a * b for a, b in zip(x, y, strict=True)) / math.sqrt(xx * yy)
    return {"value": rho, "reason": None}


def mean_pair(pair):
    return None if None in pair else pair[0] / 2 + pair[1] / 2


def denominator(rows, eligible):
    """Expose endpoint row and group counts before and after missingness."""
    return {
        "n": len(rows),
        "eligible": len(eligible),
        "missing": len(rows) - len(eligible),
        "groups": len({row["group"] for row in rows}),
        "eligible_groups": len({row["group"] for row in eligible}),
        "group_sizes": dict(sorted(Counter(row["group"] for row in rows).items())),
        "eligible_group_sizes": dict(
            sorted(Counter(row["group"] for row in eligible).items())
        ),
    }


def paired_endpoint(rows, condition="control", replicate=None):
    """Native/shuffled correlations on exactly the same nonmissing response rows."""
    response = [
        mean_pair(row["counts"][condition])
        if replicate is None
        else row["counts"][condition][replicate]
        for row in rows
    ]
    eligible = [
        row for row, value in zip(rows, response, strict=True) if value is not None
    ]
    values = [value for value in response if value is not None]
    native = spearman([row["native_rate"] for row in eligible], values)
    shuffled = spearman([row["shuffled_rate"] for row in eligible], values)
    delta = {"value": None, "reason": "undefined-arm"}
    if native["value"] is not None and shuffled["value"] is not None:
        delta = {"value": native["value"] - shuffled["value"], "reason": None}
    return {
        **denominator(rows, eligible),
        "native": native,
        "shuffled": shuffled,
        "native_minus_shuffled": delta,
    }


def quantile(values, probability):
    """Interpolate sorted values at the frozen (n-1)*p position."""
    values = sorted(values)
    position = (len(values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def bootstrap(rows, settings):
    """Paired cluster resampling; ranks recomputed with all duplicate group rows."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)
    ordered = sorted(groups)
    rng = random.Random(settings["seed"])
    arms = ("native", "shuffled", "native_minus_shuffled")
    samples = {arm: [] for arm in arms}
    requested = settings["replicates"]
    if len(ordered) >= settings["minimum_groups"]:
        for _ in range(requested):
            draw = [row for _ in ordered for row in groups[rng.choice(ordered)]]
            point = paired_endpoint(draw)
            for arm in arms:
                if point[arm]["value"] is not None:
                    samples[arm].append(point[arm]["value"])
    result = {}
    for arm, values in samples.items():
        valid = len(values)
        reason = (
            "too-few-groups"
            if len(ordered) < settings["minimum_groups"]
            else "fewer-than-90-percent-valid"
            if valid < 0.9 * requested
            else None
        )
        result[arm] = {
            "requested": requested,
            "valid": valid,
            "undefined": requested - valid,
            "interval": [quantile(values, p) for p in settings["interval"]]
            if reason is None
            else None,
            "reason": reason,
        }
    return result


def analyze(rows, protocol):
    """Describe all conditions and disjoint strata; only primary gets CIs."""
    primary = paired_endpoint(rows)
    primary["bootstrap"] = bootstrap(rows, protocol["uncertainty"])
    secondary = {}
    for condition in CONDITIONS:
        eligible = [row for row in rows if None not in row["counts"][condition]]
        secondary[condition] = {
            "replicate_1": paired_endpoint(rows, condition, 0),
            "replicate_2": paired_endpoint(rows, condition, 1),
            "mean": paired_endpoint(rows, condition),
            "replicate_agreement": {
                **denominator(rows, eligible),
                **spearman(
                    [row["counts"][condition][0] for row in eligible],
                    [row["counts"][condition][1] for row in eligible],
                ),
            },
        }
    strata = {}
    families = {
        "mapping_status": ("unique", "unmatched", "ambiguous", "identity_conflict"),
        "tu_state": (*STATES, "mapping-unavailable"),
        "terminator": (*TERMINATORS, "mapping-unavailable"),
    }
    for family, levels in families.items():
        strata[family] = {
            value: paired_endpoint([row for row in rows if row[family] == value])
            for value in sorted(levels)
        }
    return {"primary": primary, "conditions": secondary, "strata": strata}


def evaluate(
    prepared_raw, prepared_sha256, report_raw, report_sha256, protocol, manifest
):
    """Bind explicit read bytes, rederive preparation, admit full report, describe."""
    same(digest(prepared_raw), checked_hash(prepared_sha256), "Prepared file hash")
    same(digest(report_raw), checked_hash(report_sha256), "Report file hash")
    prepared, report = parse_json(prepared_raw), parse_json(report_raw)
    rebuilt = build_prepared(
        protocol,
        manifest,
        prepared["genomes"],
        prepared["source_rows"],
        prepared["context"],
    )
    same(prepared, rebuilt, "Prepared relationships/trust/schema")
    rows = admit_report(report, prepared, protocol, manifest)
    return {
        "schema": "promoter-count-association-evaluation-1",
        "trust": trust(protocol, manifest),
        "read_artifacts": {
            "prepared_sha256": prepared_sha256,
            "report_sha256": report_sha256,
        },
        "referenced_model_identities_not_read": protocol["runner"],
        "independent_source_reproduction_established": False,
        "stage": protocol["stage"],
        "target": protocol["target"],
        "forbidden_claims": protocol["forbidden_claims"],
        "source_accounting": {
            "input_rows": len(prepared["rows"]),
            "selected": len(rows),
            "excluded": prepared["excluded"],
            "groups": prepared["groups"],
        },
        "rows": rows,
        **analyze(rows, protocol),
    }


def main(argv=None):
    """Run one bounded operation and report malformed data with exit code 2."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    prep = subparsers.add_parser("prepare")
    prep.add_argument("--input-root", required=True, type=Path)
    prep.add_argument("--output", required=True, type=Path)
    evaluation = subparsers.add_parser("evaluate")
    for name in ("prepared", "prepared-sha256", "report", "report-sha256", "output"):
        evaluation.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    try:
        protocol, manifest = freezes()
        if args.operation == "prepare":
            result = prepare(args.input_root, protocol, manifest)
        else:
            result = evaluate(
                read_bytes(args.prepared),
                args.prepared_sha256,
                read_bytes(args.report),
                args.report_sha256,
                protocol,
                manifest,
            )
        publish(args.output, result)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OverflowError,
        RecursionError,
        EOFError,
        csv.Error,
    ) as exc:
        print(f"count association: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
