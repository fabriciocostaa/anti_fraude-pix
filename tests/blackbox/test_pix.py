from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
import requests


def test_health_and_authentication(api_url, payload):
    assert requests.get(f"{api_url}/health_check", timeout=5).status_code == 204
    assert requests.post(f"{api_url}/pix/transaction", json=payload(), timeout=5).status_code == 403


def test_post_get_replay_and_conflict(payload, post, get):
    body = payload()
    first = post(body)
    assert set(first) == {"key", "status", "metadata"}
    UUID(first["key"])
    assert first["status"] == "approved"
    assert get(body["id"]) == first
    assert post(body) == first
    assert post({**body, "amount": body["amount"] + 1}, expected=409)["code"] == "PIX000002"
    assert get(body["id"]) == first


def test_unknown_pix_is_not_found(get):
    assert get(f"missing-{uuid4()}", expected=404)["code"] == "PIX000001"


def test_income_is_reused_and_dict_is_queried_for_each_new_pix(document, payload, post, headers):
    payer, receiver = document(), document("00")
    first = post(payload(source=payer, destination=receiver))
    second = post(payload(source=payer, destination=receiver))
    assert first["metadata"]["income"]["source"] == "serasa_mock"
    assert second["metadata"]["income"]["source"] == "stored"
    assert first["metadata"]["income"]["declared_income"] == "Mais de R$ 2500,00 a R$ 3000,00"
    for provider, doc, count, port in [("SERASA", payer, 1, 8001), ("DICT", receiver, 2, 8002)]:
        import os
        base_url = os.getenv(f"{provider}_MOCK_URL", f"http://127.0.0.1:{port}")
        response = requests.get(f"{base_url}/calls/{doc}", headers=headers, timeout=5)
        assert response.status_code == 200
        assert response.json()["calls"] == count


def test_income_changes_the_initial_reference(document, payload, post):
    low = post(payload(amount=1500000, source=document("04")))
    high = post(payload(amount=1500000, source=document("14")))
    assert low["status"] == "two_factor_required"
    assert low["metadata"]["matched_rule"] == "atypical_amount"
    assert high["status"] == "approved"
    assert high["metadata"]["reference"]["mode"] == "income"


@pytest.mark.parametrize("suffix,expected", [("01", "rejected"), ("02", "approved"), ("00", "approved")])
def test_dict_active_mule_cancelled_and_no_marker(document, payload, post, get, suffix, expected):
    body = payload(destination=document(suffix))
    result = post(body)
    assert result["status"] == expected
    assert get(body["id"]) == result
    if expected == "rejected":
        assert result["metadata"]["matched_rule"] == "active_mule_receiver"


def test_income_is_reused_even_after_a_rejection(document, payload, post):
    payer = document("14")
    assert post(payload(source=payer, destination=document("01")))["status"] == "rejected"
    result = post(payload(source=payer))
    assert result["status"] == "approved"
    assert result["metadata"]["income"]["source"] == "stored"


@pytest.mark.parametrize("suffix", ["99", "98", "97"])
def test_dict_error_mismatch_and_invalid_marker_are_not_clean(document, payload, post, get, suffix):
    body = payload(destination=document(suffix))
    assert post(body, expected=503)["code"] == "PIX000003"
    get(body["id"], expected=404)


def test_missing_income_uses_initial_policy(document, payload, post):
    result = post(payload(amount=500000, source=document("98")))
    assert result["status"] == "two_factor_required"
    assert result["metadata"]["reference"]["mode"] == "initial"


@pytest.mark.parametrize("hour,amount,expected", [(2, 100001, "rejected"), (20, 100001, "rejected"), (5, 100000, "approved"), (6, 100001, "approved"), (19, 100001, "approved")])
def test_night_boundaries(payload, post, hour, amount, expected):
    assert post(payload(hour=hour, amount=amount))["status"] == expected


def test_night_total_includes_other_receivers(document, payload, post):
    payer = document()
    assert post(payload(hour=2, amount=60000, source=payer))["status"] == "approved"
    result = post(payload(hour=2, amount=50000, source=payer))
    assert result["status"] == "rejected"
    assert result["metadata"]["matched_rule"] == "period_limit"


def test_bank_limit_context_and_pj_receiver(document, payload, post):
    body = payload(hour=2, amount=200000, limit_context={"period": "night", "limit_amount": 500000, "used_amount": 100000})
    assert post(body)["status"] == "approved"
    assert post(payload(hour=2, amount=150000, destination=f"123{document('00')}"))["status"] == "approved"


def test_night_period_crosses_midnight(document, payload, post):
    payer = document()
    first = payload(hour=2, amount=60000, source=payer)
    first["transaction_date"] = (datetime.fromisoformat(first["transaction_date"]) - timedelta(hours=3)).isoformat()
    assert post(first)["status"] == "approved"
    assert post(payload(hour=2, amount=50000, source=payer))["status"] == "rejected"


def test_high_income_never_overrides_active_mule(document, payload, post):
    result = post(payload(amount=1500000, source=document("14"), destination=document("01")))
    assert result["status"] == "rejected"
    assert result["metadata"]["matched_rule"] == "active_mule_receiver"


def test_same_owner_never_overrides_rejection(document, payload, post):
    owner = document("04")
    assert post(payload(hour=2, amount=100001, source=owner, destination=owner))["status"] == "rejected"


def test_velocity_and_replay(document, payload, post):
    payer = document()
    body = payload(source=payer)
    first = post(body)
    for _ in range(5):
        assert post(body) == first
    results = [first] + [post(payload(source=payer)) for _ in range(9)]
    assert [r["status"] for r in results] == ["approved"] * 4 + ["two_factor_required"] * 5 + ["rejected"]


def test_concurrent_replay_has_one_result(payload, post):
    body = payload()
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: post(body), range(5)))
    assert all(result == results[0] for result in results)


def test_concurrent_same_payer_respects_velocity(document, payload, post):
    payer = document()
    bodies = [payload(source=payer) for _ in range(10)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(post, bodies))
    statuses = [r["status"] for r in results]
    assert statuses.count("approved") == 4
    assert statuses.count("two_factor_required") == 5
    assert statuses.count("rejected") == 1


def test_recent_destination_account(payload, post):
    body = payload(amount=100000)
    date = datetime.fromisoformat(body["transaction_date"])
    body["destination_account"]["opening_date"] = (date - timedelta(days=2)).isoformat()
    result = post(body)
    assert result["status"] == "two_factor_required"
    assert result["metadata"]["matched_rule"] == "recent_receiver_account"


@pytest.mark.parametrize("change", [{"amount": 0}, {"amount": True}, {"amount": -1}, {"amount": 9223372036854775808}, {"transaction_date": "invalid"}, {"transaction_date": "2026-01-01T12:00:00"}, {"extra": "unknown"}])
def test_invalid_input_is_not_persisted(payload, post, get, change):
    body = payload(**change)
    post(body, expected=400)
    get(body["id"], expected=404)


def test_optional_geolocation_and_document_normalization(payload, post):
    body = payload()
    doc = body["source_account"]["owner"]["document_number"]
    body["source_account"]["owner"]["document_number"] = f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    first = post(body)
    equivalent = deepcopy(body)
    equivalent["source_account"]["owner"]["document_number"] = doc
    assert post(equivalent) == first
    body = payload()
    body["source"]["geolocation"] = {"latitude": -23.56}
    post(body, expected=400)
