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
TUTORIAL_CALL_IN='objective:WI_FL_0708_VehDrop'


def source_requirement(row):
    requirement=row.get('source_requirements') or {}
    kind=str(requirement.get('lockType','')).casefold()
    name=str(requirement.get('lockName','')).casefold()
    return (CLASSES if kind=='class' else TOOLS if kind=='ability' else {}).get(name)


def source_rule(row,player,enabled=True,key=None,detective_randomized=True):
    requirement=source_requirement(row)
    requirements=[requirement] if requirement else []
    kind=row.get('native_type')
    if kind=='COP_CriminalScan':requirements.extend(('Police','Scanner'))
    elif kind=='COP_AudioScan':requirements.extend(('Police','Wiretap'))
    if key==TUTORIAL_CALL_IN:requirements.append('SuperBuild')
    if key=='story_arrest:clown_3':
        requirements.append('Police')
        if detective_randomized:requirements.append('Detective Scan')
    # A source's route lock can add another class, but never substitutes a
    # different scan mechanic. Aura presence itself is not a completion check.
    return (lambda state:all(has_capability(state,player,name) for name in requirements)) if enabled else (lambda state:True)
