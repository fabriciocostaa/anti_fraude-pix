from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID

import pytest

from tests.integration.pix_transaction.conftest import MULE_DOCUMENT


class TestPixTransactionCreate:
    def test_post_replay_and_conflict(self, payload, post, get):
        body = payload()
        first = post(body)
        assert set(first) == {"key", "status", "metadata"}
        UUID(first["key"])
        assert first["status"] == "approved"
        assert get(body["id"]) == first
        assert post(body) == first
        assert post({**body, "amount": body["amount"] + 1}, expected=409)["code"] == "PIX000002"
        assert get(body["id"]) == first

    def test_income_is_reused_and_dict_is_queried_for_each_new_pix(self, document, payload, post):
        payer, receiver = document(), document("00")
        first = post(payload(source=payer, destination=receiver))
        second = post(payload(source=payer, destination=receiver))
        assert first["metadata"]["income"]["source"] == "serasa_mock"
        assert second["metadata"]["income"]["source"] == "stored"
        assert first["metadata"]["income"]["declared_income"] == "Mais de R$ 2500,00 a R$ 3000,00"
        assert first["metadata"]["income"]["consulted_at"] == second["metadata"]["income"]["consulted_at"]
        assert first["metadata"]["dict"]["queried_at"] != second["metadata"]["dict"]["queried_at"]

    def test_income_threshold_evaluation(self, document, payload, post):
        within_threshold = post(payload(amount=800000, source=document()))
        above_threshold = post(payload(amount=1500000, source=document()))
        assert within_threshold["status"] == "approved"
        assert within_threshold["metadata"]["reference"]["mode"] == "income"
        assert above_threshold["status"] == "two_factor_required"
        assert above_threshold["metadata"]["matched_rule"] == "atypical_amount"

    def test_dict_active_mule_and_normal_receiver(self, document, payload, post, get):
        mule_body = payload(destination=MULE_DOCUMENT)
        mule_result = post(mule_body)
        assert mule_result["status"] == "rejected"
        assert mule_result["metadata"]["matched_rule"] == "active_mule_receiver"
        assert get(mule_body["id"]) == mule_result

        clean_body = payload(destination=document("00"))
        clean_result = post(clean_body)
        assert clean_result["status"] == "approved"
        assert get(clean_body["id"]) == clean_result

    def test_income_is_reused_even_after_a_rejection(self, document, payload, post):
        payer = document()
        assert post(payload(source=payer, destination=MULE_DOCUMENT))["status"] == "rejected"
        result = post(payload(source=payer))
        assert result["status"] == "approved"
        assert result["metadata"]["income"]["source"] == "stored"

    @pytest.mark.parametrize(
        "hour,amount,expected",
        [
            (2, 100001, "rejected"),
            (20, 100001, "rejected"),
            (5, 100000, "approved"),
            (6, 100001, "approved"),
            (19, 100001, "approved"),
        ],
    )
    def test_night_boundaries(self, payload, post, hour, amount, expected):
        assert post(payload(hour=hour, amount=amount))["status"] == expected

    def test_night_total_includes_other_receivers(self, document, payload, post):
        payer = document()
        assert post(payload(hour=2, amount=60000, source=payer))["status"] == "approved"
        result = post(payload(hour=2, amount=50000, source=payer))
        assert result["status"] == "rejected"
        assert result["metadata"]["matched_rule"] == "period_limit"

    def test_bank_limit_context_and_pj_receiver(self, document, payload, post):
        body = payload(
            hour=2,
            amount=200000,
            limit_context={"period": "night", "limit_amount": 500000, "used_amount": 100000},
        )
        assert post(body)["status"] == "approved"
        assert post(payload(hour=2, amount=150000, destination=f"123{document('00')}"))["status"] == "approved"

    def test_night_period_crosses_midnight(self, document, payload, post):
        payer = document()
        first = payload(hour=2, amount=60000, source=payer)
        first["transaction_date"] = (datetime.fromisoformat(first["transaction_date"]) - timedelta(hours=3)).isoformat()
        assert post(first)["status"] == "approved"
        assert post(payload(hour=2, amount=50000, source=payer))["status"] == "rejected"

    def test_active_mule_is_never_overridden(self, document, payload, post):
        result = post(payload(amount=10000, source=document(), destination=MULE_DOCUMENT))
        assert result["status"] == "rejected"
        assert result["metadata"]["matched_rule"] == "active_mule_receiver"

    def test_same_owner_never_overrides_rejection(self, document, payload, post):
        owner = document("04")
        assert post(payload(hour=2, amount=100001, source=owner, destination=owner))["status"] == "rejected"

    def test_velocity_and_replay(self, document, payload, post):
        payer = document()
        body = payload(source=payer)
        first = post(body)
        for _ in range(5):
            assert post(body) == first
        results = [first] + [post(payload(source=payer)) for _ in range(9)]
        assert [r["status"] for r in results] == ["approved"] * 4 + ["two_factor_required"] * 5 + ["rejected"]

    def test_concurrent_replay_has_one_result(self, payload, post):
        body = payload()
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: post(body), range(5)))
        assert all(result == results[0] for result in results)

    def test_concurrent_same_payer_respects_velocity(self, document, payload, post):
        payer = document()
        bodies = [payload(source=payer) for _ in range(10)]
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(post, bodies))
        statuses = [r["status"] for r in results]
        assert statuses.count("approved") == 4
        assert statuses.count("two_factor_required") == 5
        assert statuses.count("rejected") == 1

    def test_recent_destination_account(self, payload, post):
        body = payload(amount=100000)
        date = datetime.fromisoformat(body["transaction_date"])
        body["destination_account"]["opening_date"] = (date - timedelta(days=2)).isoformat()
        result = post(body)
        assert result["status"] == "two_factor_required"
        assert result["metadata"]["matched_rule"] == "recent_receiver_account"

    @pytest.mark.parametrize(
        "change",
        [
            {"amount": 0},
            {"amount": True},
            {"amount": -1},
            {"amount": 9223372036854775808},
            {"transaction_date": "invalid"},
            {"transaction_date": "2026-01-01T12:00:00"},
            {"extra": "unknown"},
        ],
    )
    def test_invalid_input_is_not_persisted(self, payload, post, get, change):
        body = payload(**change)
        post(body, expected=400)
        get(body["id"], expected=404)

    def test_optional_geolocation_and_document_normalization(self, payload, post):
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

