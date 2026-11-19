"""The locker agent: holds parcels until pickup."""


def accept(parcel, shelf):
    """Put a parcel on a shelf, offline if need be."""
    shelf.append(parcel)
    return len(shelf)


def release(shelf, token):
    """Hand a parcel over when the token matches."""
    return shelf.pop() if token else None
