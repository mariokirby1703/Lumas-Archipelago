"""Option-aware Wisp ownership shared by generation, logic and native policy.

Existing progressive IDs retain their meaning. Normal variants are additional
items, and never manufacture ownership of another colour.
"""
from collections import Counter
from .world_constants import WISPS,wisp_item

PROGRESSIVE_COLOURS=('Yellow Drill','Green Hover','Pink Spikes')

def option(options,name,default=True):
    value=options.get(name,default) if isinstance(options,dict) else getattr(options,name,default)
    return bool(getattr(value,'value',value))

def required_wisp_items(options):
    return tuple(wisp_item(colour,option(options,'movement_unlocks')) for colour in WISPS
                 if colour!='White Boost' or option(options,'boost_lock'))

def wisp_level(counts,colour,options=None):
    options=options or {}
    if colour not in WISPS:raise ValueError('Unknown Wisp colour: '+str(colour))
    if colour=='White Boost' and not option(options,'boost_lock'):return 1
    normal=counts.get(wisp_item(colour,False),0)
    if colour not in PROGRESSIVE_COLOURS:return int(normal>0)
    level=max(2 if normal else 0,min(2,counts.get(wisp_item(colour,True),0)))
    return 2 if level and not option(options,'movement_unlocks') else level

def all_wisps_owned(counts,options):
    return all(wisp_level(counts,colour,options)>0 for colour in WISPS)

def project_inventory(owned,options):
    counts=Counter(owned['counts'])
    for colour in WISPS:counts[wisp_item(colour)]=wisp_level(owned['counts'],colour,options)
    return {**owned,'counts':counts,'wisps':[wisp_item(c) for c in WISPS if counts[wisp_item(c)]]}
