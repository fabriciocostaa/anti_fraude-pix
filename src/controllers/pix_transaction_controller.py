import uuid
from datetime import datetime
from controllers.base_controller import BaseController

class PixTransactionController(BaseController):
    def __init__(self, repository):
        self.repository = repository # O seu repositório para fazer queries à base de dados

    def process_transaction(self, payload: dict) -> dict:
        # Extração de dados cruciais do payload de entrada
        amount = payload.get("amount", 0)
        source_doc = payload["source_account"]["owner"]["document_number"]
        dest_doc = payload["destination_account"]["owner"]["document_number"]
        
        # O desafio exige um identificador único para a análise[cite: 21, 33]
        analysis_key = str(uuid.uuid4())
        
        status = "approved"
        reasons = []

        # REGRA 1: Limite por transação (ex: bloqueia acima de R$ 50.000 / 5.000.000 centavos)[cite: 15, 30]
        if amount > 5000000:
            status = "rejected"
            reasons.append("amount_exceeds_maximum_limit")
            
        # REGRA 2: Risco moderado / Valor alto pede 2FA (ex: acima de R$ 10.000 / 1.000.000 centavos)[cite: 15, 16, 30]
        elif amount > 1000000:
            status = "two_factor_required"
            reasons.append("high_value_transaction")

        # REGRA 3: Velocity ou Montante (Exemplo conceptual)[cite: 15, 30]
        # total_hoje = self.repository.get_daily_sum(source_doc)
        # if total_hoje + amount > LIMITE_DIARIO:
        #     status = "rejected"

        # REGRA 4: Auto-transferência suspeita ou de baixo risco
        if source_doc == dest_doc:
            status = "approved"
            reasons.append("same_ownership_transfer")

        metadata = {"reasons": reasons, "processed_at": datetime.utcnow().isoformat()}

        # Aqui deve inserir a lógica para guardar na base de dados (persistência)
        # self.repository.save(analysis_key, payload, status, amount, ...)

        # Retorna os 3 campos obrigatórios definidos no contrato de saída[cite: 21, 33]
        return {
            "key": analysis_key,
            "status": status,
            "metadata": metadata
        }