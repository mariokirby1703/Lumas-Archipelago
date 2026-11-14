"""Recover two station rewards if AP-owned Police skipped the original wardrobe.

The garage advances from WaitForToken when COP is already available AND the
wardrobe build output is complete. PDA.acquired is set later at ActivateLiftDoors.
It is therefore evidence the original wardrobe reward stage has been passed,
even when no character-found event was emitted. Ownership alone is never evidence.
"""
COP_REWARD_KEY='story_disguise:COP'
GRACE_REWARD_KEY='source_pickup:GAME7/levels/standalones/police_station/police_station_garage/police_station_garage.giz:9843:0'
STATION_REWARD_KEYS=frozenset((COP_REWARD_KEY,GRACE_REWARD_KEY))


def completed_station_rewards(story):
    if story.get('status')!='read':return set()
    if story.get('jobs',{}).get('PDA',{}).get('acquired') is not True:return set()
    return set(STATION_REWARD_KEYS)


def grace_reward_metadata():
    return dict(name='Story Character: Grace Makepiece (COP_FEMALE_P2)',
        category='character_tokens',runtime=dict(kind='model_found',native_name='COP_FEMALE_P2'),
        status='experimental_model_found',linked_story_reward='COP',
        evidence='collection.txt default linked class cop; original wardrobe also grants COP_FEMALE_P2; recovery after PDA.acquired')
