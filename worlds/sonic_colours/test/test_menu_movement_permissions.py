from types import SimpleNamespace
import pytest
from ..client.state import WritePolicy
from ..client.memory import MemoryUnavailable
from ..client import skydiving,movement_gate


@pytest.mark.parametrize('scene',['world_map','global_map','game_land_select'])
@pytest.mark.parametrize('operation',['skydiving','movement_controls'])
@pytest.mark.parametrize('bound',[True,False])
def test_menu_permissions_require_current_save_binding(monkeypatch,scene,operation,bound):
    memory=SimpleNamespace(verify_revision=lambda:None)
    base=0x80002800
    monkeypatch.setattr(skydiving,'installed_data',lambda m:base)
    monkeypatch.setattr(movement_gate,'installed_data',lambda m:(base,'Gecko'))
    def check(snapshot):
        if not bound:raise MemoryUnavailable('WRITE_BLOCKED: switched or unbound save')
        return ('verified seed','selected save',snapshot.session)
    guard=SimpleNamespace(check=check)
    snapshot=SimpleNamespace(scene=scene,scene_verified=True,stable_polls=1,session='current-dolphin')
    policy=WritePolicy(memory,guard,lambda m:snapshot)
    if bound:
        assert policy(operation,base,4)[0][2]=='current-dolphin'
        if operation=='movement_controls':assert policy(operation,base+4,4)
    else:
        with pytest.raises(MemoryUnavailable,match='unbound save'):policy(operation,base,4)
    with pytest.raises(MemoryUnavailable,match='unverified movement data word'):
        policy(operation,base+8,4)


def test_local_give_and_remove_refresh_permissions_without_waiting_for_poll():
    from ..client.client import SonicCommands
    from ..client.test_inventory import LocalInventoryOverrides
    from ..client.runtime import inventory
    overlay=LocalInventoryOverrides();refreshed=[]
    runtime=SimpleNamespace(test_inventory=overlay,journal=SimpleNamespace(data={'receipts':[]}))
    context=SimpleNamespace(runtime=runtime,authenticated_identity=(0,1,'seed'),history_ready=True,items_received=[],
        refresh_movement_permissions=lambda:refreshed.append(overlay.apply(inventory([]))['counts']['Skydiving']))
    commands=object.__new__(SonicCommands);commands.ctx=context
    commands._change_test_ability('give','Skydiving')
    commands._change_test_ability('remove','Skydiving all')
    assert refreshed==[1,0]


@pytest.mark.parametrize('identity',[(0,1,'seed'),(0,1,'other-seed')])
def test_receipt_refresh_uses_authenticated_inventory(identity):
    from ..client.client import SonicContext
    from ..client.test_inventory import LocalInventoryOverrides
    from ..Items import ITEM_TABLE
    refreshed=[]
    runtime=SimpleNamespace(snapshot=object(),journal=SimpleNamespace(
        identity={'team':0,'slot':1,'seed':'seed'},data={'receipts':[]}),
        test_inventory=LocalInventoryOverrides(),
        refresh_movement_permissions=lambda memory,owned:refreshed.append(owned['counts']['Skydiving']))
    context=SimpleNamespace(runtime=runtime,memory=object(),authenticated_identity=identity,
        history_ready=True,items_received=[SimpleNamespace(item=ITEM_TABLE['Skydiving'])])
    SonicContext.refresh_movement_permissions(context)
    assert refreshed==([1] if identity[2]=='seed' else [])


def test_optional_movement_failure_does_not_block_other_permissions(monkeypatch):
    from ..client.runtime import Runtime
    from ..client import stunts,player_switch,water_native
    runtime=object.__new__(Runtime)
    runtime.snapshot=object();runtime.slot_data={'options':{'movement_unlocks':True}}
    runtime.guard=None;runtime.journal=None;runtime.experimental_direct_hooks=False
    runtime.hooks=SimpleNamespace(gameplay_controls_status={})
    def unavailable(*args,**kw):raise MemoryUnavailable('missing movement hook')
    monkeypatch.setattr(movement_gate,'configure',unavailable)
    monkeypatch.setattr(water_native,'configure',lambda *args:{'status':'not underwater'})
    monkeypatch.setattr(stunts,'configure',lambda *args:{'level':3})
    monkeypatch.setattr(player_switch,'configure',lambda *args:{'allowed':True})
    runtime.refresh_movement_permissions(object(),{'counts':{}})
    assert runtime.movement_status['status']=='missing movement hook'
    assert runtime.hooks.gameplay_controls_status=={'stunts':{'level':3},'assist_change':{'allowed':True}}
