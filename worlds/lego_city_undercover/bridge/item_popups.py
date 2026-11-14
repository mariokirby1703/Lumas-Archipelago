"""Receipt notifications, independent of grants and native save verification."""
import asyncio
from collections import deque
import logging
import re
import struct
import time
from native_model_transport import NativePlayerBusy, _policy_command
from native_context_policy import POPUP_CONTEXTS

POPUP_MAGIC = 0x4c435550
CLASS_IDS = {'filler': 0, 'useful': 1, 'progression': 2, 'trap': 3}


def popup_classification(value):
    if isinstance(value, bool):
        return 'progression' if value else 'filler'
    if value == 'progression_skip_balancing':
        return 'progression'
    if value not in CLASS_IDS:
        raise ValueError('Unknown item popup classification')
    return value


def popup_packet(pid, text, classification='filler'):
    # Native text supports formatting tags: server/item names must remain literal.
    text = re.sub(r'[<>\[\]{}\x00-\x1f\x7f]', ' ', str(text))
    text = ' '.join(text.split())
    encoded = text.encode('utf-8')[:287].decode('utf-8', errors='ignore').encode('utf-8')
    if not encoded:
        raise ValueError('Empty item notification')
    data = bytearray(320)
    classification = popup_classification(classification)
    struct.pack_into('<8I', data, 0, POPUP_MAGIC, 2, pid,
                     3, 6 if classification == 'progression' else 3, len(encoded), CLASS_IDS[classification], 0)
    data[32:32+len(encoded)] = encoded
    return bytes(data)


def show_item_popup(pid, text, classification, dll):
    result = _policy_command(pid, popup_packet(pid, text, classification), bytes(16), dll, 19)
    if result['changes'] and not result.get('tinted'):
        logging.warning('AP Item-Text übergeben, aber temporäre Klassenfarbe nicht eingerichtet')
    return bool(result['changes'])  # Accepted by native HUD, not proof of rendering.


class ItemPopupQueue:
    def __init__(self):
        self.tests = deque()
        self.next_at = 0
        self.last_error = None
        self.last_deferred = None

    def preview(self, classification):
        classification = popup_classification(classification)
        text = {'progression': 'You received Wurfhakenkanone from Player 2!',
                'useful': 'You sent 10,000 Bricks to Player 2!',
                'filler': 'You found your own 1,000 Studs!',
                'trap': 'You received Trap from Player 2!'}[classification]
        self.tests.append((text, classification))

    async def poll(self, session, snapshot, journal, dll, enabled=True):
        if not enabled or snapshot.get('actor', {}).get('context', {}).get('index') not in POPUP_CONTEXTS:
            return
        if time.monotonic() < self.next_at:
            return
        row = None if self.tests else journal.next_popup()
        if not self.tests and row is None:
            return
        text, classification = self.tests[0] if self.tests else (row['text'], row['classification'])
        # Persist before RPC. A timeout must never replay a possibly displayed toast.
        if row is not None:
            journal.popup_state(row['index'], 'dispatching')
        try:
            shown = await asyncio.to_thread(show_item_popup, session.pid, text, classification, dll)
        except NativePlayerBusy:
            if row is not None:
                journal.popup_state(row['index'], 'queued')
            return
        except (OSError, RuntimeError, ValueError) as error:
            if row is not None:
                journal.popup_state(row['index'], 'uncertain')
            else:
                self.tests.popleft()
            if str(error) != self.last_error:
                logging.warning('Item-Popup nicht bestätigt (Item-Vergabe bleibt unabhängig): %s', error)
                self.last_error = str(error)
            self.next_at = time.monotonic() + 10
            return
        if not shown:  # Native HUD is occupied; no native call was made.
            if row is not None:
                journal.popup_state(row['index'], 'queued')
            self.next_at = time.monotonic() + 1
            if text!=self.last_deferred:
                logging.info('AP-Meldung wartet auf freien HUD-Kanal und bleibt eingereiht: %s',text)
                self.last_deferred=text
            return
        if row is not None:
            journal.popup_state(row['index'], 'submitted')
        else:
            self.tests.popleft()
        self.next_at = time.monotonic() + (7 if classification == 'progression' else 4)
        self.last_error = None
        self.last_deferred = None
        logging.info('AP Item-Popup an HUD übergeben: %s', text)
