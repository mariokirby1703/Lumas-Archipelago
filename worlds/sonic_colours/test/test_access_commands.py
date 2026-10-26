from types import SimpleNamespace
import asyncio
import pytest

from ..client.client import SonicCommands
from ..client.test_inventory import LocalInventoryOverrides, WORLD_UNLOCK_ITEMS
from ..client.runtime import inventory
from ..world_progression import available_story_stages
from ..world_constants import STAGES
from ..wisps import project_inventory


def commands():
    overlay=LocalInventoryOverrides()
    ctx=SimpleNamespace(runtime=SimpleNamespace(test_inventory=overlay,journal=SimpleNamespace(data={'receipts':[]})),
        authenticated_identity=(0,1,'seed'),history_ready=True,items_received=[],
        refresh_movement_permissions=lambda:None,sync_wakeup=asyncio.Event())
    command=object.__new__(SonicCommands);command.ctx=ctx
    return command,overlay,ctx


def test_release_has_no_give_or_remove_commands():
    assert not hasattr(SonicCommands,'_cmd_give')
    assert not hasattr(SonicCommands,'_cmd_remove')
    assert 'give' not in SonicCommands.commands
    assert 'remove' not in SonicCommands.commands


def test_giveworlds_grants_only_shuttles_locally_and_reset_restores():
    command,overlay,ctx=commands()
    command._change_test_ability('give','worlds')
    effective=overlay.apply(inventory([]))
    assert all(effective['counts'][name]==1 for name in WORLD_UNLOCK_ITEMS)
    assert set(name for name,count in effective['counts'].items() if count)==set(WORLD_UNLOCK_ITEMS)
    assert ctx.items_received==[]
    assert ctx.runtime.journal.data=={'receipts':[]}
    overlay.reset()
    assert not overlay.apply(inventory([]))['counts']


def test_boss_command_survives_inventory_projection_and_is_resettable():
    command,overlay,ctx=commands()
    command._change_test_ability('give','bosses')
    assert ctx.sync_wakeup.is_set()
    assert overlay.describe(inventory([]))['boss_unlocks']
    owned=project_inventory(overlay.apply(inventory([])),{'movement_unlocks':True,'boost_lock':True})
    assert owned['local_boss_unlocks']
    assert not any(owned['counts'].values())
    command._change_test_ability('give','worlds')
    assert overlay.apply(inventory([]))['local_boss_unlocks']
    command._change_test_ability('remove','bosses')
    assert not overlay.unlock_bosses
    command._change_test_ability('give','bosses')
    command._cmd_testitems('reset')
    assert not overlay.unlock_bosses and not overlay.deltas
    assert ctx.items_received==[] and ctx.runtime.journal.data=={'receipts':[]}


@pytest.mark.parametrize('mode',[0,1])
@pytest.mark.parametrize('zone',range(7))
def test_boss_override_does_not_manufacture_clears_or_unlock_other_story_acts(zone,mode):
    cleared=set()
    ordinary=available_story_stages(zone,cleared,mode)
    unlocked=available_story_stages(zone,cleared,mode,unlock_bosses=True)
    assert cleared==set()
    if zone<6:
        boss=next(s['mission_id'] for s in STAGES if s['zone_index']==zone and s['slot']==7)
        assert unlocked==ordinary|{boss}
    else:
        assert unlocked=={'stg710','stg790','stg720'}


def test_commands_require_authenticated_runtime():
    command,overlay,ctx=commands()
    ctx.authenticated_identity=None
    command._change_test_ability('give','worlds');command._change_test_ability('give','bosses')
    assert not overlay.deltas and not overlay.unlock_bosses


def test_bad_boss_argument_preserves_override():
    command,overlay,_=commands()
    command._change_test_ability('give','bosses')
    command._change_test_ability('give','bosses unknown')
    assert overlay.unlock_bosses
