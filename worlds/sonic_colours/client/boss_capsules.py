import struct
from .capsule_refresh import PPC

HOOK=0x802E7E28
ORIGINAL=0x88030074
BLOCKED=0x802E7F4C
VTABLE=0x8077E080


CREATE_HOOK=0x802E79C8
CREATE_ORIGINAL=0x38A00001
UPDATE_HOOK=0x802E7C70
UPDATE_ORIGINAL=0x881F0074
MODEL_VTABLE=0x8077D12C


def permission(a,capsule_control,progression_control,actor,allowed,denied):
    def const(r,value):a.d(15,r,0,value>>16);a.d(24,r,r,value&65535)
    def eq(left,right):a.emit(0x7C000000|left<<16|right<<11)
    a.d(32,0,actor,0);const(5,VTABLE);eq(0,5);a.branch(denied,0x40820000)
    const(12,capsule_control)
    a.d(32,5,12,0);a.d(11,0,5,0);a.branch(denied,0x41820000)
    a.d(34,0,5,0);a.d(32,6,12,4);eq(0,6);a.branch(denied,0x40820000)
    a.d(32,0,actor,0x60);a.d(11,0,0,-1);a.branch('white',0x41820000)
    a.d(10,0,0,6);a.branch(denied,0x41810000)
    # Capsule controls own the save *container*, whereas progression owns
    # the selected record's flags: container + 8 + index*0x19608 + 0x1c.
    # Never compare these distinct native owners directly (even slot 0
    # differs by 0x24). Keep the native index proof above for every slot.
    a.d(15,12,0,1);a.d(24,12,12,0x9608)
    a.emit(0x7CC661D6) # mullw r6,r6,r12
    a.d(14,6,6,0x24);a.emit(0x7CA53214) # add r5,r5,r6
    a.d(14,6,0,1);a.emit(0x7CC60030) # slw r6,r6,r0
    const(12,progression_control)
    a.d(32,0,12,0);eq(0,5);a.branch(denied,0x40820000)
    a.d(32,0,12,8);a.emit(0x7C003039) # and. r0,r0,r6
    a.branch(denied,0x41820000);a.branch(allowed)
    a.label('white');a.d(32,0,12,8);a.d(28,0,0,1);a.branch(denied,0x41820000)
    a.branch(allowed)


def program(capsule_control,progression_control):
    # No calls/writes; actor/event arguments r3/r4 remain intact.
    a=PPC();permission(a,capsule_control,progression_control,3,'allow','deny')
    a.label('allow');a.emit(ORIGINAL);a.branch('return')
    a.label('deny');denied=len(a.words);a.emit(0x60000000)
    a.label('return');a.emit(0)
    return a.finish(),denied


def create_program(capsule_control,progression_control):
    # Before 802E79DC stores the native model mode into its constructor args.
    # Preserve the colour in r3 and the actor in r30. Mode 0 is the native
    # ghost model, mode 1 the normal contents model. Other args are unchanged.
    a=PPC();permission(a,capsule_control,progression_control,30,'allow','deny')
    a.label('allow');a.d(14,5,0,1);a.branch('return')
    a.label('deny');a.d(14,5,0,0)
    a.label('return');a.emit(0)
    return a.finish()


def update_program(capsule_control,progression_control):
    # This native void-update boundary has no live volatile FPR/GPR values.
    # r30/r31 stay intact; our additional nonvolatile r28/r29 and LR are saved.
    # Only rebuild on a mode change, using the original model constructor and
    # reference-assignment routine. Do not recreate collision/physics/provider.
    a=PPC();a.d(37,1,1,-0x100);a.emit(0x7C0802A6);a.d(36,0,1,0xf4)
    a.d(36,28,1,0xe0);a.d(36,29,1,0xe4);a.mr(28,31)
    a.d(32,0,28,0);a.d(15,5,0,VTABLE>>16);a.d(24,5,5,VTABLE&65535)
    a.emit(0x7C002800);a.branch('end',0x40820000)
    a.d(32,0,28,0x60);a.d(11,0,0,-1);a.branch('end',0x41800000)
    a.branch('colour_valid',0x41820000)
    a.d(10,0,0,6);a.branch('end',0x41810000)
    a.label('colour_valid')
    a.d(34,0,28,0x74);a.d(11,0,0,0);a.branch('end',0x40820000)
    permission(a,capsule_control,progression_control,28,'allow','deny')
    a.label('allow');a.d(14,29,0,1);a.branch('model')
    a.label('deny');a.d(14,29,0,0)
    a.label('model');a.d(32,6,28,0x68);a.d(11,0,6,0);a.branch('end',0x41820000)
    a.d(32,0,6,0);a.d(15,5,0,MODEL_VTABLE>>16);a.d(24,5,5,MODEL_VTABLE&65535)
    a.emit(0x7C002800);a.branch('end',0x40820000)
    a.d(32,0,6,8);a.emit(0x7C00E000);a.branch('end',0x40820000)
    a.d(32,0,6,0x88);a.d(10,0,0,1);a.branch('end',0x41810000)
    a.emit(0x7C00E800);a.branch('end',0x41820000)
    a.d(32,0,28,0x60);a.d(36,0,1,0x40);a.d(36,29,1,0x44)
    a.d(14,0,0,3);a.d(36,0,1,0x48)
    a.d(14,3,1,0x60);a.d(14,4,28,0x44);a.d(14,5,28,0x50);a.call(0x801A3920)
    a.d(14,3,0,0xc8);a.d(14,4,0,0xff);a.call(0x80077B04)
    a.d(11,0,3,0);a.branch('end',0x41820000)
    a.mr(4,28);a.d(14,5,1,0x40);a.d(14,6,1,0x60)
    a.d(48,1,28,0x64);a.emit(0xFC400890) # fmr f2,f1
    a.call(0x802D5AD0);a.d(11,0,3,0);a.branch('end',0x41820000)
    a.mr(4,3);a.d(14,3,28,0x68);a.call(0x800D3E54)
    a.label('end');a.d(32,28,1,0xe0);a.d(32,29,1,0xe4)
    a.d(32,0,1,0xf4);a.emit(0x7C0803A6);a.d(14,1,1,0x100)
    a.emit(UPDATE_ORIGINAL);a.emit(0)
    return a.finish()


def patches(capsule_control,progression_control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    from .native_events import scatter
    pool={site['address']:site for name in ('boss_capsule_sites.json',)
          for site in load_data(name)}
    sites=[site for site in sorted(pool.values(),key=lambda s:s['address']) if not any(
        site['address']<address+len(new) and address<site['address']+12
        for address,old,new in occupied)]
    result=[]
    words,denied=program(capsule_control,progression_control)
    programs=((HOOK,ORIGINAL,words,denied),
              (CREATE_HOOK,CREATE_ORIGINAL,create_program(capsule_control,progression_control),None),
              (UPDATE_HOOK,UPDATE_ORIGINAL,update_program(capsule_control,progression_control),None))
    used=0
    for hook,original,words,denied in programs:
        selected=sites[used:];chunks=scatter(words,selected,hook+4,compact=denied is None)
        if denied is not None:
            address,old,_=chunks[denied]
            chunks[denied]=(address,old,struct.pack('>3I',branch(address,BLOCKED),0x60000000,0x60000000))
        result.append((hook,original.to_bytes(4,'big'),branch(hook,selected[0]['address']).to_bytes(4,'big')))
        result.extend(chunks);used+=len(chunks)
    return result


def planned_patches():
    from .native_dol import plan
    rows=plan()[0]
    start=next(i for i,row in enumerate(rows) if row[0]==HOOK)
    from .wisp_hud import HOOK as following
    end=next(i for i,row in enumerate(rows) if row[0]==following)
    return rows[start:end]
