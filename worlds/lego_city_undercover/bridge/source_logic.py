"""Requirements copied from source lock metadata, never inferred from reward type.

Unknown locks are reported by the audit; this is not complete traversal logic.
"""
try:
    from .capabilities import has_capability
except ImportError:
    from capabilities import has_capability

CLASSES={'cop':'Police','robber':'Robber','miner':'Miner','astronaut':'Astronaut',
         'farmer':'Farmer','fireman':'Firefighter','worker':'Construction Worker','construction':'Construction Worker'}
TOOLS={'energygun':'Color Gun','superbuild':'SuperBuild','parkour':'Parkour','superstrength':'Rex Fury',
       'jetpack':'Jetpack','wiretap':'Wiretap','pig':'Farmer'}


def source_requirement(row):
    requirement=row.get('source_requirements') or {}
    kind=str(requirement.get('lockType','')).casefold()
    name=str(requirement.get('lockName','')).casefold()
    return (CLASSES if kind=='class' else TOOLS if kind=='ability' else {}).get(name)


def source_rule(row,player,enabled=True):
    requirement=source_requirement(row)
    return (lambda state:has_capability(state,player,requirement)) if enabled and requirement else (lambda state:True)
