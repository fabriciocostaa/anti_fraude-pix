from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers.pix_transaction_controller import PixTransactionController
from utils.schema_handler import SchemaHandler

class PixTransactionResource:
    """
    A porta de entrada HTTP para o motor de decisão do Antifraude Pix.
    """

    @SchemaHandler.validate("post_pix_transaction.json")
    def on_post(self, payload: dict) -> JSONResponse:
        """
        Recebe o pedido de Pix, aplica o motor de regras e responde com a decisão[cite: 12, 18, 29].
        """
        controller = PixTransactionController()
        decision = controller.process_transaction(payload)

        # O endpoint devolve o status da análise (approved, rejected, two_factor_required)[cite: 21, 33]
        return JSONResponse(
            content=jsonable_encoder(decision),
            status_code=http_status.HTTP_200_OK,
        )

    def on_get_by_id(self, pix_id: str) -> JSONResponse:
        """
        Devolve a análise que foi gravada no banco através do ID do Pix[cite: 21, 33].
        """
        controller = PixTransactionController()
        transaction = controller.get_by_pix_id(pix_id)

        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_200_OK,
        )