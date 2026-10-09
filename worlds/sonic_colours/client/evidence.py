from dataclasses import dataclass
from enum import Enum
from ..world_constants import load_data


class EvidenceGrade(str, Enum):
    UNRESOLVED = 'unresolved'
    CODE_DERIVED = 'code-derived'
    DUMP_CORRELATED = 'dump-correlated'
    LIVE_READ = 'live-read-validated'
    LIVE_WRITE = 'live-write-validated'


@dataclass(frozen=True)
class NativeEvidence:
    name: str
    grade: EvidenceGrade
    kind: str
    proof: str
    live_read: bool
    live_write: bool


def evidence_registry():
    result = {}
    for name, record in load_data('native_evidence.json').items():
        grade = EvidenceGrade(record['grade'])
        if not record['proof'] or record['live_write'] and grade != EvidenceGrade.LIVE_WRITE:
            raise ValueError('unproven write capability: ' + name)
        if record['live_read'] and grade not in (EvidenceGrade.LIVE_READ, EvidenceGrade.LIVE_WRITE):
            raise ValueError('unproven read capability: ' + name)
        result[name] = NativeEvidence(name, grade, record['kind'], record['proof'],
                                      record['live_read'], record['live_write'])
    return result
