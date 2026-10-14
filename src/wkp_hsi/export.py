"""Lossless ENVI and NRRD writers for cube[line, pixel, band] arrays."""

import gzip
from pathlib import Path

import numpy as np


# NumPy type: (ENVI code, NRRD scalar type). Always write little-endian data.
_TYPES = {
    "u1": (1, "uint8"), "i2": (2, "int16"), "i4": (3, "int32"),
    "f4": (4, "float"), "f8": (5, "double"), "u2": (12, "uint16"),
    "u4": (13, "uint32"), "i8": (14, "int64"), "u8": (15, "uint64"),
}


def _validate(cube, wavelengths_nm, wavelength_note):
    cube = np.asarray(cube)
    if cube.ndim != 3 or any(size == 0 for size in cube.shape):
        raise ValueError("cube must have nonempty (line, pixel, band) dimensions")
    key = f"{cube.dtype.kind}{cube.dtype.itemsize}"
    if key not in _TYPES:
        raise ValueError(f"Unsupported cube dtype: {cube.dtype}")
    wavelengths = None
    if wavelengths_nm is not None:
        wavelengths = np.asarray(wavelengths_nm, dtype=float)
        if (wavelengths.shape != (cube.shape[2],)
                or not np.all(np.isfinite(wavelengths))
                or np.any(wavelengths <= 0)):
            raise ValueError("wavelengths_nm must contain one finite positive value per band")
    if not wavelength_note.isascii() or any(c in wavelength_note for c in "\r\n{}\\"):
        raise ValueError("wavelength_note must be single-line ASCII without braces or backslashes")
    return cube, wavelengths, key


def _prepare(paths, overwrite):
    for path in paths:
        if path.exists() and not overwrite:
            raise FileExistsError(f"Output exists: {path}; use overwrite=True or --overwrite")
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def _write_blocks(stream, blocks, dtype):
    # Convert at most one line/plane at a time, avoiding another full cube copy.
    for block in blocks:
        stream.write(np.asarray(block, dtype=dtype).tobytes(order="C"))


def write_envi(path, cube, *, wavelengths_nm=None, wavelength_note="",
               interleave="bip", overwrite=False):
    """Write a binary raster and appended .hdr; return (data_path, header_path).

    `path` names the binary file (e.g. scan.bip). BIP is the reader's native
    ordering; BIL and BSQ are also supported. No scaling or calibration is done.
    """
    cube, wavelengths, key = _validate(cube, wavelengths_nm, wavelength_note)
    if interleave not in ("bip", "bil", "bsq"):
        raise ValueError("interleave must be bip, bil, or bsq")
    path = Path(path)
    if path.suffix.lower() == ".hdr":
        raise ValueError("ENVI path must name the binary raster, not its .hdr")
    header_path = Path(str(path) + ".hdr")
    lines, pixels, bands = cube.shape
    header = ["ENVI", "description = {Stored hyperspectral intensities; no calibration applied.}",
              f"samples = {pixels}", f"lines = {lines}", f"bands = {bands}",
              "header offset = 0", "file type = ENVI Standard",
              f"data type = {_TYPES[key][0]}", f"interleave = {interleave}", "byte order = 0"]
    if wavelengths is not None:
        header += ["wavelength units = Nanometers",
                   "wavelength = {" + ", ".join(format(v, ".17g") for v in wavelengths) + "}"]
    if wavelength_note:
        header.append(f"wavelength note = {{{wavelength_note}}}")
    _prepare((path, header_path), overwrite)
    if interleave == "bip":
        blocks = iter(cube)
    elif interleave == "bil":
        blocks = (line.T for line in cube)
    else:
        blocks = (cube[:, :, band] for band in range(bands))
    with path.open("wb" if overwrite else "xb") as stream:
        _write_blocks(stream, blocks, cube.dtype.newbyteorder("<"))
    with header_path.open("w" if overwrite else "x", encoding="ascii") as stream:
        stream.write("\n".join(header) + "\n")
    return path, header_path


def write_nrrd(path, cube, *, wavelengths_nm=None, wavelength_note="",
               encoding="gzip", overwrite=False):
    """Write an attached NRRD, returning its path; encoding is raw or gzip.

    NRRD axes are fastest-first: (pixel, line, wavelength). Bands form the
    third domain axis, not vector components. A C-order reader returns
    (band, line, pixel); transpose(1, 2, 0) restores the input convention.
    Geometry uses pixel/line indices and an endpoint-affine wavelength axis;
    the exact, potentially nonuniform wavelength table is retained separately.
    """
    cube, wavelengths, key = _validate(cube, wavelengths_nm, wavelength_note)
    if encoding not in ("raw", "gzip"):
        raise ValueError("encoding must be raw or gzip")
    path = Path(path)
    if path.suffix.lower() != ".nrrd":
        raise ValueError("Attached NRRD output must have a .nrrd extension")
    lines, pixels, bands = cube.shape
    step, origin, spectral_units = 1.0, 0.0, "band"
    approximation_error = 0.0
    if wavelengths is not None:
        origin, spectral_units = float(wavelengths[0]), "nm"
        if bands > 1:
            differences = np.diff(wavelengths)
            if not (np.all(differences > 0) or np.all(differences < 0)):
                raise ValueError("NRRD wavelength coordinates must be strictly monotonic")
            step = float((wavelengths[-1] - wavelengths[0]) / (bands - 1))
            approximation_error = float(np.max(np.abs(
                wavelengths - (origin + np.arange(bands) * step))))
    header = ["NRRD0005", f"type: {_TYPES[key][1]}", "dimension: 3",
              f"sizes: {pixels} {lines} {bands}", "kinds: domain domain domain",
              'labels: "spatial_pixel" "scan_line" "wavelength"' if wavelengths is not None
              else 'labels: "spatial_pixel" "scan_line" "band"',
              "space dimension: 3",
              f"space directions: (1,0,0) (0,1,0) (0,0,{step:.17g})",
              f"space origin: (0,0,{origin:.17g})",
              f'space units: "pixel" "scan_line" "{spectral_units}"',
              f"encoding: {encoding}", "sample units: \"stored intensity\"",
              "spatial_scale_note:=Index coordinates; physical pixel and scan-line spacing unknown",
              "intensity_note:=Stored values; no calibration applied"]
    if cube.dtype.itemsize > 1:
        header.append("endian: little")
    if wavelengths is not None:
        header += ["wavelength_units:=nm",
                   "wavelength_geometry:=Endpoint-affine approximation; exact coordinates in wavelengths_nm",
                   f"wavelength_geometry_max_error_nm:={approximation_error:.17g}",
                   "wavelengths_nm:=" + " ".join(format(v, ".17g") for v in wavelengths)]
    if wavelength_note:
        header.append(f"wavelength_note:={wavelength_note}")
    _prepare((path,), overwrite)
    with path.open("wb" if overwrite else "xb") as stream:
        stream.write(("\n".join(header) + "\n\n").encode("ascii"))
        if encoding == "gzip":
            with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as compressed:
                _write_blocks(compressed, (cube[:, :, b] for b in range(bands)),
                              cube.dtype.newbyteorder("<"))
        else:
            _write_blocks(stream, (cube[:, :, b] for b in range(bands)),
                          cube.dtype.newbyteorder("<"))
    return path
