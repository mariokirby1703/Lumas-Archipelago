"""Apply proven source bindings for detection without changing seed/journal identity."""
from copy import deepcopy
import json
from pathlib import Path


def detection_catalogue(catalogue,bindings=None):
    if bindings is None:bindings=json.loads(Path(__file__).with_name('city_pickup_bindings.json').read_text())
    try:
        from .client_checks import KNOWN_AMBIGUOUS_PICKUP_BITS
    except ImportError:
        from client_checks import KNOWN_AMBIGUOUS_PICKUP_BITS
    sources={}
    for bit,row in bindings.items():
        if int(bit) not in KNOWN_AMBIGUOUS_PICKUP_BITS:sources.setdefault(row['source_key'],set()).add(int(bit))
    result=deepcopy(catalogue)
    for row in result.values():
        key=row.get('key','');runtime=row.get('runtime')
        if not key.startswith('source_pickup:') or runtime:continue
        bits=sources.get(key[len('source_pickup:'):],set())
        if len(bits)==1:row.update(runtime=dict(kind='pickup',bit=next(iter(bits))),status='native_pickup')
    return result
