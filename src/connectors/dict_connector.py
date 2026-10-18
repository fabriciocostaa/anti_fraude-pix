import requests
from connectors.rest_connector import RestConnector
from constants import DICT_API_URL, EXTERNAL_TIMEOUT, INTERNAL_TOKEN
from errors.pix_errors import DependencyUnavailable


class DictConnector(RestConnector):
    def __init__(self):
        super().__init__(__name__, DICT_API_URL, EXTERNAL_TIMEOUT, INTERNAL_TOKEN)

    def get_fraud_marker(self, document):
        try:
            response = self.send(f"/fraud-markers/{document}", "GET")
        except requests.RequestException:
            raise DependencyUnavailable("dict_mock") from None
        data = response.json
        if response.status != 200 or not isinstance(data, dict) or "fraud_marker" not in data:
            raise DependencyUnavailable("dict_mock")
        marker = data["fraud_marker"]
        if marker is None:
            return None
        if (not isinstance(marker, dict) or str(marker.get("tax_id_number")) != str(document)
                or marker.get("status") not in {"REGISTERED", "CANCELLED"}
                or marker.get("fraud_type") not in {"MULE_ACCOUNT", "APPLICATION_FRAUD", "SCAMMER_ACCOUNT", "OTHER", "UNKNOWN"}):
            raise DependencyUnavailable("dict_mock")
        return {"tax_id_number": str(marker["tax_id_number"]), "status": marker["status"], "fraud_type": marker["fraud_type"]}
