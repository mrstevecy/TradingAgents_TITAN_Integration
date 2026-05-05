"""Smoke-test the Titan data-provider abstraction."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.data_providers import DataProviderError, create_default_registry


def main() -> int:
    out_dir = Path("outputs/data_provider_probe")
    out_dir.mkdir(parents=True, exist_ok=True)

    registry = create_default_registry()
    result = {
        "registered_providers": registry.names(),
        "price_bars": {},
        "fundamentals": {},
        "warnings": [],
    }

    for provider_name in ("yfinance", "stooq"):
        provider = registry.get(provider_name)
        try:
            bars = provider.get_price_bars("NVDA", "2026-04-20", "2026-05-01")
            result["price_bars"][provider_name] = {
                "count": len(bars),
                "first": asdict(bars[0]) if bars else None,
                "last": asdict(bars[-1]) if bars else None,
            }
        except DataProviderError as exc:
            result["warnings"].append(f"{provider_name}: {exc}")

    try:
        fundamentals = registry.get("sec_edgar").get_fundamentals("NVDA")
        result["fundamentals"]["sec_edgar"] = {
            "cik": fundamentals.cik,
            "fact_keys": sorted(fundamentals.facts.keys()),
            "recent_filings": fundamentals.filings[:5],
            "source": asdict(fundamentals.source) if fundamentals.source else None,
        }
    except DataProviderError as exc:
        result["warnings"].append(f"sec_edgar: {exc}")

    output_path = out_dir / "NVDA_provider_probe.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(output_path)
    print(json.dumps(result, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
