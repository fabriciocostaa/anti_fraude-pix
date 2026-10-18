import copy
import hashlib
import ipaddress
import json
import re
from datetime import datetime, timezone
from errors.base_error import InvalidSchema


def normalize_payload(payload):
    normalized = copy.deepcopy(payload)
    try:
        json.dumps(payload, allow_nan=False)
        for account_name in ("source_account", "destination_account"):
            account = normalized[account_name]
            account["branch"] = account["branch"].strip()
            account["account_number"] = account["account_number"].strip()
            doc = re.sub(r"[.\-/\s]", "", account["owner"]["document_number"]).upper()
            if not re.fullmatch(r"[0-9]{11}|[A-Z0-9]{12}[0-9]{2}", doc):
                raise ValueError("document_number must identify a CPF or CNPJ")
            account["owner"]["document_number"] = doc
        for container, key in [(normalized, "transaction_date"), (normalized["source_account"], "opening_date"), (normalized["destination_account"], "opening_date")]:
            date = datetime.fromisoformat(container[key].replace("Z", "+00:00"))
            if date.utcoffset() is None:
                raise ValueError(f"{key} requires an explicit timezone")
            container[key] = date.astimezone(timezone.utc).isoformat()
        transaction_date = datetime.fromisoformat(normalized["transaction_date"])
        for account_name in ("source_account", "destination_account"):
            if datetime.fromisoformat(normalized[account_name]["opening_date"]) > transaction_date:
                raise ValueError("account opening_date cannot follow transaction_date")
        normalized["amount"] = int(normalized["amount"])
        normalized["source"]["ip"] = ipaddress.ip_address(normalized["source"]["ip"]).compressed
        if "geolocation" in normalized["source"]:
            normalized["source"]["geolocation"] = {k: float(v) for k, v in normalized["source"]["geolocation"].items()}
        canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as error:
        raise InvalidSchema(str(error)) from None
    return normalized, hashlib.sha256(canonical.encode("utf-8")).hexdigest()
