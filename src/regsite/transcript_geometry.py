"""Checked coordinate exports for a supplied, strictly linear RNA segment."""

from regsite import promoter


class GeometryError(ValueError):
    """A native feature contradicts its declared coordinate frame."""


def interval(value: object, length: int) -> list[int]:
    """Check an ascending half-open interval, retaining empty boundary spans."""
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(type(x) is not int for x in value)
        or not 0 <= value[0] <= value[1] <= length
    ):
        raise GeometryError("native interval outside its coordinate frame")
    return list(value)


def feature(
    bounds: object,
    *,
    length: int,
    offset: int,
    strand: str,
    projection: dict | None,
) -> dict:
    """Offset a verified native interval and use the public genomic projector.

    Empty spans have no genomic bases or runs. They retain their exact local
    boundary, including length, without pretending it is a genomic point.
    """
    native = None if bounds is None else interval(bounds, length)
    construct = None if native is None else [x + offset for x in native]
    genomic = None
    if construct is not None and projection is not None:
        mapped_strand, runs = promoter.project_interval(
            projection, strand, (construct[0], construct[1])
        )
        genomic = {
            "contig": projection["contig"],
            "strand": mapped_strand,
            "runs": [] if construct[0] == construct[1] else [list(r) for r in runs],
        }
    return {
        "native_interval": native,
        "construct_interval": construct,
        "local_strand": strand,
        "genomic": genomic,
        "reason": "feature_unavailable" if native is None else None,
    }


def _rbs_interval(raw: object) -> object:
    if raw is None:
        return None
    if not isinstance(raw, dict) or not {"start", "end"} <= raw.keys():
        raise GeometryError("native RBS interval missing start/end")
    if raw.get("strand") != "+":
        raise GeometryError("native RBS interval must be transcript-oriented +")
    return [raw["start"], raw["end"]]


def rbs_features(site: dict, length: int, offset: int, projection: dict | None) -> dict:
    """Export only established native RBS interval semantics, never CT indices."""
    bounds = {
        name: _rbs_interval(site.get(name))
        for name in (
            "start_codon",
            "binding_interval",
            "standby_interval",
            "coding_footprint",
        )
    }
    window = site.get("window")
    if not isinstance(window, dict) or "input_interval" not in window:
        raise GeometryError("native RBS window missing input_interval")
    bounds["window"] = _rbs_interval(window["input_interval"])
    standby = site.get("standby") or {}
    for name in ("original_hairpin", "hairpin", "distal", "proximal"):
        bounds["standby." + name] = _rbs_interval(standby.get(name))
    for i, item in enumerate(standby.get("downstream_hairpins", [])):
        bounds[f"standby.downstream_hairpins.{i}"] = _rbs_interval(item["interval"])
    return {
        name: feature(
            raw, length=length, offset=offset, strand="+", projection=projection
        )
        for name, raw in bounds.items()
    }


def promoter_features(site: dict, length: int, projection: dict | None) -> dict:
    """Export selected model windows in the full construct frame."""
    selected = site["selected"]
    bounds = dict.fromkeys(
        ("UP", "gap", "hex35", "spacer", "extended10", "hex10", "discriminator", "itr")
    )
    if selected is not None:
        if not isinstance(selected.get("intervals"), dict):
            raise GeometryError("native selected Promoter intervals missing")
        oriented = site["tss"]["oriented_base"]
        expected_oriented = (
            site["tss"]["forward_base"]
            if site["strand"] == "+"
            else length - 1 - site["tss"]["forward_base"]
        )
        if oriented != expected_oriented:
            raise GeometryError("native Promoter orientation mismatch")
        expected = {
            name: list(
                promoter.oriented_to_local_interval(length, site["strand"], span)
            )
            for name, span in promoter.state_windows(
                oriented, selected["discriminator_length"], selected["spacer_length"]
            ).items()
        }
        if selected["intervals"] != expected:
            raise GeometryError("native Promoter selected window mismatch")
        bounds.update(selected["intervals"])
    tss = site["tss"]["forward_base"]
    bounds["tss"] = [tss, tss + 1]
    return {
        name: feature(
            raw, length=length, offset=0, strand=site["strand"], projection=projection
        )
        for name, raw in bounds.items()
    }
