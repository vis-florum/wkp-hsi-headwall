# Cube export

The existing HELIOS reader returns `cube[scan_line, spatial_pixel, band]`.
The export addon accepts this same array convention, independent of the camera
reader. It preserves sample values, dtype, band order, and optional wavelengths.
It does not perform reflectance calibration, contrast stretching, or resampling.

## Format choice

**ENVI Standard** is the default HSI interchange choice here: a flat binary
raster plus a text `.hdr` containing dimensions, scalar type, byte order,
interleave, and band wavelengths. It is explicitly supported by
[ENVI](https://www.nv5geospatialsoftware.com/docs/enviimagefiles.html),
[GDAL](https://gdal.org/en/stable/drivers/raster/envi.html), and
[Spectral Python](https://www.spectralpython.net/fileio.html).
There is no single universal HSI format; ENVI is a practical choice for
exchanging spectral cubes. TIFF/GeoTIFF is useful for geospatial imagery;
HDF5 and NetCDF suit richer datasets but require a chosen metadata convention.
Those formats are not implemented in this addon.

**NRRD** is a general n-dimensional raster format useful for scientific imaging
and visualization. The addon follows the
[NRRD specification](https://teem.sourceforge.net/nrrd/format.html) and writes
one attached `.nrrd`, with raw or gzip-compressed data. Bands form the third
domain axis of a scalar image stack. Standard geometry fields specify the
wavelength origin and spacing; the exact wavelength table is custom metadata.

## Command line

After `uv sync`, run from the repository root:

```bash
uv run hsi-helios-eiff-export data/helios_eiff/your_scan.eiff \
  --envi outputs/scan.bip --nrrd outputs/scan.nrrd

# Alternative ENVI layouts and uncompressed NRRD:
uv run hsi-helios-eiff-export data/helios_eiff/your_scan.eiff \
  --envi outputs/scan.bsq --interleave bsq \
  --nrrd outputs/scan_raw.nrrd --nrrd-encoding raw
```

Either output can be requested independently. This command runs without a
desktop window and reads the cube once when exporting both formats.
Parent output directories are created. Existing files require `--overwrite`.
The ENVI binary filename is used exactly as supplied; its header has `.hdr`
appended, e.g. `scan.bip.hdr`. Keep both files together. `--interleave` selects
the actual layout regardless of the supplied filename extension.

EIFF wavelengths use the reader's **inferred** embedded-table `/40` nm scale.
The exports record this qualification in `wavelength note` (ENVI) or
`wavelength_note` (NRRD). Use `--omit-wavelengths` to export only band indices.
Intensities remain stored counts with unverified calibration. NRRD uses unit
pixel and scan-line index steps; physical spatial spacing remains unknown.
Its coordinate space mixes image indices and wavelength, not anatomical axes.

## Python addon

```python
from pathlib import Path
from wkp_hsi.helios_eiff import read_eiff, read_wavelengths
from wkp_hsi.export import write_envi, write_nrrd

source = Path("data/helios_eiff/your_scan.eiff")
cube = read_eiff(source)
metadata = dict(
    wavelengths_nm=read_wavelengths(source),
    wavelength_note="Inferred EIFF scale: embedded table / 40 nm",
)
write_envi("outputs/scan.bip", cube, **metadata)
write_nrrd("outputs/scan.nrrd", cube, **metadata)
```

Supported scalar types are uint8, int16/32/64, uint16/32/64, float32/64.
Outputs always use little-endian storage. ENVI supports BIP (default, native
reader order), BIL, and BSQ. NRRD uses BSQ bytes with fastest-first header axes
`(spatial_pixel, scan_line, wavelength)` and `kinds: domain domain domain`.
The third dimension contains band slices, allowing scalar-volume readers to
retain all bands. Each voxel has one intensity component; bands are slices.

NRRD `space dimension`, `space directions`, `space origin`, and `space units`
declare the coordinate scale. The spectral step is `(last - first)/(bands - 1)`;
the origin is the first wavelength. EIFF steps are slightly nonuniform, so this
affine scale is approximate: for the supplied scan the step is
3.1299595141700403 nm and the maximum coordinate error is 0.021053 nm.
`wavelengths_nm` retains every exact coordinate. Values are not resampled.
Without wavelengths the third axis is a unit-spaced band index starting at zero.

This layout is intended for loading as a Scalar Volume in 3D Slicer. Slicer
uses medical spatial coordinates and may present mixed index/nm coordinates as
millimetres; those display labels do not establish physical spatial calibration.
Slicer desktop loading has not been exercised here.

For [pynrrd](https://pynrrd.readthedocs.io/en/stable/background/index-ordering.html):

```python
import nrrd
stack, header = nrrd.read("outputs/scan.nrrd", index_order="C")
cube = stack.transpose(1, 2, 0)  # [band, line, pixel] -> [line, pixel, band].
# Default index_order="F" instead returns [pixel, line, band].
wavelengths_nm = [float(v) for v in header["wavelengths_nm"].split()]
```

NRRD custom keys are `wavelengths_nm` (space-separated values),
`wavelength_units` (`nm`), `wavelength_note`, `wavelength_geometry`,
`wavelength_geometry_max_error_nm`, `spatial_scale_note`, and `intensity_note`.
Generic visualization tools may ignore these keys. Missing wavelength metadata
means only band indices are known. The wavelength axis is spectral, not a
physical depth axis; readers must respect its nm units.

Writers serialize one line or band plane at a time to avoid a second full-cube
copy. The existing EIFF reader still loads the full decoded cube into memory.

## Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests check interleave ordering, endian conversion, dtype preservation,
noncontiguous input, wavelength metadata, raw/gzip NRRD, validation, and
overwrite protection.

The supplied `(2376, 312, 248)` uint16 HELIOS scan was exported to
`outputs/helios_eiff.bip` (with `.hdr`) and `outputs/helios_eiff.nrrd`.
Every exported sample and wavelength was compared against the original reader:
ENVI through Spectral Python's ENVI reader and memory map, and NRRD through
pynrrd with C indexing (transposed back to the original cube convention).
Both matched exactly. The NRRD header was additionally checked for three domain
axes, geometry, origin, units, and wavelength approximation error. Eight tests passed, including
the optional pynrrd read-back test (skipped when pynrrd is absent).
