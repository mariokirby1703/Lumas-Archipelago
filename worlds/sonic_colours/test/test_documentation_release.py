"""Canonical guides, real WebHost filenames and release-only file boundaries."""
from pathlib import Path
import re
import zipfile

import pytest

from ..build_apworld import build, release_file, WEB_GAME_INFO
from ..web_world import SonicColoursWeb
from ..world_constants import GAME


def test_source_has_only_two_canonical_guides():
    docs=Path(__file__).parents[1]/'docs'
    assert {p.name for p in docs.iterdir()}=={'setup.md','sonic_colours.md'}


def test_source_webhost_publishes_canonical_game_info(tmp_path,monkeypatch):
    import WebHost
    import Utils
    from werkzeug.utils import secure_filename
    original=Utils.local_path
    def local_path(*parts):
        if parts[:4]==('WebHostLib','static','generated','docs'):
            return str(tmp_path.joinpath(*parts[4:]))
        return original(*parts)
    monkeypatch.setattr(Utils,'local_path',local_path)
    WebHost.copy_tutorials_files_to_static()
    generated=tmp_path/secure_filename(GAME)
    assert (generated/WEB_GAME_INFO).read_bytes()==(Path(__file__).parents[1]/'docs/sonic_colours.md').read_bytes()


def test_built_guides_and_tutorial_follow_stock_webhost_conventions(tmp_path):
    from werkzeug.utils import secure_filename
    assert WEB_GAME_INFO=='en_'+secure_filename(GAME)+'.md'
    with zipfile.ZipFile(build(tmp_path/'sonic_colours_wii.apworld')) as archive:
        names=set(archive.namelist())
        overview=archive.read('sonic_colours_wii/docs/sonic_colours.md')
        assert archive.read('sonic_colours_wii/docs/'+WEB_GAME_INFO)==overview
        for tutorial in SonicColoursWeb.tutorials:
            assert tutorial.file_name=='setup.md'
            assert tutorial.link=='setup'
            assert archive.read('sonic_colours_wii/docs/'+tutorial.file_name)
        for name in ['sonic_colours_wii/README.md',*sorted(n for n in names if '/docs/' in n)]:
            for target in re.findall(r'\]\(([^)]+)\)',archive.read(name).decode()):
                path=target.split('#',1)[0]
                if not path or '://' in path:continue
                # Resolve relative Markdown links using the same archive tree.
                import posixpath
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),path))
                assert resolved in names,(name,target)


@pytest.mark.parametrize('name',[
    'notes/private.md','test/fixtures/pal_traces/live_pal_act1.json',
    'client/__pycache__/x.pyc','client/.pytest_cache/report.json',
    'data/.mypy_cache/report.json','data/.ruff_cache/report.json',
    'build/log.json','old_release.zip','old_release.apworld','TODO.md',
    'research_audit.json','docs/obsolete_report.md','tools/audit_research.py',
    'examples/SonicColours_Native_Test.yaml','examples/Luma_Migrated.yaml',
])
def test_development_files_are_never_release_inputs(name):
    assert not release_file(Path(name))


@pytest.mark.parametrize('name',[
    'client/runtime.py','data/native_event_sites.json','data/logic_from_sheet_v3.json',
    'assets/COLORSAPlogo.png','tools/build_hud_overlay.py','tools/hud_original_assets.py',
    'docs/setup.md','docs/sonic_colours.md','examples/SonicColours.yaml',
    'Options.py','archipelago.json','requirements.txt',
])
def test_runtime_and_local_iso_patcher_remain_release_inputs(name):
    assert release_file(Path(name))


def test_optional_native_references_are_outside_the_world(tmp_path):
    from ..tools.private_assets import reference_root
    root=tmp_path/'worlds/sonic_colours'
    assert reference_root(root)==tmp_path/'build/sonic_colours_reference'
    assert not reference_root(root).is_relative_to(root)
    assert not release_file(Path('tools/private_assets.py'))


def test_legacy_yaml_is_preserved_as_a_test_fixture():
    path=Path(__file__).parent/'fixtures/yaml/Luma_Migrated.yaml'
    assert path.is_file()
    assert not (Path(__file__).parents[1]/'examples/Luma_Migrated.yaml').exists()
