"""Build the experimental model-grant DLL; does not load/inject it."""
import argparse
import subprocess
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/lego_city_undercover/LCUItemBridge.dll')
    output=parser.parse_args().output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(ROOT/'worlds/lego_city_undercover/bridge'))
    from native_context_policy import header as context_header
    (output.parent/'native_context_policy.h').write_text(context_header(),encoding='utf-8')
    from purchase_gate import header
    (output.parent/"purchase_gate_patch.h").write_text(header(),encoding="utf-8")
    from category_selection import CATEGORY_PATCHES
    from model_selection import NAVIGATION_PATCHES
    lines=['// Generated from model_selection.py; do not edit.']
    for i,(rva,original,replacement) in enumerate(NAVIGATION_PATCHES+CATEGORY_PATCHES):
        lines.append(f'static constexpr std::uintptr_t navigation_rva_{i}=0x{rva:x};')
        for label,data in (('original',original),('replacement',replacement)):
            values=','.join(f'0x{b:02x}' for b in data)
            lines.append(f'static const unsigned char navigation_{label}_{i}[]={{'+values+'};')
    (output.parent/'booth_selection_patch.h').write_text('\n'.join(lines),encoding='utf-8')
    environment=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(output.parent/'zig-cache'),
                     ZIG_LOCAL_CACHE_DIR=str(output.parent/'zig-local-cache'))
    subprocess.run([sys.executable,'-m','ziglang','c++','-target','x86_64-windows-gnu',
        '-fms-extensions','-shared','-O2','-static-libstdc++',
        '-I',str(output.parent),
        str(ROOT/'worlds/lego_city_undercover/bridge/native/item_bridge.cpp'),
        '-o',str(output),'-luser32'],check=True,env=environment)
    print(output)
