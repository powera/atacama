"""Message utility functions for retrieving message and quote relationships."""

from typing import List

from models.database import db
from models import Email


def get_parent_chain_ids(message_id: int) -> List[int]:
    """
    Get IDs of all parent messages in the chain for a given message ID.
    Includes the input message ID in the returned list.

    :param message_id: ID of message to get parents for
    :return: List of message IDs in parent chain, ordered from oldest to newest
    """
    ids = []

    with db.session() as session:
        current = session.query(Email).get(message_id)
        if not current:
            return []

        # Add the target message ID first
        ids.append(message_id)

        # Walk up parent chain
        while current.parent_id:
            ids.append(current.parent_id)
            current = session.query(Email).get(current.parent_id)

    # Return in chronological order (oldest first)
    return list(reversed(ids))
