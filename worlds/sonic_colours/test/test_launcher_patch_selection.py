from types import SimpleNamespace
import pytest
from ..client.launch import select_player_patch
from ..client.launch import patch_server_address


def args(**kw):
    return SimpleNamespace(**(dict(patch_file=None,url=None,connect=None,nogui=False,
                                  no_start_dolphin=False)|kw))


def test_launcher_asks_for_patch_and_cancellation_stops(monkeypatch):
    import Utils
    selected=args()
    monkeypatch.setattr(Utils,'open_filename',lambda *a:'player.apsoniccolours')
    assert select_player_patch(selected)
    assert selected.patch_file=='player.apsoniccolours'
    monkeypatch.setattr(Utils,'open_filename',lambda *a:None)
    assert not select_player_patch(args())


def test_launcher_parser_without_nogui_still_selects_patch(monkeypatch):
    import Utils
    from CommonClient import get_base_parser
    parsed=get_base_parser().parse_args([])
    parsed.patch_file=None
    parsed.url=None
    parsed.no_start_dolphin=False
    monkeypatch.setattr(Utils,'open_filename',lambda *a:'player.apsoniccolours')
    assert select_player_patch(parsed)
    assert parsed.patch_file=='player.apsoniccolours'


@pytest.mark.parametrize('kw',[dict(patch_file='existing.apsoniccolours'),
    dict(url='archipelago://server'),dict(connect='localhost:38281'),
    dict(nogui=True),dict(no_start_dolphin=True)])
def test_explicit_client_invocations_do_not_open_picker(monkeypatch,kw):
    import Utils
    def unexpected(*a):pytest.fail('unexpected patch selection')
    monkeypatch.setattr(Utils,'open_filename',unexpected)
    assert select_player_patch(args(**kw))


def test_patch_endpoint_is_used_and_missing_address_never_reuses_last_room():
    patch=SimpleNamespace(server='archipelago.gg:38281')
    assert patch_server_address(patch,gui=False)=='archipelago.gg:38281'
    assert patch_server_address(patch,'localhost:12345',gui=False)=='localhost:12345'
    with pytest.raises(ValueError,match='no server address'):
        patch_server_address(SimpleNamespace(server=None),gui=False)


@pytest.mark.parametrize('address',['archipelago.gg','http://example.org:80','host:0/no','user:password@host:38281'])
def test_patch_requires_an_explicit_room_endpoint(address):
    with pytest.raises(ValueError):patch_server_address(SimpleNamespace(server=address),gui=False)
