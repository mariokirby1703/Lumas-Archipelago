from pathlib import Path

import pytest

from ..client.native_hook_table import _records,hook_rows
from ..client.native_dol import ARENA,SIGNATURE,plan


def test_native_plan_preserves_all_installed_hooks_and_bytes():
    _,payload,digest,hooks=plan()
    assert digest.hex()=='d37b812a9e186695a45db4519ebada0f557e4523dc26dcea5098d95c6ddadc47'
    assert ARENA+len(payload)<=SIGNATURE
    assert len({hook['hook'] for hook in hooks})==len(hooks)
    assert hook_rows()


def test_payload_words_are_not_interpreted_as_record_headers():
    assert _records(['C2001000 00000001','C2002000 00000000'])==[
        (0xc2001000,1),(0xc2002000,0)]


@pytest.mark.parametrize('lines',[
    ['C2001000 00000002','60000000 00000000'],
    ['C2001000 00000000'],['FF000000 00000000'],
])
def test_invalid_native_records_are_rejected(lines):
    with pytest.raises(ValueError):_records(lines)


@pytest.mark.parametrize('flag',['--export-movement-gecko','--export-capsule-gecko'])
def test_old_export_commands_are_unavailable(flag,tmp_path):
    from ..client.launch import launch_client
    target=tmp_path/'codes.ini'
    with pytest.raises(SystemExit) as error:launch_client(flag,str(target))
    assert error.value.code==2
    assert not target.exists()


def test_old_export_files_are_absent_and_ini_files_are_not_packaged():
    from ..build_apworld import release_file
    root=Path(__file__).parents[1]
    assert not list((root/'data').glob('*.ini'))
    assert not (root/'client/movement_gecko.py').exists()
    assert not release_file(Path('data/old_codes.ini'))
