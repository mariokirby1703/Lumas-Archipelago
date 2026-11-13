"""Section transitions independent of collection/check detection."""
import re

AREA_NAMES = {
    'SF_Residential': 'Cherry Tree Hills', 'SF_Docks': 'Auburn',
    'WI_Farmlands': 'Fort Meadows', 'WI_Forest': 'Bluebell Nationalpark',
    'BR_Golden_Gate': 'Auburn Bay Bridge',
    'IS_Prison_Island': 'Albatross Island',
}


def location_heading(location):
    tile = location.get('native_tile', '')
    match = re.fullmatch(r'(.+)_\d{4}', tile)
    if not match:
        return 'Gebiet: aktuell nicht erkannt'
    area = match[1]
    return f"Gebiet: {AREA_NAMES.get(area, area)} · Kachel: {tile}"


def story_heading(story):
    jobs = story.get('jobs', {})
    act = jobs.get('Flow_Setup', {}).get('Flow_Act')
    fields = jobs.get(f'Flow_Setup.Act_{act}', {})
    mission = fields.get(f'Act{act}_Mission')
    stage = fields.get(f'Act{act}_Stage')
    if not isinstance(act, int) or not isinstance(mission, int):
        return 'Storyfortschritt: aktuell nicht erkannt'
    return f'Storyfortschritt: Akt {act} · Abschnitt {mission} · Stage {stage} (unabhängig vom Gebiet)'


class SectionTracker:
    def __init__(self):
        self.area = None
        self.story = None

    def update(self, snapshot):
        events = []
        location = snapshot.get('location', {})
        tile = location.get('native_tile', '')
        match = re.fullmatch(r'(.+)_\d{4}', tile)
        if match:
            area = match[1]
            if area != self.area:
                events.append(dict(kind='area_section', text=f"----- {AREA_NAMES.get(area, area)} -----",
                                   native_area=area, native_tile=tile, location=location))
                self.area = area
        jobs = snapshot.get('story', {}).get('jobs', {})
        act = jobs.get('Flow_Setup', {}).get('Flow_Act')
        fields = jobs.get(f'Flow_Setup.Act_{act}', {})
        mission = fields.get(f'Act{act}_Mission')
        # Mission 0 is used during transitions; do not announce it as an assignment.
        if isinstance(act, int) and isinstance(mission, int) and 1 <= act <= 4 and mission > 0:
            key = (act, mission)
            if key != self.story:
                events.append(dict(kind='story_section', text=f'----- Story: Akt {act} · Abschnitt {mission} -----',
                                   act=act, mission=mission, stage=fields.get(f'Act{act}_Stage'),
                                   evidence='native campaign cursor; not independent level identity', location=location))
                self.story = key
        return events
