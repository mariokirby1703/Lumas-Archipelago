"""Goals use native completion records; missing/new slot data keeps legacy tokens."""
ASSIGNMENTS=('rooftops','prison','mine','temple','bank','space_centre','scrapyard','museum','fire_station',
             'blackwells_mansion_1','icecream_parlour','construction_site','secretbase','blackwells_mansion_2','moon_base')


def native_goal_complete(snapshot,goal):
    progress=snapshot.get('level_progress',{})
    if progress.get('status')!='read':return False
    records=progress.get('records',[])
    complete={r.get('assignment',r['mission']) for r in records if r.get('complete')}
    return ('moon_base' in complete if goal==0 else set(ASSIGNMENTS)<=complete if goal==1 else False)
