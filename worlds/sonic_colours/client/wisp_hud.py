"""Remove unowned cached cockpit icons through the native HUD event handler."""
import struct
from .capsule_refresh import PPC

HOOK=0x8010EEA4
ORIGINAL=0x801E01A8  # lwz r0,0x1a8(r30), before the cockpit state dispatch


def program(capsule_control,progression_control):
    # At this dispatch boundary no volatile GPR/FPR is live: every successor
    # initializes its arguments; r0 is the displaced load. Native callees keep
    # r14..r31/f14..f31. Preserve LR/CTR/CR and keep event storage above the
    # ABI's outgoing argument home area (stack+08..27).
    a=PPC()
    def const(r,value):a.d(15,r,0,value>>16);a.d(24,r,r,value&65535)
    def eq(l,r):a.emit(0x7C000000|l<<16|r<<11)
    a.d(37,1,1,-0x140)
    for instruction,offset in ((0x7C0802A6,0x90),(0x7C0902A6,0x94),(0x7C000026,0x98)):
        a.emit(instruction);a.d(36,0,1,offset)
    a.d(32,0,30,0);const(5,0x80764440);eq(0,5);a.branch('done',0x40820000)
    a.d(32,0,30,0x1b0);a.d(10,0,0,6);a.branch('done',0x41810000)
    # The selected record must agree with both authenticated permission owners.
    const(12,capsule_control);a.d(32,5,12,0);a.d(11,0,5,0);a.branch('done',0x41820000)
    a.d(34,3,5,0);a.d(32,6,12,4);eq(3,6);a.branch('done',0x40820000)
    a.d(10,0,6,3);a.branch('done',0x41810000)
    const(12,0x19608);a.emit(0x7CC661D6);a.d(14,6,6,0x24);a.emit(0x7CA53214)
    const(12,progression_control);a.d(32,3,12,0);eq(3,5);a.branch('done',0x40820000)
    a.d(14,6,0,1);a.emit(0x7CC60030);a.d(32,3,12,8);a.emit(0x7C633039)
    a.branch('done',0x40820000)
    # Do not cancel a newly queued owned replacement while removing an old icon.
    a.d(32,0,30,0x1b4);a.d(10,0,0,6);a.branch('remove',0x41810000)
    a.d(14,6,0,1);a.emit(0x7CC60030);a.d(32,3,12,8);a.emit(0x7C633039)
    a.branch('done',0x40820000)
    a.label('remove')
    # An actual native event removes the icon and its effects/animation.
    # Emptying the boost model or changing its dirty flag does not send this.
    a.d(14,3,1,0x30);a.d(14,4,0,-1);a.d(14,5,0,0);a.call(0x8012154C)
    a.mr(3,30);a.d(14,4,1,0x30);a.call(0x80112A94)
    a.label('done')
    for offset,instruction in ((0x98,0x7C0FF120),(0x94,0x7C0903A6),(0x90,0x7C0803A6)):
        a.d(32,0,1,offset);a.emit(instruction)
    a.d(14,1,1,0x140);a.emit(ORIGINAL);a.emit(0)
    return a.finish()


def patches(capsule_control,progression_control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    from .native_events import scatter
    sites=[s for s in load_data('wisp_hud_sites.json') if not any(
        s['address']<address+len(new) and address<s['address']+12 for address,old,new in occupied)]
    words=program(capsule_control,progression_control)
    return [(HOOK,struct.pack('>I',ORIGINAL),struct.pack('>I',branch(HOOK,sites[0]['address']))),
            *scatter(words,sites,HOOK+4,compact=True)]


def planned_patches():
    from .native_dol import plan
    rows=plan()[0];start=next(i for i,row in enumerate(rows) if row[0]==HOOK)
    from .homing_fallback import HOOK as following
    end=next(i for i,row in enumerate(rows) if row[0]==following)
    return rows[start:end]
