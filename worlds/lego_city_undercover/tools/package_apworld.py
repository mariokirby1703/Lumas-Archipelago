"""Package only integration code/metadata/docs, never extracted game assets."""
import hashlib
import json
from pathlib import Path
import zipfile

WORLD=Path(__file__).resolve().parents[1]
ROOT=WORLD.parents[1]


def main():
    build=ROOT/'build/lego_city_undercover';build.mkdir(parents=True,exist_ok=True)
    files=[*WORLD.glob('*.py'),WORLD/'catalogue.json',WORLD/'archipelago.json',WORLD/'README.md',
           *WORLD.joinpath('bridge').glob('*.py'),*WORLD.joinpath('bridge').glob('*.json'),
           *WORLD.joinpath('docs').rglob('*.md'),*WORLD.joinpath('docs').rglob('*.yaml'),
           *WORLD.joinpath('docs').rglob('*.csv'),*WORLD.joinpath('docs').rglob('*.json')]
    target=build/'lego_city_undercover.apworld';temporary=target.with_suffix('.apworld.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            relative=path.relative_to(WORLD)
            info=zipfile.ZipInfo('lego_city_undercover/'+relative.as_posix(),date_time=(2026,11,14,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,path.read_bytes())
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip():raise RuntimeError('Corrupt archive')
        names=archive.namelist()
        if any('/notes/' in name or name.lower().endswith(('.exe','.dll','.giz','.sf')) for name in names):
            raise RuntimeError('Proprietary/native build asset in APWorld')
    temporary.replace(target)
    # AP's importer derives the package name from the archive filename.
    # A differently named copy needs a matching package root, not identical bytes.
    alias=build/'lego_city_undercover_experimental.apworld'
    with zipfile.ZipFile(target) as source,zipfile.ZipFile(alias,'w',zipfile.ZIP_DEFLATED) as dest:
        for entry in source.infolist():
            renamed=zipfile.ZipInfo(entry.filename.replace('lego_city_undercover/','lego_city_undercover_experimental/',1),entry.date_time)
            renamed.compress_type=zipfile.ZIP_DEFLATED;dest.writestr(renamed,source.read(entry.filename))
    manifest=build/'native_items_build.json'
    data=json.loads(manifest.read_text()) if manifest.exists() else {}
    data.update(apworld_filename=target.name,apworld_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),archive_members=len(names),
                apworld_compatibility_filename=alias.name,apworld_compatibility_sha256=hashlib.sha256(alias.read_bytes()).hexdigest())
    data.update(source_client_sha256=hashlib.sha256((WORLD/'Client.py').read_bytes()).hexdigest(),
                common_client_sha256=hashlib.sha256((ROOT/'CommonClient.py').read_bytes()).hexdigest(),
                progressive_astronaut=True,source_requirement_logic=True,native_goal_modes=True,
                native_story_tickets=False,native_district_gates=False,native_open_world_setup=False)
    data.update(native_near_boundary_area_return='experimental; native calls and synthetic fixtures; live movement unverified',
                native_area_return_max_distance=90,area_start='SF_Docks',area_first_pass='SF_Residential',
                sheet_design_requirements_verified=False)
    manifest.write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8')
    print(f'{target}: {len(names)} entries, SHA256 {data["apworld_sha256"]}')


if __name__=='__main__':main()
