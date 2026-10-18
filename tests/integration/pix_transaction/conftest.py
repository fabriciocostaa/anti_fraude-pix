import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

MULE_DOCUMENT = "12345678901"


@pytest.fixture
def api_url():
    return os.getenv("API_URL", f"http://127.0.0.1:{os.getenv('API_PORT', '3000')}").rstrip("/")


@pytest.fixture
def headers():
    return {"INTERNAL-TOKEN": os.getenv("INTERNAL_TOKEN", "default_token")}


@pytest.fixture
def document():
    def make(suffix="04"):
        return f"{uuid.uuid4().int % 10**9:09d}{suffix}"
    return make


@pytest.fixture
def payload(document):
    def make(amount=10000, source=None, destination=None, hour=12, **changes):
        now = datetime.now(timezone(timedelta(hours=-3))).replace(hour=hour, minute=0, second=0, microsecond=0)
        body = {
            "id": f"pix-{uuid.uuid4()}",
            "amount": amount,
            "transaction_date": now.isoformat(),
            "source_account": {
                "branch": "0001",
                "account_number": "88213",
                "opening_date": "2010-01-01T00:00:00-03:00",
                "owner": {"document_number": source or document()},
            },
            "destination_account": {
                "participant": "60701190",
                "branch": "3675",
                "account_number": "10442",
                "opening_date": "2010-01-01T00:00:00-03:00",
                "owner": {"document_number": destination or document("00")},
            },
            "source": {"device_id": "test-device", "channel": "app", "ip": "198.51.100.23"},
        }
        body.update(changes)
        return body
    return make


@pytest.fixture
def post(api_url, headers):
    def send(body, expected=200):
        response = requests.post(f"{api_url}/pix/transaction", json=body, headers=headers, timeout=15)
        assert response.status_code == expected, response.text
        return response.json()
    return send


@pytest.fixture
def get(api_url, headers):
    def send(pix_id, expected=200):
        response = requests.get(f"{api_url}/pix/transaction/{pix_id}", headers=headers, timeout=15)
        assert response.status_code == expected, response.text
        return response.json()
    return send

