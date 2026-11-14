"""Persistent completion sources for the three opening-story clown arrests."""
ARRESTS=tuple(dict(key=f'story_arrest:clown_{i}',name=f'Story Arrest: Clown Robber {i}',
                  job='Flow_Setup.Flow_Completed',field=f'Act_1_CatchRobber_{i}') for i in range(1,4))


def completed_story_arrests(story):
    if story.get('status')!='read':return set()
    jobs=story.get('jobs',{})
    return {row['key'] for row in ARRESTS if jobs.get(row['job'],{}).get(row['field']) is True}
