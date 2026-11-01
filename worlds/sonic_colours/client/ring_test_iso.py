"""Build a separate, explicit material experiment from an existing native AP ISO."""
import argparse
import os
from pathlib import Path
import tempfile

from .iso_patch import command, disc_header, find_disc_tree, get_wit, sha
from .native_dol import Dol
from .red_ring_render_test import (ALLOCATION_SITE, ORIGINAL, BUFFERED,
                                   FORWARD_SITE, FORWARD_ORIGINAL, FORWARD_BUFFERED)


def build(source, target, wit=None, progress=print):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target or target.exists():
        raise FileExistsError('Choose a new output ISO; the source is never overwritten')
    disc_header(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    wit = get_wit(wit, progress)
    source_hash = sha(source)
    with tempfile.TemporaryDirectory(prefix='.ring-material-test-', dir=target.parent) as directory:
        directory = Path(directory)
        extract = directory / 'disc'
        command(wit, ['EXTRACT', source, extract, '--psel', 'DATA', '--progress'], progress)
        tree = find_disc_tree(extract)
        path = tree / 'sys/main.dol'
        image = Dol(path.read_bytes())
        boot = (tree / 'sys/boot.bin').read_bytes()

        class Backend:
            def read_bytes(self, address, size):
                if 0x80000000 <= address < 0x80000020:
                    return boot[address-0x80000000:address-0x80000000+size]
                try:
                    return image.read(address, size)
                except ValueError:
                    return bytes(size)

        from .memory import SonicMemory
        memory = SonicMemory(Backend())
        memory.verify_revision()
        if not memory.native_patch:
            raise ValueError('Source must be an already patched native AP ISO for your seed')
        image.replace(ALLOCATION_SITE, ORIGINAL, BUFFERED)
        image.replace(FORWARD_SITE, FORWARD_ORIGINAL, FORWARD_BUFFERED)
        memory.verify_revision()
        path.write_bytes(image.data)
        output = directory / 'ring_test.iso'
        command(wit, ['COPY', extract, output, '--iso', '--psel', 'DATA', '--progress'], progress)
        command(wit, ['VERIFY', output, '--psel', 'DATA'], progress)
        disc_header(output)
        if sha(source) != source_hash:
            raise ValueError('Source changed during test build; output not published')
        os.link(output, target)  # Exclusive publication on the same filesystem.
    progress(f'Experimental ISO ready: {target}')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('--wit', type=Path)
    args = parser.parse_args()
    build(args.source, args.target, args.wit)
