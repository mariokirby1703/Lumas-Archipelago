AUTO_UNLOCK = 0x8016C2DC
AUTO_UNLOCK_END = 0x8016C350


def patches():
    from .native_dol import branch
    return [(AUTO_UNLOCK, bytes.fromhex('38610008'),
             branch(AUTO_UNLOCK, AUTO_UNLOCK_END).to_bytes(4, 'big'))]
