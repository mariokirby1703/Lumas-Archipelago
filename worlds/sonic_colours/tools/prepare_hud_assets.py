"""Hash-gated extraction of privately owned PAL HUD resources.

This prepares inputs for the GNCP/TLS rewriter; it does not produce a renderer.
Never overwrite a source archive or commit the extracted Nintendo resources.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def prepare(source, output):
    source=Path(source).resolve(); output=Path(output).resolve()
    if output.exists():
        raise ValueError('output must be a new directory')
    if source == output or output in source.parents:
        raise ValueError('output must not contain the source archive')
    scripts_dir=Path(__file__).resolve().parent
    # These helpers import neighbouring scripts. Restore sys.path when done.
    previous=list(sys.path)
    try:
        sys.path.insert(0,str(scripts_dir))
        spec=importlib.util.spec_from_file_location('sonic_hud_preflight',scripts_dir/'hud_preflight.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        report=module.audit(source)
        archive=module.CPK(source)
        resources={}
        for arc, names in [('ui_cockpit_e.arc',('ui_gameplay.gncp','ui_gameplay.tls')),
                           ('ui_name_entry_e.arc',('ui_soft_keyboard.gncp','ui_soft_keyboard.tls'))]:
            for name in names:
                resources[name]=module.find_asset(archive,arc,name)
    finally:
        sys.path[:]=previous
    report['resources']={name:{'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
                         for name,blob in resources.items()}
    report['renderer_built']=False
    report['next_required']='TLS relocation audit and GNCP font/cast rewriter'
    output.mkdir(parents=True)
    (output/'.gitignore').write_text('*\n',encoding='ascii')
    for name,blob in resources.items():(output/name).write_bytes(blob)
    (output/'preflight.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cpk',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    print(json.dumps(prepare(args.cpk,args.output),indent=2))
