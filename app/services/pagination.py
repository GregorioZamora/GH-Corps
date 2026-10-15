from math import ceil


def paginate(total: int, page: int, per_page: int = 10):
    """Return a pagination dict for templates.

    - page: 1-based current page (clamped to valid range).
    - total_pages, has_prev, has_next, prev_page, next_page.
    """
    if per_page < 1:
        per_page = 10
    total_pages = max(1, ceil(total / per_page))
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    return {
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "total": total,
    }