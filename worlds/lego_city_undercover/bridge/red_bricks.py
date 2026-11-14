"""Canonical Red Brick locations; two mansion assignments are distinct."""
def redbrick_location_key(source):
    if '/levels/lego_city/lego_city/' in source:return 'source_pickup:'+source
    if '/levels/standalones/' not in source:return None
    parts=source.split('/levels/standalones/',1)[1].split('/')
    mission=parts[0]
    if mission=='gamemechanicstestarea':return None
    if mission=='blackwells_mansion':
        if len(parts)<2:return None
        if parts[1].startswith('mansion1_'):mission='blackwells_mansion_1'
        elif parts[1].startswith('mansion2_'):mission='blackwells_mansion_2'
        else:return None
    return 'mission:'+mission+':Red Brick'
