"""Resource admission retains intentionally unsupported starts as partial output."""

import hashlib
import json
from pathlib import Path

import pytest
from test_transcript import SyntheticSession
from test_transcript import backend as backend

from regsite import transcript_cli
from regsite.backend import RnaStructure

ROOT = Path(__file__).parents[1] / "models/transcript/0.8.0rc1"
PLAN = json.loads((ROOT / "resource-plan.json").read_bytes())


@pytest.mark.parametrize("identifier", ["maximum-A", "maximum-GC", "maximum-ACGT"])
def test_unsupported_resource_controls_expect_partial_exit(
    identifier, monkeypatch, capsys, backend
):
    def forbidden(*args):
        pytest.fail("unsupported-start control attempted folding")

    for method in ("fold", "cofold", "evaluate", "evaluate_many"):
        monkeypatch.setattr(SyntheticSession, method, forbidden)
    monkeypatch.setattr(RnaStructure, "open", lambda root: backend)
    case = next(case for case in PLAN["cases"] if case["id"] == identifier)
    path = ROOT / "requests" / (identifier + ".json")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == case["request_sha256"]
    assert (
        transcript_cli.main([str(path), "--backend-root", "synthetic"])
        == (case["expected_exit"])
        == 1
    )
    output = capsys.readouterr()
    assert output.err == ""
    result = json.loads(output.out)
    assert result["status"] == "partial"
    assert result["components"]["rbs"]["status"] == "unsupported"
    assert len(result["cds"]) == 10
    assert all(row["reason"] == "unsupported_start_codon" for row in result["cds"])
    coverage = result["components"]["promoter"]["coverage"]
    assert coverage["requested"] == coverage["returned"] == coverage["scored"] == 512
    assert coverage["missing"] == coverage["not_evaluated"] == 0
