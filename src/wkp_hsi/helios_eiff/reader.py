"""Read the observed EVK HELIOS EIFF layout and embedded wavelength table."""

from pathlib import Path
import zlib

import numpy as np


def chunks(stream, end):
    """Walk the nested chunks, yielding each leaf's name and bytes."""
    while stream.tell() < end:
        # Each chunk starts with a 10-byte ASCII name and an 8-byte BIG-endian
        # payload length. There is no padding, even for odd payload lengths.
        name = stream.read(10).decode("ascii").strip()
        size = int.from_bytes(stream.read(8), "big")
        chunk_end = stream.tell() + size
        if name in ("LIST", "FORM", "PROP"):
            stream.read(10)  # Container subtype, e.g. SPEHLIOS.
            yield from chunks(stream, chunk_end)
        else:
            yield name, stream.read(size)


def decompress(payload):
    # Compressed leaves in this scan have a 9-byte wrapper followed by zlib.
    # Bytes 4:8 contain the uncompressed length as a LITTLE-endian integer.
    raw = zlib.decompress(payload[9:])
    assert len(raw) == int.from_bytes(payload[4:8], "little")
    return raw


def read_eiff(path):
    """Return uint16 data indexed as cube[scan_line, spatial_pixel, band]."""
    line = 0
    with path.open("rb") as stream:
        for name, payload in chunks(stream, path.stat().st_size):
            if name == "EVKSTNRD":
                # These field offsets were identified from the supplied file.
                bands = int.from_bytes(payload[6:10], "big")
                pixels = int.from_bytes(payload[10:14], "big")
                lines = int.from_bytes(payload[26:30], "big")
                cube = np.empty((lines, pixels, bands), dtype=np.uint16)
            elif name == "BODY":
                # One BODY is one scan line. Samples are LITTLE-endian uint16;
                # all 248 bands of pixel 0 precede all bands of pixel 1, etc.
                samples = np.frombuffer(decompress(payload), dtype="<u2")
                cube[line] = samples.reshape(pixels, bands)
                line += 1
    assert line == lines
    return cube


def read_wavelengths(path):
    """Read the embedded table using the inferred scale of 1/40 nm per unit."""
    with path.open("rb") as stream:
        for name, payload in chunks(stream, path.stat().st_size):
            if name == "EVKWAVTB":
                raw = decompress(payload)
                bands = int.from_bytes(raw[6:8], "little")
                values = np.frombuffer(raw, dtype="<u4", count=bands, offset=8)
                # In this file, /40 yields 929.075–1702.175 nm, matching the
                # camera's specified range. This unit scale is inferred;
                # it has not been confirmed by an EIFF specification.
                return values.astype(float) / 40.0
