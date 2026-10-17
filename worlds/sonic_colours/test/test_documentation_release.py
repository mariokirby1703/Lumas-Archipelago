"""Canonical guides, real WebHost filenames and release-only file boundaries."""
import json
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


def test_built_guides_and_tutorial_follow_stock_webhost_conventions(tmp_path):
    from werkzeug.utils import secure_filename
    assert WEB_GAME_INFO=='en_'+secure_filename(GAME)+'.md'
    with zipfile.ZipFile(build(tmp_path/'sonic_colours.apworld')) as archive:
        names=set(archive.namelist())
        overview=archive.read('sonic_colours/docs/sonic_colours.md')
        assert archive.read('sonic_colours/docs/'+WEB_GAME_INFO)==overview
        for tutorial in SonicColoursWeb.tutorials:
            assert tutorial.file_name=='setup.md'
            assert tutorial.link=='setup'
            assert archive.read('sonic_colours/docs/'+tutorial.file_name)
        for name in ['sonic_colours/README.md',*sorted(n for n in names if '/docs/' in n)]:
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
    'client/runtime.py','data/native_event_sites.json','data/logic_from_sheet_v2.json',
    'assets/Colours Logo.png','tools/build_hud_overlay.py','tools/hud_original_assets.py',
    'docs/setup.md','docs/sonic_colours.md','examples/SonicColours.yaml',
    'Options.py','archipelago.json','requirements.txt',
])
def test_runtime_and_local_iso_patcher_remain_release_inputs(name):
    assert release_file(Path(name))


def test_research_report_goes_to_ignored_build_not_docs(tmp_path):
    from ..tools.audit_research import write_report
    root=tmp_path/'worlds/sonic_colours';root.mkdir(parents=True)
    report={'live_validation':False,'files':[]}
    target=write_report(root,report)
    assert target==tmp_path/'build/research_audit.json'
    assert json.loads(target.read_text())==report
    assert not (root/'docs').exists()
