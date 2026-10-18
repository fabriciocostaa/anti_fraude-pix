import re


def _to_cents(raw: str) -> int:
    cleaned = raw.replace(".", "")
    if "," in cleaned:
        reais, cents = cleaned.split(",", 1)
        return int(reais) * 100 + int((cents + "00")[:2])
    return int(cleaned) * 100


def parse_income_band(label):
    if not isinstance(label, str) or not label.strip():
        return None
    numbers = [_to_cents(match) for match in re.findall(r"\d+(?:\.\d{3})*(?:,\d{1,2})?", label)]
    if not numbers:
        return None
    if len(numbers) >= 2:
        return {"lower_cents": numbers[0], "upper_cents": numbers[1]}
    if "até" in label.lower() or "ate" in label.lower():
        return {"lower_cents": 0, "upper_cents": numbers[0]}
    return {"lower_cents": numbers[0], "upper_cents": None}
