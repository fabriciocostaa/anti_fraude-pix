class PixTransactionDTO:
    @staticmethod
    def to_dict(transaction):
        return {"key": str(transaction.analysis_key), "status": transaction.status.enumerator, "metadata": transaction.decision_metadata}
