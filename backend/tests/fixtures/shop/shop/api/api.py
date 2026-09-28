from fastapi import APIRouter

from shop.api import routes as order_routes

router = APIRouter()
router.include_router(order_routes.router, prefix="/shop")
