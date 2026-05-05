"""User-supplied input folder discovery.

The research workflow should prefer the latest ticker/date input folder that is
eligible for the requested analysis date. This keeps operator commands simple
and prevents stale local CSV folders from being selected by habit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


SUPPORTED_USER_FILE_SUFFIXES = {".csv", ".json", ".md", ".txt", ".pdf", ".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class InputFolderResolution:
    ticker: str
    analysis_date: str
    selected_input_folder: str
    selection_reason: str
    dated_folders_considered: list[str]
    requested_input_folder: str | None = None
    warning: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "analysis_date": self.analysis_date,
            "selected_input_folder": self.selected_input_folder,
            "selection_reason": self.selection_reason,
            "dated_folders_considered": self.dated_folders_considered,
            "requested_input_folder": self.requested_input_folder,
            "warning": self.warning,
        }


def resolve_latest_input_folder(
    *,
    input_root: Path,
    ticker: str,
    analysis_date: str,
    requested_input_folder: Path | None = None,
) -> InputFolderResolution:
    """Resolve the best available user-input folder for a ticker/date.

    Selection order:
    1. Latest dated ``inputs/<TICKER>/<YYYY-MM-DD>`` folder on or before the
       analysis date that contains supported user files.
    2. Requested folder, if supplied and usable.
    3. Exact dated folder path, even if it does not yet exist, so users have a
       deterministic place to add files.
    """

    ticker_upper = ticker.upper()
    root = input_root.resolve()
    ticker_root = root / ticker_upper
    eligible = _eligible_dated_folders(ticker_root, analysis_date)
    requested_resolved = requested_input_folder.resolve() if requested_input_folder else None
    requested_text = str(requested_resolved) if requested_resolved else None

    if eligible:
        selected = eligible[-1]
        warning = None
        if requested_resolved and requested_resolved != selected:
            warning = (
                f"Requested input folder {requested_resolved} was not the latest eligible dated folder; "
                f"selected {selected} instead."
            )
        return InputFolderResolution(
            ticker=ticker_upper,
            analysis_date=analysis_date,
            selected_input_folder=str(selected),
            selection_reason="latest_eligible_dated_folder_with_supported_files",
            dated_folders_considered=[str(path) for path in eligible],
            requested_input_folder=requested_text,
            warning=warning,
        )

    if requested_resolved and _has_supported_files(requested_resolved):
        return InputFolderResolution(
            ticker=ticker_upper,
            analysis_date=analysis_date,
            selected_input_folder=str(requested_resolved),
            selection_reason="requested_folder_with_supported_files",
            dated_folders_considered=[],
            requested_input_folder=requested_text,
        )

    fallback = ticker_root / analysis_date
    return InputFolderResolution(
        ticker=ticker_upper,
        analysis_date=analysis_date,
        selected_input_folder=str(fallback.resolve()),
        selection_reason="no_existing_dated_folder_with_supported_files; using_exact_analysis_date_path",
        dated_folders_considered=[],
        requested_input_folder=requested_text,
        warning="No dated user-input folder with supported files was found on or before the analysis date.",
    )


def _eligible_dated_folders(ticker_root: Path, analysis_date: str) -> list[Path]:
    cutoff = _parse_date(analysis_date)
    if not ticker_root.exists():
        return []
    folders: list[tuple[date, Path]] = []
    for path in ticker_root.iterdir():
        if not path.is_dir():
            continue
        folder_date = _parse_date(path.name)
        if not folder_date or folder_date > cutoff:
            continue
        if _has_supported_files(path):
            folders.append((folder_date, path.resolve()))
    folders.sort(key=lambda item: item[0])
    return [path for _, path in folders]


def _has_supported_files(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    for item in path.iterdir():
        if item.is_file() and item.suffix.lower() in SUPPORTED_USER_FILE_SUFFIXES:
            return True
    return False


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
