"""SEC EDGAR adapter for official filings and XBRL company facts."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import DataProvider
from .schemas import DataProviderError, FundamentalsSnapshot, ProviderCapability, SourceAudit

SEC_USER_AGENT = os.getenv(
    "SEC_EDGAR_USER_AGENT",
    "TitanIntegration/0.1 research-user-agent-not-configured",
)


class SecEdgarProvider(DataProvider):
    name = "sec_edgar"
    capabilities = (ProviderCapability.FUNDAMENTALS, ProviderCapability.FILINGS)

    def get_fundamentals(self, symbol: str) -> FundamentalsSnapshot:
        cik = _cik_for_symbol(symbol)
        companyfacts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        facts_payload = _get_json(companyfacts_url)
        submissions = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")

        facts = _latest_core_facts(facts_payload.get("facts", {}))
        filings = _recent_filings(submissions, limit=10)

        audit = SourceAudit.now(
            provider=self.name,
            source_url=companyfacts_url,
            license_note="Official SEC EDGAR public API; no API key required.",
            reliability="official",
            raw_reference=f"CIK{cik}",
        )

        return FundamentalsSnapshot(
            symbol=symbol.upper(),
            cik=cik,
            fiscal_period=_first_available(facts, "DocumentFiscalPeriodFocus"),
            fiscal_year=_safe_int(_first_available(facts, "DocumentFiscalYearFocus")),
            facts=facts,
            filings=filings,
            source=audit,
        )

    def get_filings(self, symbol: str, limit: int = 10) -> list[dict]:
        cik = _cik_for_symbol(symbol)
        submissions = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        return _recent_filings(submissions, limit=limit)


@lru_cache(maxsize=1)
def _ticker_map() -> dict[str, str]:
    payload = _get_json("https://www.sec.gov/files/company_tickers.json")
    mapping: dict[str, str] = {}
    for item in payload.values():
        ticker = item["ticker"].upper()
        mapping[ticker] = str(item["cik_str"]).zfill(10)
    return mapping


def _cik_for_symbol(symbol: str) -> str:
    ticker = symbol.upper()
    mapping = _ticker_map()
    try:
        return mapping[ticker]
    except KeyError as exc:
        raise DataProviderError(f"No SEC CIK mapping found for {ticker}") from exc


def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise DataProviderError(f"SEC EDGAR request failed: {url}") from exc


def _latest_core_facts(facts_root: dict) -> dict:
    us_gaap = facts_root.get("us-gaap", {})
    dei = facts_root.get("dei", {})
    wanted = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": us_gaap,
        "Revenues": us_gaap,
        "NetIncomeLoss": us_gaap,
        "OperatingIncomeLoss": us_gaap,
        "NetCashProvidedByUsedInOperatingActivities": us_gaap,
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations": us_gaap,
        "PaymentsToAcquirePropertyPlantAndEquipment": us_gaap,
        "PaymentsToAcquireProductiveAssets": us_gaap,
        "PaymentsToAcquireBusinessesAndPropertyPlantAndEquipment": us_gaap,
        "Assets": us_gaap,
        "Liabilities": us_gaap,
        "StockholdersEquity": us_gaap,
        "EarningsPerShareDiluted": us_gaap,
        "DocumentFiscalYearFocus": dei,
        "DocumentFiscalPeriodFocus": dei,
    }

    latest: dict = {}
    for concept, namespace in wanted.items():
        concept_payload = namespace.get(concept)
        if not concept_payload:
            continue
        unit_payload = concept_payload.get("units", {})
        unit_name, values = _first_unit(unit_payload)
        if not values:
            continue
        value = _latest_fact(values)
        if value is not None:
            latest[concept] = {
                "value": value.get("val"),
                "unit": unit_name,
                "period": value.get("fy"),
                "form": value.get("form"),
                "filed": value.get("filed"),
                "end": value.get("end"),
            }
    return latest


def _first_unit(unit_payload: dict) -> tuple[str | None, list[dict]]:
    for unit_name, values in unit_payload.items():
        return unit_name, values
    return None, []


def _latest_fact(values: list[dict]) -> dict | None:
    if not values:
        return None
    return sorted(values, key=lambda item: item.get("filed", ""))[-1]


def _recent_filings(submissions: dict, limit: int) -> list[dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])

    filings: list[dict] = []
    for index, form in enumerate(forms[:limit]):
        filings.append(
            {
                "form": form,
                "accession_number": _at(accession_numbers, index),
                "filing_date": _at(filing_dates, index),
                "report_date": _at(report_dates, index),
            }
        )
    return filings


def _at(values: list, index: int):
    return values[index] if index < len(values) else None


def _first_available(facts: dict, concept: str):
    item = facts.get(concept)
    if not item:
        return None
    return item.get("value")


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
