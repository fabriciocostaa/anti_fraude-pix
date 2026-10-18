import requests
from connectors.rest_connector import RestConnector
from constants import SERASA_API_URL, EXTERNAL_TIMEOUT, INTERNAL_TOKEN
from utils.income import INCOME_BY_LABEL


class SerasaConnector(RestConnector):
    def __init__(self):
        super().__init__(__name__, SERASA_API_URL, EXTERNAL_TIMEOUT, INTERNAL_TOKEN)

    def get_income(self, document):
        try:
            response = self.send(f"/income/{document}", "GET")
        except requests.RequestException:
            return None
        if response.status != 200 or not isinstance(response.json, dict):
            return None
        label = response.json.get("income")
        return label if isinstance(label, str) and label in INCOME_BY_LABEL else None
