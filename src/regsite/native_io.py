"""Bounded native JSON loading and explicit GFF3 coordinate export."""

import json
from typing import TextIO
from urllib.parse import quote

from regsite.native import RESULT_VERSION
from regsite.sequence import InputError

MAX_NATIVE_CHARACTERS = 40_000_000


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate native JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise InputError(f"nonfinite native JSON number: {value}")


def load_native(stream: TextIO) -> object:
    """Read bounded JSON; duplicate settings and nonfinite values are errors."""
    text = stream.read(MAX_NATIVE_CHARACTERS + 1)
    if len(text) > MAX_NATIVE_CHARACTERS:
        raise InputError("native JSON exceeds 40M characters")
    try:
        return json.loads(text, parse_constant=_constant, object_pairs_hook=_object)
    except (ValueError, RecursionError) as exc:
        raise InputError(f"invalid native JSON: {exc}") from exc


def gff_bounds(segments: list[dict], contig_length: int) -> tuple[int, int] | None:
    """Convert projected half-open segments to 1-based inclusive GFF3 bounds.

    Circular spans use the GFF3 convention end > contig length. Empty modeled
    intervals produce no feature, rather than becoming a zero-length insertion.
    Inputs are projected intervals from the validated native result contract.
    """
    if not segments:
        return None
    if len(segments) == 1:
        return segments[0]["start"] + 1, segments[0]["end"]
    lower, upper = sorted(segments, key=lambda segment: segment["start"])
    return upper["start"] + 1, contig_length + lower["end"]


def _attribute(value: object) -> str:
    # GFF3 attributes reserve controls, %, ;, =, &, and comma. Unicode/spaces
    # remain ordinary UTF-8 text; unlike seqid they need not be URL-encoded.
    return "".join(
        f"%{ord(c):02X}" if c in "%;&=," or ord(c) < 32 or ord(c) == 127 else c
        for c in str(value)
    )


def write_gff3(result: dict, stream: TextIO) -> None:
    """Export predicted anchors/spans, with missing rows retained as comments.

    The numeric score and CDS phase columns are '.', since relative TIR is not
    a calibrated significance score and these features are not full CDSs.
    JSON remains authoritative for evidence, failures and complete structures.
    """
    if result.get("schema_version") != RESULT_VERSION:
        raise InputError("GFF3 export requires native-rbs-result-1")
    stream.write("##gff-version 3\n")
    stream.write("# Model predictions; binding spans are not measured SD boundaries.\n")
    landmarks = {}
    for record in result["results"]:
        if record["context"] is not None:
            landmarks[record["evidence"]["genome_id"]] = record["context"]
    for key, context in landmarks.items():
        seqid = quote(key, safe=".:^*$@!+_?-|").replace("~", "%7E")
        length = context["path"]["contig_length"]
        stream.write(f"##sequence-region {seqid} 1 {length}\n")
        attributes = {
            "ID": f"regsite:{result['batch_id']}:landmark:{key}",
            "Name": context["genome"]["accession"],
            "assembly": context["genome"]["assembly"],
            "annotation": context["genome"]["annotation"],
            "sequence_sha256": context["genome"]["sequence_sha256"],
            "Is_circular": str(context["path"]["circular"]).lower(),
        }
        stream.write(
            f"{seqid}\tregsite\tregion\t1\t{length}\t.\t+\t.\t"
            + ";".join(f"{k}={_attribute(v)}" for k, v in attributes.items())
            + "\n"
        )
    for row_index, record in enumerate(result["results"]):
        stream.write(
            f"# record={_attribute(record['id'])};status={record['status']};"
            f"reason={_attribute(record['reason'] or '')}\n"
        )
        if record["prediction"] is None:
            continue
        context = record["context"]
        seqid = quote(record["evidence"]["genome_id"], safe=".:^*$@!+_?-|").replace(
            "~", "%7E"
        )
        length = context["path"]["contig_length"]
        for site_index, (site, projected) in enumerate(
            zip(record["prediction"]["sites"], record["genomic_sites"], strict=True)
        ):
            for field in (
                "start_codon",
                "binding_interval",
                "standby_interval",
                "coding_footprint",
            ):
                segments = projected[field]
                bounds = gff_bounds(segments, length) if segments is not None else None
                if bounds is None:
                    continue
                attributes = {
                    "ID": (
                        f"regsite:{result['batch_id']}:{row_index}:{site_index}:{field}"
                    ),
                    "Name": record["id"],
                    "prediction_kind": field,
                    "model_id": result["model_id"],
                    "prediction_id": record["prediction"]["prediction_id"],
                    "status": site["status"],
                }
                if site["tir"] is not None:
                    attributes["relative_tir"] = site["tir"]
                line = [
                    seqid,
                    "regsite",
                    "start_codon" if field == "start_codon" else "sequence_feature",
                    str(bounds[0]),
                    str(bounds[1]),
                    ".",
                    context["path"]["strand"],
                    ".",
                    ";".join(f"{k}={_attribute(v)}" for k, v in attributes.items()),
                ]
                stream.write("\t".join(line) + "\n")
