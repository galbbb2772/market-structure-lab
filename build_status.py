"""Write a compact health/coverage summary for the public Structure Lab dataset."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "docs/data/structure_lab.json"
TARGET = ROOT / "docs/data/status.json"
MAJORS = ("^GSPC", "^IXIC", "^DJI")


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    instruments = data.get("instruments") or {}
    macro = data.get("macro") or {}

    summary = {
        "schema": "STRUCTURE-LAB-STATUS-V1",
        "generated_at": data.get("generated_at"),
        "indices": {
            sym: {
                "name": (instruments.get(sym) or {}).get("name"),
                "start": (instruments.get(sym) or {}).get("start"),
                "end": (instruments.get(sym) or {}).get("end"),
                "bars": len((instruments.get(sym) or {}).get("bars") or []),
                "source_status": (instruments.get(sym) or {}).get("source_status"),
            }
            for sym in MAJORS
        },
        "market_instruments": len(instruments),
        "market_failures": sum(1 for k in (data.get("errors") or {}) if k in instruments or k in MAJORS),
        "macro": {
            key: {
                "name": value.get("name"),
                "start": value.get("start"),
                "end": value.get("end"),
                "observations": len(value.get("observations") or []),
                "status": value.get("status"),
            }
            for key, value in macro.items()
        },
        "news_observations": len(data.get("news_tension") or []),
        "news_status": data.get("news_status"),
        "errors": data.get("errors") or {},
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", TARGET)


if __name__ == "__main__":
    main()
