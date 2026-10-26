from .world_constants import load_data,BASE_ID,BY_MISSION

ROWS=load_data('one_up_positions.json')['locations']
ONEUPS={}
for index,row in enumerate(ROWS):
    mission=row['mission_id']
    key=f"{mission}:{row['layer']}:{row['object_id']}:{row['instance']}"
    ONEUPS[key]={**row,'key':key,'code':BASE_ID+20000+index,
                 'location_name':BY_MISSION[mission]['name']+' - 1-Up'}
if len(ONEUPS)!=31:raise ValueError('Expected 31 unique physical 1-Up instances')
