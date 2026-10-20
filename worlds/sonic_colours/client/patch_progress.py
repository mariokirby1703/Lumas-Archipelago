"""User-facing patch status, separate from detailed diagnostic output."""
import re

PHASES={
    'Validating original ISO and cached output':'Checking your original ISO…',
    'Verifying original Wii DATA partition integrity':'Checking the original game data…',
    'Extracting the Wii DATA partition':'Reading the original game files…',
    'Preparing reusable verified original partition (first build only)':'Preparing a cache to speed up future patches…',
    'Building all native AP hooks and patch handshake':'Adding Archipelago support…',
    'Building gameplay, maps, Game Land HUD and seed music together':'Preparing the item HUD and randomized music…',
    'Rebuilding Wii filesystem, encrypted DATA partition and hashes':'Creating your playable ISO…',
    'Verifying generated Wii partition integrity':'Checking the new ISO…',
    'Final source and output checksums':'Running the final file checks…',
    'Publishing verified ISO':'Saving your finished ISO…',
    'Reusing verified ISO for this seed':'Your existing ISO is ready to use.',
    'Original cache unavailable/damaged; extracting the original ISO instead':'Reading the original ISO again; the saved cache could not be used…',
    'Patched ISO complete; original untouched. Dolphin gameplay validation is separate.':'Your Archipelago ISO is ready. Your original ISO is unchanged.',
}


class PatchProgress:
    def __init__(self):
        self.message='Preparing your Archipelago ISO…'
        self.detail=''

    def receive(self,line):
        if line in PHASES:
            self.message=PHASES[line];self.detail=''
        elif line.startswith('Checking/copying cached original partition:'):
            self.message='Loading the saved original game files…'
            self.detail=line.partition(': ')[2]
        elif line.startswith('Checking ') and re.search(r'\d+/\d+ MiB$',line):
            self.detail=line.rsplit(': ',1)[-1]
        elif line.startswith('WIT '):
            percent=re.search(r'\b(\d+)%',line)
            eta=re.search(r'\bETA\s+(\d+:\d+(?::\d+)?)',line)
            if percent:
                self.detail=f'{percent[1]}% of this step'
                if eta:self.detail+=f' · Estimated time left for this step: {eta[1]}'
        elif line.startswith('Downloading'):
            self.message='Downloading the required ISO patching tool…';self.detail=''
        elif line.startswith('Keeping existing ISO;'):
            self.message='Keeping your existing ISO and preparing an updated version…';self.detail=''

    def timing(self,seconds):
        seconds=max(0,int(seconds))
        return f'Elapsed: {seconds//60}:{seconds%60:02d}'
