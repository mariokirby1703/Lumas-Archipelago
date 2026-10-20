"""Transactional player-owned Wii ISO build using Wiimms ISO Tools.

No original game files are shipped. All extraction, hashes and transformed
resources are local. WIT rebuilds FST, encrypted clusters and partition hashes.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
import time
from .iso_cache import check_cancel,restore as restore_original,store as store_original
from .native_dol import patch_dol,PAL_DOL_SHA256,plan
from .asset_patch import PAL_CPK_SHA256

logger=logging.getLogger('Client')
WIT_URL='https://wit.wiimm.de/download/wit-v3.05a-r8638-cygwin64.zip'
WIT_SHA256='049670558970f0cea2796d68e0ba1e48491474b5708bf12a95ab8a185f4e59c1'

def sha(path,progress=None,cancel=None):
    digest=hashlib.sha256();path=Path(path);total=path.stat().st_size;done=0;last=0
    with path.open('rb') as f:
        while chunk:=f.read(4*1024*1024):
            check_cancel(cancel);digest.update(chunk);done+=len(chunk)
            if progress and time.monotonic()-last>=.5:
                progress(f'Checking {path.name}: {done//1048576}/{total//1048576} MiB');last=time.monotonic()
    return digest.hexdigest()


def original_cache_path():
    import Utils
    return Path(Utils.user_path('sonic_colours_cache','original-v1'))

def disc_header(path):
    path=Path(path)
    if path.suffix.lower()!='.iso':raise ValueError('Only uncompressed .iso disc images are supported')
    with path.open('rb') as f:header=f.read(32)
    if len(header)!=32 or header[:6]!=b'SNCP8P' or header[7]!=0 or header[24:28]!=bytes.fromhex('5d1c9ea3'):
        raise ValueError('Original Sonic Colours Wii PAL SNCP8P Revision 0 ISO required')
    return header

def settings_group():
    from settings import get_settings
    from ..world import SonicColoursWorld
    return get_settings()[SonicColoursWorld.settings_key]

def get_wit(explicit=None,progress=lambda s:None):
    if explicit:
        result=Path(explicit).resolve()
        if not result.is_file():raise FileNotFoundError('Configured WIT executable does not exist')
        return result
    found=shutil.which('wit')
    if found:return Path(found)
    if os.name!='nt':raise FileNotFoundError('Install Wiimms ISO Tools and set sonic_colours_options.wit_path or put wit on PATH')
    import Utils
    cache=Path(Utils.user_path('sonic_colours_tools','wit-3.05a'))
    executable=cache/'wit-v3.05a-r8638-cygwin64'/'bin'/'wit.exe'
    if executable.is_file():return executable
    progress('Downloading verified Wiimms ISO Tools (GPL, wiimm.de)')
    cache.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wit-',dir=cache.parent) as tmp:
        tmp=Path(tmp);archive=tmp/'wit.zip'
        with urllib.request.urlopen(WIT_URL,timeout=60) as source,archive.open('wb') as out:
            shutil.copyfileobj(source,out)
        if sha(archive)!=WIT_SHA256:raise ValueError('Wiimms tool download integrity check failed')
        unpack=tmp/'unpack';unpack.mkdir()
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                dest=(unpack/info.filename).resolve()
                if not dest.is_relative_to(unpack.resolve()):raise ValueError('unsafe tool archive path')
            z.extractall(unpack)
        if not (unpack/executable.relative_to(cache)).is_file():raise ValueError('WIT archive lacks executable')
        if cache.exists():raise FileExistsError('tool cache changed while downloading')
        unpack.rename(cache)
    return executable

def command(wit,args,progress,cancel=None):
    import queue
    import threading
    from .patch_progress import PatchProgress
    display=PatchProgress()
    from collections import deque
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    process=subprocess.Popen([str(wit),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                             text=True,encoding='utf-8',errors='replace',**flags)
    messages=queue.Queue();tail=deque(maxlen=80)
    def read_output():
        try:
            for line in process.stdout:messages.put(line.rstrip())
        finally:messages.put(None)
    reader=threading.Thread(target=read_output,daemon=True);reader.start()
    try:
        last=0
        while True:
            check_cancel(cancel)
            try:line=messages.get(timeout=.1)
            except queue.Empty:continue
            if line is None:break
            tail.append(line)
            if line and time.monotonic()-last>=.25:
                progress(f'WIT {args[0]}: {line[-240:]}');last=time.monotonic()
        while process.poll() is None:
            check_cancel(cancel)
            try:process.wait(timeout=.1)
            except subprocess.TimeoutExpired:pass
        output='\n'.join(tail)
        if process.returncode:raise RuntimeError(f'WIT {args[0]} failed ({process.returncode}):\n{output[-6000:]}')
        logger.info('%s',output.strip())
    finally:
        if process.poll() is None:process.kill();process.wait()
        reader.join();process.stdout.close()

def find_disc_tree(root):
    rows=list(Path(root).rglob('sys/main.dol'))
    if len(rows)!=1:raise ValueError('ISO must contain precisely one extracted DATA main.dol')
    tree=rows[0].parent.parent
    if not (tree/'files/sonic2010_0.cpk').is_file():raise ValueError('DATA partition lacks sonic2010_0.cpk')
    return tree

def install(patch,source=None,target=None,wit=None,progress=None,cancel=None,cache_dir=None):
    from ..patch import resource_component_id,EQUIVALENT_RESOURCES,EQUIVALENT_RESOURCE_TARGET
    progress=progress or (lambda text:logger.info('Sonic ISO: %s',text))
    started=time.monotonic();phase_started=started;current_phase=None;timings={}
    def phase(text):
        nonlocal phase_started,current_phase
        now=time.monotonic()
        if current_phase is not None:timings[current_phase]=round(now-phase_started,3)
        current_phase=text;phase_started=now;progress(text)
    if patch.slot_data is None:patch.read()
    group=None
    if source is None:
        group=settings_group();source=str(group.iso_file)
    source=Path(source).resolve();disc_header(source)
    default_target=target is None
    target=Path(target or Path(patch.path).with_suffix('.iso')).resolve()
    if target==source:raise ValueError('The original ISO must never be the output')
    if target.suffix.lower()!='.iso':raise ValueError('Output must be a separate .iso')
    target.parent.mkdir(parents=True,exist_ok=True)
    receipt=Path(str(target)+'.sonic.json')
    seed_data={'game':patch.game,'player':patch.player,'player_name':patch.player_name,'slot_data':patch.slot_data}
    identity=hashlib.sha256(json.dumps(seed_data,sort_keys=True).encode()).hexdigest()
    resources=resource_component_id()
    compatible_resources={resources}
    if resources==EQUIVALENT_RESOURCE_TARGET:compatible_resources.update(EQUIVALENT_RESOURCES)
    phase('Validating original ISO and cached output')
    source_hash=sha(source,progress,cancel)
    if target.exists() or receipt.exists():
        if target.is_file() and receipt.is_file():
            record=json.loads(receipt.read_text(encoding='utf-8'))
            if (record.get('identity')==identity and record.get('source_iso_sha256')==source_hash
                    and record.get('native_component_sha256')==plan()[2].hex() and record.get('pipeline_version')==1
                    and record.get('resource_component_sha256') in compatible_resources
                    and record.get('output_iso_sha256')==sha(target,progress,cancel)):
                progress('Reusing verified ISO for this seed');return target
        if default_target:
            # Keep an old ABI/resource build intact. A component-specific name
            # also makes repeated Open Patch calls reuse the upgraded image.
            suffix=hashlib.sha256((plan()[2].hex()+resource_component_id()).encode()).hexdigest()[:10]
            upgraded=target.with_name(target.stem+'-ap-'+suffix+'.iso')
            progress('Keeping existing ISO; building/reusing updated components at '+str(upgraded))
            return install(patch,source=source,target=upgraded,wit=wit,progress=progress,cancel=cancel,cache_dir=cache_dir)
        raise FileExistsError('Output already exists and is not a verified cache match; choose another output path')
    # Extraction, a separate CPK and the output image coexist during validation.
    required=source.stat().st_size*3+2*1024**3
    if shutil.disk_usage(target.parent).free<required:raise OSError(f'Not enough free disk space: need approximately {required//1024**3} GiB')
    configured=vars(group).get('wit_path','') if group else ''
    wit=get_wit(wit or (str(configured) if configured else None),progress)
    command(wit,['VERSION'],progress,cancel)
    with tempfile.TemporaryDirectory(prefix='.sonic-build-',dir=target.parent) as directory:
        tmp=Path(directory);extract=tmp/'source'
        cache=(original_cache_path() if cache_dir is None else Path(cache_dir)) if cache_dir is not False else None
        cached=bool(cache and restore_original(cache,extract,source_hash,progress,cancel))
        if not cached:
            phase('Verifying original Wii DATA partition integrity')
            command(wit,['VERIFY',source,'--psel','DATA'],progress,cancel)
            phase('Extracting the Wii DATA partition')
            command(wit,['EXTRACT',source,extract,'--psel','DATA','--progress'],progress,cancel)
        tree=find_disc_tree(extract);dol=tree/'sys/main.dol';cpk=tree/'files/sonic2010_0.cpk'
        boot=(tree/'sys/boot.bin').read_bytes()
        if boot[:6]!=b'SNCP8P' or boot[7]!=0:raise ValueError('DATA partition game/revision differs')
        if sha(dol)!=PAL_DOL_SHA256 or sha(cpk)!=PAL_CPK_SHA256:raise ValueError('Original main.dol or CPK checksum mismatch; modified/unsupported ISO')
        if cache and not cached:
            # Optional acceleration must not make an otherwise valid build fail
            # on a full/read-only cache volume. Leave room for the actual build.
            size=sum(p.stat().st_size for p in extract.rglob('*') if p.is_file())
            try:
                cache.mkdir(parents=True,exist_ok=True)
                room=shutil.disk_usage(cache).free
                same_volume=os.stat(cache).st_dev==os.stat(tmp).st_dev
                reserve=required if same_volume else 1024**3
                if room>=size+reserve:
                    phase('Preparing reusable verified original partition (first build only)')
                    store_original(cache,extract,source_hash,cancel)
                else:progress('Skipping optional original cache: keeping free space for the ISO build')
            except InterruptedError:raise
            except OSError as error:logger.warning('Optional original cache not saved: %s',error)
        check_cancel(cancel)
        phase('Building all native AP hooks and patch handshake')
        native,registry=patch_dol(dol.read_bytes(),patch.slot_data['seed_name']);dol.write_bytes(native)
        mapping=None
        if patch.slot_data['options']['music_randomization']:
            from .music_bank import slot_plan
            mapping=slot_plan(patch.slot_data)
        phase('Building gameplay, maps, Game Land HUD and seed music together')
        from ..tools.build_hud_overlay import build
        modified=tmp/'sonic2010_0.cpk'
        build(cpk,modified,include_maps=True,ap_connected=True,music_mapping=mapping,music_mapping_version=patch.slot_data.get('music_mapping_version',1),write_xml=False)
        check_cancel(cancel)
        modified.replace(cpk)
        phase('Rebuilding Wii filesystem, encrypted DATA partition and hashes')
        output=tmp/'patched.iso'
        command(wit,['COPY',extract,output,'--iso','--psel','DATA','--progress'],progress,cancel)
        disc_header(output)
        phase('Verifying generated Wii partition integrity')
        command(wit,['VERIFY',output,'--psel','DATA'],progress,cancel)
        phase('Final source and output checksums')
        if sha(source,progress,cancel)!=source_hash:raise ValueError('Source ISO changed during build; refusing finalization')
        if cancel and cancel.is_set():raise InterruptedError('ISO build cancelled')
        record={**seed_data,'identity':identity,'pipeline_version':1,'native_component_sha256':plan()[2].hex(),
                'resource_component_sha256':resource_component_id(),
                'source_iso_sha256':source_hash,'output_iso_sha256':sha(output,progress,cancel),
                'patched_dol_sha256':sha(dol),'patched_cpk_sha256':sha(cpk),
                'native_registry':registry,'music_mapping':mapping,'boot_verified':False,'live_verified':False,
                'original_cache_used':cached}
        phase('Publishing verified ISO')
        record['build_timings_seconds']=timings
        record['build_elapsed_seconds']=round(time.monotonic()-started,3)
        meta=tmp/'result.json';meta.write_text(json.dumps(record,indent=2),encoding='utf-8')
        # Never replace existing destinations, including a concurrent installer.
        os.link(output,target) # same filesystem, atomic and refuses replacement
        try:
            with receipt.open('x',encoding='utf-8') as f:f.write(meta.read_text(encoding='utf-8'))
        except BaseException:target.unlink();raise
    if group:
        group.iso_file=type(group.iso_file)(str(source))
        from settings import get_settings
        get_settings().save()
    progress('Patched ISO complete; original untouched. Dolphin gameplay validation is separate.')
    return target

def install_with_progress(patch,**kwargs):
    """GUI event thread remains responsive while WIT/local builds run."""
    import queue
    import threading
    messages=queue.Queue();cancel=threading.Event();result=[];errors=[]
    group=None
    if not kwargs.get('source'):
        group=settings_group()
        kwargs['source']=str(group.iso_file) # file selection belongs to GUI thread
        if not kwargs.get('wit'):kwargs['wit']=str(vars(group).get('wit_path','')) or None
    try:
        import tkinter as tk
        from tkinter import ttk
        root=tk.Tk();root.title('Sonic Colours Archipelago ISO Patcher')
        label=ttk.Label(root,text=display.message,wraplength=500);label.pack(padx=24,pady=20)
        detail=ttk.Label(root,text='',wraplength=500);detail.pack(padx=24)
        elapsed=ttk.Label(root,text='Elapsed: 0:00');elapsed.pack()
        ttk.Label(root,text='Patching time depends on your drive and whether files are already cached.',
                  wraplength=450).pack(padx=24,pady=8)
        bar=ttk.Progressbar(root,mode='indeterminate',length=450);bar.pack(padx=24,pady=12);bar.start()
        def request_cancel():
            cancel.set();label.config(text='Cancelling safely; temporary files will be removed...')
            detail.config(text='')
        ttk.Button(root,text='Cancel',command=request_cancel).pack(pady=12)
        root.protocol('WM_DELETE_WINDOW',request_cancel)
    except Exception:
        installed=install(patch,**kwargs)
        if group:
            group.iso_file=type(group.iso_file)(kwargs['source'])
            from settings import get_settings
            get_settings().save()
        return installed
    def worker():
        try:result.append(install(patch,progress=messages.put,cancel=cancel,**kwargs))
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=worker,daemon=True);thread.start()
    gui_started=time.monotonic()
    def update():
        while True:
            try:display.receive(messages.get_nowait())
            except queue.Empty:break
        if not cancel.is_set():
            label.config(text=display.message);detail.config(text=display.detail)
        seconds=int(time.monotonic()-gui_started)
        elapsed.config(text=display.timing(seconds))
        if thread.is_alive():root.after(100,update)
        else:root.destroy()
    update();root.mainloop();thread.join()
    if errors:raise errors[0]
    if group:
        group.iso_file=type(group.iso_file)(kwargs['source'])
        from settings import get_settings
        get_settings().save()
    return result[0]
