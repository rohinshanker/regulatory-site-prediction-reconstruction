"""Independent finite-state arithmetic for the historical Promoter reference.

Research fixture tooling, not the project predictor. Equations, tables and
parameters originate in the pinned Salis GPL-3.0-or-later source; see NOTICE.
No upstream inference code or experimental measurements are imported.
"""

import math


def intervals(tss, discriminator, spacer):
    """Derive zero-based half-open windows backwards from the first ITR base."""
    disc = [tss - discriminator, tss]
    h10 = [disc[0] - 6, disc[0]]
    sp = [h10[0] - spacer, h10[0]]
    h35 = [sp[0] - 6, sp[0]]
    gap = [h35[0] - 1, h35[0]]
    return {
        "UP": [gap[0] - 24, gap[0]],
        "gap": gap,
        "hex35": h35,
        "spacer": sp,
        "extended10": [sp[1] - 3, sp[1] - 1],
        "hex10": h10,
        "disc": disc,
        "ITR": [tss, tss + 20],
    }


def project_reverse(length, tss, windows):
    """Keep the historical boundary-like key separate from a mapped base."""
    return {
        "legacy_key": length - tss,
        "forward_base": length - 1 - tss,
        "forward_intervals": {
            k: [length - b, length - a] for k, (a, b) in windows.items()
        },
    }


def kmer_index(word):
    """OneHotEncoder sorts DNA categories lexically: A,C,G,T, base-four index."""
    value = 0
    for base in word:
        value = 4 * value + "ACGT".index(base)
    return value


def terms(sequence, windows, parameters):
    """Independent scalar expression of every active source feature/term."""
    features = {k: sequence[a:b] for k, (a, b) in windows.items()}
    c = parameters["coefficients"]
    tables = parameters["tables"]

    def dimers(sequence, table):
        return math.fsum(
            tables[table][sequence[i : i + 2]] for i in range(0, len(sequence), 2)
        )

    up, h35, h10, sp, itr = (
        features[k] for k in ("UP", "hex35", "hex10", "spacer", "ITR")
    )
    # Source uses seven NON-overlapping dimers at offsets0,2,...,12, not14.
    dna = dimers(itr[:14], "DNA_DNA_hybrids")
    rna = dimers(itr[:14], "RNA_DNA_hybrids")
    raw = [
        dimers(up[:12], "groove_access"),
        dimers(up[12:], "groove_access"),
        dna - rna,
        dimers(up + h35 + sp[:14], "persistence") / 44,
    ]
    normalized = [raw[i] / parameters["normalizers"][i] * c[339 + i] for i in range(4)]
    result = {
        "dG_10": c[kmer_index(h10[:3])] + c[64 + kmer_index(h10[3:])],
        "dG_35": c[128 + kmer_index(h35[:3])] + c[192 + kmer_index(h35[3:])],
        "dG_disc": c[256 + kmer_index(features["disc"][:3])],
        "dG_ext10": c[320 + kmer_index(features["extended10"])],
        "dG_ITR": normalized[2],
        "dG_UP": math.fsum((normalized[0], normalized[1], normalized[3])),
        "dG_spacer": 0.1463 * len(sp) ** 2 - 4.9113 * len(sp) + 41.119,
    }
    result["dG_total"] = math.fsum((*result.values(), parameters["intercept"]))
    result["dG_bind"] = math.fsum(
        result[k] for k in ("dG_10", "dG_35", "dG_ext10", "dG_UP", "dG_spacer")
    )
    result["dG_apparent"] = (result["dG_total"] + 2.80271176) / 0.81632623
    return {"features": features, "raw_numericals": raw, "terms": result}


def states(
    sequence, tss, parameters, organism="Escherichia coli str. K-12 substr. MG1655"
):
    """Enumerate the declared30 states, retaining only complete source windows."""
    beta = 0.81632623 if organism == "in vitro" else 1.636217004872062
    records = []
    for discriminator in range(6, 11):
        for spacer in range(15, 21):
            windows = intervals(tss, discriminator, spacer)
            if windows["UP"][0] < 0 or windows["ITR"][1] > len(sequence):
                continue
            value = terms(sequence, windows, parameters)
            value.update(
                tss=tss,
                discriminator=discriminator,
                spacer=spacer,
                intervals=windows,
                Tx_rate=42 * math.exp(-beta * value["terms"]["dG_total"]),
                beta=beta,
                K=42,
            )
            records.append(value)
    return records


def winner(records):
    """Exact first-visited tie order: discriminator then spacer, both ascending."""
    return min(records, key=lambda r: r["terms"]["dG_total"]) if records else None
