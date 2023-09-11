from typing import Callable, List


def get_item(row: dict, name: str = 'Name') -> dict:
    """This is the default get item function. It requires at least that Name
    is a key in the row data."""
    row['name'] = row.pop(name)
    return row


def get_state(
        type_name: str,
        rows: List[dict],
        on_item: Callable[[dict], dict] = get_item) -> dict:
    """Default get_state function."""
    return {type_name: [on_item(itm) for itm in rows]}
