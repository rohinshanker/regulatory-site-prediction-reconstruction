"""Download only declared source members, verify hashes, and keep them outside Git."""

import io
from pathlib import Path
import urllib.request
import zipfile

from benchmarks.rbs.datasets import PINS, digest

SOURCES = {
    "standby2014": ("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3936740/supplementaryFiles",
                    ("supp_gkt1139_nar-02492-r-2013-File010.xls",)),
    "footprint2017": ("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5435973/supplementaryFiles",
                      ("gkx061_Supp.zip", "nar-03716-r-2016-File008.xlsx")),
    "salis2009": ("https://raw.githubusercontent.com/reisalex/SynBioMTS/"
                  "d7d46af7981f90d2147cbc0463c5254b16c5c92c/examples/RBS/datasets/Salis_Nat_Biotech_2009.xls", ()),
    "mts2020_ic": ("https://ndownloader.figshare.com/files/25103531", ()),
    "mts2020_fs": ("https://ndownloader.figshare.com/files/25103534", ()),
}


def fetch(root, identities):
    """Fetch missing files; never replace changed cached data or extract other files."""
    root = Path(root).resolve()
    repository = Path(__file__).resolve().parents[2]
    if root == repository or repository in root.parents:
        raise ValueError("Source downloads must stay outside the repository")
    result = {}
    for identity in identities:
        relative, expected = PINS[identity]
        path = root / relative
        if path.exists():
            data = path.read_bytes()
        else:
            url, members = SOURCES[identity]
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            for member in members:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    data = archive.read(member)
        if digest(data) != expected:
            raise ValueError(f"Source hash mismatch: {identity}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
        result[identity] = expected
    return result
