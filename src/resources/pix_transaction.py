from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers.pix_transaction_controller import PixTransactionController
from utils.schema_handler import SchemaHandler

class PixTransactionResource:

    @SchemaHandler.validate("post_pix_transaction.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = PixTransactionController()
        decision = controller.process_transaction(payload)

        return JSONResponse(
            content=jsonable_encoder(decision),
            status_code=http_status.HTTP_200_OK,
        )

    def on_get_by_id(self, pix_id: str) -> JSONResponse:
        controller = PixTransactionController()
        transaction = controller.get_by_pix_id(pix_id)

        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_200_OK,
        )