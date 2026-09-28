class BaseRepo:
    def get(self, key):
        return self._fetch(key)

    def _fetch(self, key):
        return key


class OrderRepo(BaseRepo):
    """Stores orders."""

    def save(self, item):
        return self.get(item)


class UserRepo(BaseRepo):
    def save(self, item):
        return item
