def read_dol_memory(image, address, size):
    result = bytearray(size)
    for _, _, base, section_size in image.sections:
        start = max(address, base)
        end = min(address + size, base + section_size)
        if start < end:
            result[start - address:end - address] = image.read(start, end - start)
    return bytes(result)
