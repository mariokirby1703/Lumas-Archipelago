"""Per-user Windows association; never replaces another application's owner."""
import os
from pathlib import Path
import subprocess
import sys

def register_windows_patch():
    if os.name!='nt':return False
    import winreg
    import Utils
    launcher=Path(Utils.local_path('ArchipelagoLauncher.exe'))
    if launcher.is_file():command=subprocess.list2cmdline([str(launcher)])+' "%1"'
    elif Path(Utils.local_path('Launcher.py')).is_file():
        command=subprocess.list2cmdline([sys.executable,Utils.local_path('Launcher.py')])+' "%1"'
    else:return False
    progid='Archipelago.SonicColours.Patch'
    base=r'Software\Classes'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,base+r'\.apsoniccolours') as key:
            owner=winreg.QueryValueEx(key,'')[0]
            if owner and owner!=progid:return False
    except FileNotFoundError:pass
    for path,value in ((r'\.apsoniccolours',progid),('\\'+progid,'Sonic Colours Archipelago Player Patch'),
                       ('\\'+progid+r'\shell\open\command',command)):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,base+path) as key:
            winreg.SetValueEx(key,'',0,winreg.REG_SZ,value)
    return True
