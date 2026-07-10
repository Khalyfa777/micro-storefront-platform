from uuid import UUID
from pydantic import BaseModel


class PaymentInitializeRequest(BaseModel):
    order_id: UUID
    customer_email: str | None = None


class PaymentInitializeResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str
