"""DeepSeek model ID normalization for operational model switching."""

from __future__ import annotations

DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
DEEPSEEK_V4_PRO = "deepseek-v4-pro"

DEEPSEEK_MODEL_ALIASES = {
    "flash": DEEPSEEK_V4_FLASH,
    "v4-flash": DEEPSEEK_V4_FLASH,
    DEEPSEEK_V4_FLASH: DEEPSEEK_V4_FLASH,
    # Deprecated compatibility names documented by DeepSeek.
    "deepseek-chat": DEEPSEEK_V4_FLASH,
    "deepseek-reasoner": DEEPSEEK_V4_FLASH,
    "reasoner": DEEPSEEK_V4_FLASH,
    "pro": DEEPSEEK_V4_PRO,
    "v4-pro": DEEPSEEK_V4_PRO,
    DEEPSEEK_V4_PRO: DEEPSEEK_V4_PRO,
    # Operator convenience aliases. The official API model is deepseek-v4-pro.
    "pro-max": DEEPSEEK_V4_PRO,
    "promax": DEEPSEEK_V4_PRO,
    "deepseek-v4-pro-max": DEEPSEEK_V4_PRO,
    "deepseek-v4-promax": DEEPSEEK_V4_PRO,
}


def normalize_deepseek_model(value: str | None) -> str:
    if not value:
        return DEEPSEEK_V4_FLASH
    key = value.strip().lower()
    return DEEPSEEK_MODEL_ALIASES.get(key, value.strip())


def deepseek_model_note(*values: str | None) -> str:
    normalized = [normalize_deepseek_model(value) for value in values if value]
    originals = {str(value).strip().lower() for value in values if value}
    notes = []
    if originals.intersection({"pro-max", "promax", "deepseek-v4-pro-max", "deepseek-v4-promax"}):
        notes.append("Pro-Max alias normalized to official DeepSeek model ID deepseek-v4-pro.")
    if originals.intersection({"deepseek-chat", "deepseek-reasoner"}):
        notes.append("Deprecated DeepSeek compatibility alias normalized to deepseek-v4-flash.")
    if any(model not in {DEEPSEEK_V4_FLASH, DEEPSEEK_V4_PRO} for model in normalized):
        notes.append("Custom DeepSeek model ID supplied by operator.")
    return " ".join(notes) or "official DeepSeek V4 model ID"
