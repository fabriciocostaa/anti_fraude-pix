from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from utils.income import INCOME_BY_LABEL

POLICY_VERSION = "pix-mvp-v1"
BRASILIA = timezone(timedelta(hours=-3))
PROFILE_COUNT = 10
PROFILE_DAYS = 3
FACTOR = 3
RELEVANT_AMOUNT = 100000


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Fraction(ordered[middle])
    return Fraction(ordered[middle - 1] + ordered[middle], 2)


def evaluate(payload, history, declared_income, marker, now):
    amount = payload["amount"]
    transaction_date = datetime.fromisoformat(payload["transaction_date"]).astimezone(BRASILIA)
    source = payload["source_account"]
    destination = payload["destination_account"]
    approved = [row for row in history if row["status"] == "approved"]
    today = now.astimezone(BRASILIA).date()
    active_days = {row["received_at"].astimezone(BRASILIA).date() for row in approved}
    profile_ready = len(approved) >= PROFILE_COUNT and len(active_days) >= PROFILE_DAYS
    daily_totals = defaultdict(int)
    for row in approved:
        daily_totals[row["received_at"].astimezone(BRASILIA).date()] += row["amount"]
    day_total = daily_totals.get(today, 0)
    count = 1 + sum(row["received_at"] >= now - timedelta(seconds=60) for row in history)
    income_band = INCOME_BY_LABEL.get(declared_income)
    if profile_ready:
        full_days = [total for day, total in daily_totals.items() if today - timedelta(days=30) < day < today]
        reference = {"mode": "history", "amount_threshold": int(FACTOR * median([r["amount"] for r in approved])),
                     "daily_threshold": int(FACTOR * median(full_days))}
    elif income_band:
        # Na faixa aberta, o piso e referencia conservadora; nao e renda exata.
        basis = income_band["upper_cents"] or income_band["lower_cents"]
        reference = {"mode": "income", "income_reference": basis,
                     "open_income_band": income_band["upper_cents"] is None,
                     "amount_threshold": FACTOR * basis, "daily_threshold": FACTOR * basis}
    else:
        reference = {"mode": "initial", "amount_threshold": 500000, "daily_threshold": 2000000}
    metadata = {
        "policy_version": POLICY_VERSION,
        "reference": reference,
        "history": {"approved_observations": len(approved), "active_days": len(active_days),
                    "profile_ready": profile_ready, "profile_comparison": "evaluated" if profile_ready else "not_applicable"},
        "velocity": {"count": count, "window_seconds": 60},
        "daily_approved_amount": day_total,
    }

    def decision(status, rule, evidence):
        return status, {**metadata, "matched_rule": rule, "evidence": evidence}

    if marker and marker["status"] == "REGISTERED" and marker["fraud_type"] == "MULE_ACCOUNT":
        return decision("rejected", "active_mule_receiver", marker)

    bank_limit = payload.get("limit_context")
    period = "night" if transaction_date.hour >= 20 or transaction_date.hour < 6 else "day"
    if bank_limit:
        limit, used = bank_limit["limit_amount"], bank_limit["used_amount"]
        period, limit_source = bank_limit["period"], "bank_context"
    elif period == "night" and len(source["owner"]["document_number"]) == 11 and len(destination["owner"]["document_number"]) == 11:
        start = transaction_date.replace(hour=20, minute=0, second=0, microsecond=0)
        if transaction_date.hour < 6:
            start -= timedelta(days=1)
        end = start + timedelta(hours=10)
        used = sum(row["amount"] for row in approved
                   if row["source_branch"] == source["branch"] and row["source_account_number"] == source["account_number"]
                   and len(row["destination_document"]) == 11 and start <= row["transaction_date"] < end)
        limit, limit_source = 100000, "mvp_observed_history"
    else:
        limit, used, limit_source = None, 0, "not_provided"
    metadata["period_limit"] = {"period": period, "limit_amount": limit, "used_amount": used, "source": limit_source}
    if limit is not None and used + amount > limit:
        return decision("rejected", "period_limit", {"amount": amount, "used_amount": used, "limit_amount": limit})
    if count >= 10:
        return decision("rejected", "extreme_velocity", {"count": count, "threshold": 10})
    if count >= 5:
        return decision("two_factor_required", "elevated_velocity", {"count": count, "threshold": 5})
    atypical = amount >= reference["amount_threshold"] if reference["mode"] == "initial" else amount >= RELEVANT_AMOUNT and amount > reference["amount_threshold"]
    if atypical:
        return decision("two_factor_required", "atypical_amount", {"amount": amount, "threshold": reference["amount_threshold"]})
    if day_total + amount > reference["daily_threshold"]:
        return decision("two_factor_required", "daily_accumulated_amount", {"amount_including_current": day_total + amount, "threshold": reference["daily_threshold"]})
    if profile_ready and amount >= RELEVANT_AMOUNT:
        device_known = any(row["device_id"] == payload["source"]["device_id"] for row in approved)
        receiver_known = any(row["destination_document"] == destination["owner"]["document_number"] for row in approved)
        if not device_known and not receiver_known:
            return decision("two_factor_required", "new_context", {"device_observed": False, "receiver_observed": False})
    age = transaction_date - datetime.fromisoformat(destination["opening_date"])
    if timedelta(0) <= age < timedelta(days=7) and amount >= RELEVANT_AMOUNT:
        return decision("two_factor_required", "recent_receiver_account", {"account_age_days": age.days, "amount": amount})
    return decision("approved", "all_rules_passed", {})
