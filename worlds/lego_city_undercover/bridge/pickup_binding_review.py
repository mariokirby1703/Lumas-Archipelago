"""Validate journal structural evidence before promoting shared source mappings.

This cannot upgrade native structural evidence to live gameplay verification.
Review is pure; the CLI owns explicitly requested catalogue writes.
"""
import math
import re
from collections import defaultdict
from pathlib import PurePosixPath
try:
    from .pickup_binding_observer import HASH,TYPES
    from .pickup_reader import pickup_bit
    from .client_checks import KNOWN_AMBIGUOUS_PICKUP_BITS
except ImportError:
    from pickup_binding_observer import HASH,TYPES
    from pickup_reader import pickup_bit
    from client_checks import KNOWN_AMBIGUOUS_PICKUP_BITS


def normal_tile(value):
    return value.casefold().removesuffix('_tech') if isinstance(value,str) else ''


def address(value):
    return isinstance(value,str) and re.fullmatch(r'0x[0-9a-fA-F]+',value) and 0x10000<=int(value,16)<0x800000000000


def validate_proof(proof,locations,sources,blocked=(),require_collection=False):
    """Return a precise rejection, or None for complete consistent evidence."""
    if not isinstance(proof,dict):return 'proof is not an object'
    source=proof.get('source_key');bit=proof.get('bit')
    if not isinstance(source,str) or '/levels/lego_city/lego_city/' not in source:return 'not a city source'
    if type(bit) is not int or not 0<=bit<12800:return 'invalid native bit'
    if bit in set(blocked)|KNOWN_AMBIGUOUS_PICKUP_BITS:return 'quarantined or known ambiguous bit'
    location=locations.get('source_pickup:'+source)
    if not location or location.get('category')!='super_bricks':return 'source is absent or not a Superbrick'
    code=location.get('source_type_code')
    if (code not in TYPES or type(proof.get('source_type')) is not int or type(proof.get('native_type')) is not int or
            proof.get('source_type')!=code or proof.get('native_type')!=TYPES[code]):return 'source/native type mismatch'
    if proof.get('resource')!=location.get('source'):return 'resource mismatch'
    if proof.get('verification')!='native_binding_verified' or type(proof.get('proof_version')) is not int or proof['proof_version']!=2:return 'requires version 2 structural proof'
    if proof.get('game_mutated') is not False:return 'read-only evidence required'
    if proof.get('writer_enabled') is not True:return 'native global city writer guard not proven'
    process=proof.get('process') or {}
    if not isinstance(process,dict) or process.get('sha256')!=HASH or type(process.get('pid')) is not int or process['pid']<=0:return 'unsupported executable/process'
    if not address(proof.get('native_bank')) or not address(proof.get('instance_address')):return 'invalid native identity addresses'
    if not isinstance(proof.get('journal_binding'),str) or not re.fullmatch('[0-9a-f]{32}',proof['journal_binding']):return 'missing journal identity'
    tile=normal_tile(proof.get('tile_name'));name=proof.get('name')
    matches={r['source_key'] for r in sources if normal_tile(r.get('tile_name'))==tile and
             r.get('name')==name and r.get('native_type')==proof['native_type']}
    if matches!={source}:return 'tile/name/type does not uniquely identify source'
    expected_tile=normal_tile(PurePosixPath(location['source']).stem)
    if tile!=expected_tile:return 'tile/resource mismatch'
    xy=proof.get('tile_xy');width=proof.get('grid_width');index=proof.get('local_index')
    if (type(width) is not int or not 1<=width<=256 or type(index) is not int or
            not isinstance(xy,list) or len(xy)!=2 or any(type(v) is not int for v in xy)):
        return 'missing native grid evidence'
    try:
        if not 0<=xy[1]<38:return 'tile row outside reviewed city writer branch'
        if pickup_bit(xy[0],xy[1],width,index)!=bit:return 'native bit formula mismatch'
    except ValueError:return 'invalid native grid evidence'
    flags=proof.get('native_flags') or {}
    try:
        type_flags=int(flags['type_flags'],16);instance_flags=int(flags['instance_flags'],16)
        if not 0<=type_flags<2**32 or not 0<=instance_flags<2**16:return 'invalid writer flag values'
        if not type_flags&0x4000000 or instance_flags&0x200:
            return 'writer branch flags not satisfied'
    except (ValueError,KeyError,TypeError):return 'missing writer branch flags'
    observations=proof.get('observations')
    if type(proof.get('observation_count')) is not int or proof['observation_count']!=2 or not isinstance(observations,list) or len(observations)!=2:
        return 'requires two native registration observations'
    for observation in observations:
        if not isinstance(observation,dict):return 'invalid registration observation'
        expected=dict(address=proof['instance_address'],source_key=source,native_type=proof['native_type'],bit=bit,
            local_index=index,tile_name=proof['tile_name'],grid_width=width,tile_xy=xy,
            status='native_writer_derived_binding',type_flags=flags['type_flags'],instance_flags=flags['instance_flags'])
        expected['writer_enabled']=True
        if any(type(observation.get(key)) is not type(value) or observation.get(key)!=value for key,value in expected.items()):
            return 'registration observations disagree'
        if any(type(value) is not int for value in observation['tile_xy']):return 'registration grid coordinates are not integers'
    pos=proof.get('position')
    if not isinstance(pos,list) or len(pos)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in pos):
        return 'invalid resource position metadata'
    if require_collection and not (proof.get('collection_transition_observed') is True and
                                  proof.get('before_collected') is False and proof.get('after_collected') is True):
        return 'collection transition not observed'
    return None


def review_bindings(proofs,existing,locations,sources,blocked=(),require_collection=False):
    accepted=[];rejected=[];unchanged=[]
    blocked=set(blocked);by_bit=defaultdict(set);by_source=defaultdict(set)
    if any(type(bit) is not int or not 0<=bit<12800 for bit in blocked):raise ValueError('Invalid quarantined bit list')
    # Account for all incoming evidence, including incomplete/conflicting peers.
    for proof in proofs:
        if isinstance(proof,dict) and isinstance(proof.get('source_key'),str) and type(proof.get('bit')) is int:
            by_bit[proof['bit']].add(proof['source_key']);by_source[proof['source_key']].add(proof['bit'])
    for bit,row in existing.items():
        by_bit[int(bit)].add(row['source_key']);by_source[row['source_key']].add(int(bit))
    seen=set()
    for proof in proofs:
        source=proof.get('source_key') if isinstance(proof,dict) else None
        bit=proof.get('bit') if isinstance(proof,dict) else None
        reason=validate_proof(proof,locations,sources,blocked,require_collection)
        if not reason and (len(by_bit[bit])!=1 or len(by_source[source])!=1):reason='source/bit collision with incoming or existing evidence'
        if reason:
            rejected.append(dict(source_key=source,bit=bit,reason=reason));continue
        if (source,bit) in seen:continue
        seen.add((source,bit))
        if str(bit) in existing:
            unchanged.append(dict(source_key=source,bit=bit));continue
        entry=dict(proof,status='native_writer_two_snapshot_identity',
                   evidence='validated journal proof v2; original writer flags and bit formula; not a live gameplay verdict')
        accepted.append(entry)
    return dict(accepted=accepted,rejected=rejected,unchanged=unchanged,
                verification='native_binding_verified',live_gameplay_verified=False,game_writes=False)
