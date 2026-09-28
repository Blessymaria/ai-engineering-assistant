"""Order service."""
import json

from shop.db.repo import OrderRepo


def validate(payload):
    if not payload:
        raise ValueError("empty order")


def create_order(payload):
    """Validate and save an order."""
    validate(payload)
    repo = OrderRepo()
    repo.save(payload)
    notifier(payload)
    return json.dumps(payload)


def load_order(repo, order_id):
    return repo.get(order_id)
