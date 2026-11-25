"""Write a synthetic call check snapshot for the TestOps demonstration."""

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

LIMIT_MS = 15_000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-ms", required=True, type=int)
    parser.add_argument(
        "--output", type=Path, default=Path("examples/stand/latest.json")
    )
    args = parser.parse_args()
    if args.connection_ms < 0:
        parser.error("--connection-ms must be non-negative")
    passed = args.connection_ms <= LIMIT_MS
    snapshot = {
        "check_id": str(uuid4()),
        "bench": "CALL-01",
        "name": "Установление исходящего вызова",
        "outcome": "passed" if passed else "failed",
        "note": (f"Демо: задано {args.connection_ms} мс при лимите {LIMIT_MS} мс."),
        "measured_at": datetime.now(UTC).isoformat(),
    }
    output = args.output.resolve()
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(snapshot, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            # The Compose application reads this file as an unprivileged user.
            temporary.chmod(0o644)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"{snapshot['outcome']}: {output}")


if __name__ == "__main__":
    main()
