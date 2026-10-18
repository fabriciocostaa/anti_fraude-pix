from uuid import UUID, uuid4


class TestPixTransactionGet:
    def test_get_existing_pix_transaction(self, payload, post, get):
        body = payload()
        created = post(body)
        assert set(created) == {"key", "status", "metadata"}
        UUID(created["key"])
        assert get(body["id"]) == created

    def test_unknown_pix_is_not_found(self, get):
        assert get(f"missing-{uuid4()}", expected=404)["code"] == "PIX000001"

