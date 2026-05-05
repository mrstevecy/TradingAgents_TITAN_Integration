"""Logo asset resolution for report theming.

The resolver is intentionally conservative:

1. Use a previously approved local logo asset when available.
2. If missing, discover the issuer's official website and try to acquire an
   icon/logo asset from that site.
3. If no suitable official-site asset is found, fall back to a ticker badge.

This keeps report generation deterministic while still supporting automated
logo discovery for new companies.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LOGO_DIR = REPO_ROOT / "assets" / "logos"
LOGO_MANIFEST = LOGO_DIR / "logo_manifest.json"


@dataclass(frozen=True)
class LogoResolution:
    ticker: str
    status: str
    path: Path | None
    source_url: str | None
    official_website: str | None
    note: str


def _load_manifest() -> dict[str, Any]:
    if LOGO_MANIFEST.exists():
        return json.loads(LOGO_MANIFEST.read_text(encoding="utf-8"))
    return {"logos": {}}


def _write_manifest(manifest: dict[str, Any]) -> None:
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    LOGO_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _local_logo(ticker: str) -> Path | None:
    for ext in (".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico"):
        path = LOGO_DIR / f"{ticker.upper()}{ext}"
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def _urlopen_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "TitanTradingResearch/0.1 logo-resolver"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(2_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def _download(url: str, output: Path, timeout: int = 20) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "TitanTradingResearch/0.1 logo-resolver"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read(5_000_000)
    if not data:
        raise ValueError(f"Empty logo response from {url}")
    output.write_bytes(data)


def _discover_official_website(ticker: str) -> str | None:
    manifest = _load_manifest()
    entry = manifest.get("logos", {}).get(ticker.upper(), {})
    if entry.get("official_website"):
        return str(entry["official_website"])
    try:
        import yfinance as yf  # type: ignore

        info = yf.Ticker(ticker).get_info()
        website = info.get("website") or info.get("irWebsite")
        return str(website) if website else None
    except Exception:
        return None


def _candidate_logo_urls(official_website: str) -> list[str]:
    html = _urlopen_text(official_website)
    base = official_website
    candidates: list[str] = []

    # Prefer explicit logo/open-graph assets, then favicons.
    patterns = [
        r'<meta[^>]+(?:property|name)=["\'](?:og:logo|og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\'][^"\']*(?:apple-touch-icon|mask-icon|icon|shortcut icon)[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        r'<img[^>]+(?:class|id|alt|src)=["\'][^"\']*logo[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']*logo[^"\']*)["\']',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE):
            url = urllib.parse.urljoin(base, match.group(1).strip())
            if url not in candidates:
                candidates.append(url)
    return candidates


def resolve_logo_asset(
    ticker: str,
    *,
    official_website: str | None = None,
    allow_network: bool = True,
) -> LogoResolution:
    ticker = ticker.upper()
    local = _local_logo(ticker)
    manifest = _load_manifest()
    entry = manifest.setdefault("logos", {}).setdefault(ticker, {})
    if local:
        entry.setdefault("path", str(local.relative_to(REPO_ROOT)))
        entry.setdefault("source_type", "local_approved_asset")
        entry.setdefault("usage_note", "Issuer logo is used solely for identification and does not imply affiliation, sponsorship, approval, or endorsement.")
        _write_manifest(manifest)
        return LogoResolution(
            ticker=ticker,
            status="Local Approved Logo Available",
            path=local,
            source_url=entry.get("source_url"),
            official_website=entry.get("official_website") or official_website,
            note="Using existing local logo asset.",
        )

    if not allow_network:
        return LogoResolution(ticker, "Ticker Badge Fallback", None, None, official_website, "Network discovery disabled and no local logo asset exists.")

    website = official_website or _discover_official_website(ticker)
    if not website:
        return LogoResolution(ticker, "Ticker Badge Fallback", None, None, None, "No official website was available for logo discovery.")

    try:
        candidates = _candidate_logo_urls(website)
        preferred = sorted(
            candidates,
            key=lambda url: (
                0 if url.lower().endswith(".svg") else 1,
                0 if "logo" in url.lower() else 1,
                len(url),
            ),
        )
        for url in preferred:
            suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
            if suffix not in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico"}:
                suffix = ".png"
            output = LOGO_DIR / f"{ticker}{suffix}"
            _download(url, output)
            entry.update(
                {
                    "path": str(output.relative_to(REPO_ROOT)),
                    "source_url": url,
                    "official_website": website,
                    "source_type": "official_website_discovery",
                    "usage_note": "Issuer logo is used solely for identification and does not imply affiliation, sponsorship, approval, or endorsement.",
                }
            )
            _write_manifest(manifest)
            return LogoResolution(ticker, "Official Website Logo Discovered", output, url, website, "Downloaded candidate logo/icon from issuer official website.")
    except Exception as exc:
        entry.update(
            {
                "official_website": website,
                "source_type": "official_website_discovery_failed",
                "error": str(exc),
            }
        )
        _write_manifest(manifest)
        return LogoResolution(ticker, "Ticker Badge Fallback", None, None, website, f"Official website logo discovery failed: {exc}")

    return LogoResolution(ticker, "Ticker Badge Fallback", None, None, website, "No suitable logo/icon asset was found on the official website.")
