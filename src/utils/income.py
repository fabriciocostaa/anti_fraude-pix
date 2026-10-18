import json
from pathlib import Path

INCOME_RANGES = json.loads((Path(__file__).resolve().parents[1] / "income_ranges.json").read_text(encoding="utf-8"))
INCOME_BY_LABEL = {item["label"]: item for item in INCOME_RANGES}
