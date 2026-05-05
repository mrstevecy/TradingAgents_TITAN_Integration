"""Run local publication safety checks before creating or pushing a GitHub repo."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC_ROOT_FILES = {
    ".env.example",
    ".gitignore",
    "LICENSE",
    "NOTICE.md",
    "README.md",
    "SECURITY.md",
}
PUBLIC_DIRS = {
    "citation_manifests",
    "docs",
    "inputs",
    "scripts",
    "titan_integration",
}
BLOCKED_DIRS = {
    "TradingAgents",
    "data",
    "corpus",
    "outputs",
    "output",
    "research_materials",
    "research_packets",
    "research_cycles",
    "normalized_data",
    "provider_cache",
    "assets",
    "test-results",
    "playwright-report",
    "htmlcov",
    "logs",
    "embeddings",
    "cache",
    "graphify-out",
}
REQUIRED_GITIGNORE_PATTERNS = {
    ".env",
    "TradingAgents/",
    "data/**",
    "inputs/**",
    "output/**",
    "outputs/**",
    "research_packets/**",
    "research_cycles/**",
    "provider_cache/**",
    "assets/**",
    "test-results/**",
    ".tmp*",
}
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"(?im)(api[_-]?key|secret|token|password)[ \t]*=[ \t]*['\"]?(?!<|your-|$)[A-Za-z0-9_\-]{12,}"),
]


def main() -> int:
    failures: list[str] = []
    failures.extend(_blocked_paths_present_in_public_set())
    failures.extend(_scan_public_files_for_secrets())
    failures.extend(_check_required_docs())
    failures.extend(_check_gitignore_guards())
    if failures:
        print("Publication safety check FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Publication safety check PASSED")
    print("No blocked directories are included in the public candidate set.")
    print("No obvious API key/token patterns were found in public candidate files.")
    print("Required attribution and safety docs are present.")
    return 0


def _public_candidate_files() -> list[Path]:
    files: list[Path] = []
    for name in PUBLIC_ROOT_FILES:
        path = ROOT / name
        if path.exists():
            files.append(path)
    for dirname in PUBLIC_DIRS:
        base = ROOT / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not _is_blocked(path) and not _is_runtime_noise(path):
                if dirname == "inputs" and path.name != "README.md":
                    continue
                files.append(path)
    return files


def _blocked_paths_present_in_public_set() -> list[str]:
    failures: list[str] = []
    for path in _public_candidate_files():
        rel = path.relative_to(ROOT)
        if _is_blocked(path):
            failures.append(f"Blocked path appears in public candidate set: {rel}")
        if rel.parts[0] == "inputs" and path.name != "README.md":
            failures.append(f"User input file would be public: {rel}")
    return failures


def _scan_public_files_for_secrets() -> list[str]:
    failures: list[str] = []
    for path in _public_candidate_files():
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"Possible secret pattern in {path.relative_to(ROOT)}")
                break
    return failures


def _check_required_docs() -> list[str]:
    failures: list[str] = []
    required = [
        "README.md",
        "NOTICE.md",
        "SECURITY.md",
        "LICENSE",
        ".env.example",
        "docs/USER_MANUAL_STAGE0A_TO_STAGE5.md",
        "docs/direct-user-interface-and-deployment-path.md",
        "docs/evidence-led-validation-architecture-2026-05-03.md",
        "docs/stage3-graphify-evidence-graph-2026-05-02.md",
    ]
    for name in required:
        if not (ROOT / name).exists():
            failures.append(f"Missing required publication file: {name}")
    readme = ROOT / "README.md"
    notice = ROOT / "NOTICE.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        for needle in ("TauricResearch", "TradingAgents", "Titan OS 2.9", "Titan DTP 1.6", "Apache-2.0", "not financial advice"):
            if needle.lower() not in text.lower():
                failures.append(f"README.md missing required wording: {needle}")
    if notice.exists():
        text = notice.read_text(encoding="utf-8")
        for needle in ("TauricResearch", "TradingAgents", "arXiv", "Apache-2.0", "independent"):
            if needle.lower() not in text.lower():
                failures.append(f"NOTICE.md missing required wording: {needle}")
    return failures


def _check_gitignore_guards() -> list[str]:
    path = ROOT / ".gitignore"
    if not path.exists():
        return ["Missing .gitignore"]
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern not in text:
            failures.append(f".gitignore missing required publication guard: {pattern}")
    return failures


def _is_blocked(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True
    return bool(rel.parts and rel.parts[0] in BLOCKED_DIRS)


def _is_runtime_noise(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if "__pycache__" in rel.parts:
        return True
    return path.suffix.lower() in {".pyc", ".pyo", ".log", ".tmp"}


if __name__ == "__main__":
    raise SystemExit(main())
