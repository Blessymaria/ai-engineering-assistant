from fastapi import APIRouter, Depends

import shop
from shop.services import orders
from shop.services.orders import create_order
from ..db.repo import OrderRepo

router = APIRouter(prefix="/v1")


@router.post("/orders")
def post_order(payload: dict):
    """Create an order."""
    return create_order(payload)


@router.get("/orders/{order_id}")
async def get_order(order_id: int, repo=Depends(OrderRepo)):
    return orders.load_order(repo, order_id)


def via_package(payload):
    return shop.create_order(payload)
