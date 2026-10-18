from copy import deepcopy
from models import PixTransaction


class PixTransactionDTO:
    @staticmethod
    def to_dict(transaction: PixTransaction) -> dict:
        return {
            "key": str(transaction.analysis_key),
            "status": transaction.status.enumerator,
            "metadata": deepcopy(transaction.analysis_metadata),
        }
