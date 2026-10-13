"""Bounded, command-accessible Sonic-only diagnostic history.

Routine native scanner/transport log records are *not* sent to the client's
console. Errors and urgent warnings intentionally retain their normal logger
paths: hiding a failed/uncertain AP delivery would be unsafe.

This module does not add a global logging filter, so Archipelago's own chat,
connection and item notifications continue to work normally.
"""

from collections import deque
from datetime import datetime, timezone


_HISTORY_LIMIT = 500
_recent = deque(maxlen=_HISTORY_LIMIT)


def record(category, message, *args):
    """Capture a routine diagnostic without writing it to the GUI/console."""
    try:
        rendered = message % args if args else str(message)
    except (TypeError, ValueError):
        rendered = f'{message} {args!r}'
    # Frequent identical status transitions would crowd out interesting events.
    if _recent and _recent[-1]['category'] == category and _recent[-1]['message'] == rendered:
        _recent[-1]['repeats'] = _recent[-1].get('repeats', 1) + 1
        _recent[-1]['last_time_utc'] = datetime.now(timezone.utc).isoformat()
        return
    _recent.append({
        'time_utc': datetime.now(timezone.utc).isoformat(),
        'category': category,
        'message': rendered,
    })


def history(limit=25):
    """Copy recent entries; never reveal mutable internal deque state."""
    if limit is None:
        entries = list(_recent)
    else:
        entries = list(_recent)[-limit:] if limit else []
    return {'stored': len(_recent), 'capacity': _HISTORY_LIMIT,
            'showing': len(entries), 'entries': [dict(entry) for entry in entries]}


def clear():
    count = len(_recent)
    _recent.clear()
    return count
