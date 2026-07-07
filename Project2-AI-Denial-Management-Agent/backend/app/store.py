from app.models import ReviewItem

_review_items: dict[str, ReviewItem] = {}


def save(item: ReviewItem) -> None:
    _review_items[item.id] = item


def get(item_id: str) -> ReviewItem | None:
    return _review_items.get(item_id)


def list_all() -> list[ReviewItem]:
    return list(_review_items.values())
