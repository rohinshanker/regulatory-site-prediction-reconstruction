"""Analyze explicit transcript/CDS organization with local regulatory predictors."""

import argparse
import os
import sys
from contextlib import nullcontext

from regsite.backend import RnaStructure
from regsite.structures import BackendError
from regsite.transcript import TranscriptError, predict_transcript
from regsite.transcript_io import export_text, load_request


def main(argv: list[str] | None = None) -> int:
    """Return 0 complete, 1 partial/unavailable, or 2 atomic input/setup/I/O error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="supplied-transcript JSON request; '-' for stdin")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument(
        "--backend-root",
        default=os.environ.get("REGSITE_RNASTRUCTURE"),
        help="separate verified RNAstructure installation; eligible CDSs require it",
    )
    args = parser.parse_args(argv)
    try:
        with (
            nullcontext(sys.stdin.buffer)
            if args.input == "-"
            else open(args.input, "rb")
        ) as stream:
            request = load_request(stream)
        backend = RnaStructure.open(args.backend_root) if args.backend_root else None
        result = predict_transcript(request, backend)
        raw = export_text(result, args.format).encode("utf-8")
        sys.stdout.buffer.write(raw)
        sys.stdout.flush()
        return int(result["status"] != "complete")
    except (TranscriptError, BackendError, OSError, UnicodeError) as exc:
        if isinstance(exc, BrokenPipeError):
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        print(
            "regsite-transcript: Input, backend or output is unavailable or invalid",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
