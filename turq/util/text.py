def force_str(x, encoding='iso-8859-1'):
    if isinstance(x, bytes):
        return x.decode(encoding)
    else:
        return str(x)


def force_bytes(x, encoding='iso-8859-1'):
    if isinstance(x, bytes):
        return x
    else:
        return x.encode(encoding)
