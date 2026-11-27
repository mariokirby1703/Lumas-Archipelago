"""Run native pause navigation against synthetic contexts, never a game process."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform=='win32','Windows native fixture')
class PauseMenuNativeTests(unittest.TestCase):
    def test_original_rows_all_fifteen_chapters_and_native_back(self):
        root=Path(__file__).resolve().parents[3]
        output=root/'build/lego_city_undercover'
        output.mkdir(parents=True,exist_ok=True)
        executable=output/'pause_menu_fixture.exe'
        command=[sys.executable,'-m','ziglang','c++','-target','x86_64-windows-gnu','-O2',
            '-I',str(root/'worlds/lego_city_undercover/bridge/native'),
            str(Path(__file__).parent/'native/pause_menu_fixture.cpp'),'-o',str(executable)]
        subprocess.run(command,check=True,capture_output=True,text=True,timeout=60,
            env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(output/'zig-cache'),
                     ZIG_LOCAL_CACHE_DIR=str(output/'zig-local-cache')))
        subprocess.run([str(executable)],check=True,timeout=10,capture_output=True,text=True)
