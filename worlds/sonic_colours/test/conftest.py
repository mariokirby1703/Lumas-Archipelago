import pytest

from ..tools.private_assets import reference_root


@pytest.fixture
def pal_dol_bytes():
    path=reference_root()/'memdumps_and_more/main.dol'
    if not path.is_file():
        pytest.skip('Private PAL main.dol not supplied; original game files are not distributed')
    return path.read_bytes()


@pytest.fixture
def pal_executable():
    path=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.is_file():
        pytest.skip('Private PAL disassembly ELF not supplied; original game files are not distributed')
    from ..tools.ppc import Executable
    return Executable(path)
