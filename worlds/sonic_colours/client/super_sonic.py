AUTO_UNLOCK = 0x8016C2DC
AUTO_UNLOCK_END = 0x8016C350


def patches(control=None, occupied=()):
    from .native_dol import branch
    result = [(AUTO_UNLOCK, bytes.fromhex('38610008'),
               branch(AUTO_UNLOCK, AUTO_UNLOCK_END).to_bytes(4, 'big'))]
    if control is None:
        return result
    from .capsule_refresh import PPC
    from .native_events import scatter_mixed
    from ..world_constants import load_data
    a = PPC()
    # Bit 7 is the Super Sonic permission. Native saves (including older saves
    # with every Game Land clear) must not override the AP permission mailbox.
    a.d(11, 0, 4, 7)
    a.branch('original', 0x40820000)
    a.d(15, 3, 0, control >> 16)
    a.d(24, 3, 3, control & 0xffff)
    a.d(32, 3, 3, 8)
    a.emit(0x5463CFFE)  # rlwinm r3,r3,25,31,31: bit 7
    a.emit(0x4E800020)
    a.label('original')
    a.emit(0x80C30000)  # displaced lwz r6,0(r3)
    a.emit(0)
    words = a.finish()
    sites = [s for s in load_data('native_event_sites.json')
             if not any(p < s['address'] + 12 and s['address'] < p + len(new)
                        for p, _, new in (*occupied, *result))]
    code, _ = scatter_mixed(words, sites, 0x8015ED10)
    result.extend(code)
    result.append((0x8015ED0C, bytes.fromhex('80c30000'),
                   branch(0x8015ED0C, code[0][0]).to_bytes(4, 'big')))
    a = PPC()
    a.d(15, 5, 0, control >> 16)
    a.d(24, 5, 5, control & 0xffff)
    a.d(32, 5, 5, 8)
    a.d(28, 5, 5, 0x80)
    a.branch('original', 0x40820000)
    a.d(14, 3, 0, 0)
    a.emit(0x4E800020)
    a.label('original')
    a.emit(0x9421FFF0)
    a.emit(0)
    sites = [s for s in load_data('native_event_sites.json')
             if not any(p < s['address'] + 12 and s['address'] < p + len(new)
                        for p, _, new in (*occupied, *result))]
    code, _ = scatter_mixed(a.finish(), sites, 0x803125CC)
    result.extend(code)
    result.append((0x803125C8, bytes.fromhex('9421fff0'),
                   branch(0x803125C8, code[0][0]).to_bytes(4, 'big')))
    return result
