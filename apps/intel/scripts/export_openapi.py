"""Write (or --check) packages/contracts/openapi.json from the FastAPI app."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intel.api import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "openapi.json"


def main() -> int:
    spec = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != spec:
            print(f"{OUT} is stale - run: uv run python scripts/export_openapi.py")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(spec)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
