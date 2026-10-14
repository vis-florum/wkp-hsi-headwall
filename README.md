# wkp-hsi-headwall

Simple Python readers and viewers for hyperspectral camera files. Each camera
and file format has its own use case under `src/wkp_hsi/`. The first use case
reads **EVK / Headwall HELIOS EIFF** scans; further formats can be added alongside
it without changing its reader.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then from
the repository root run:

```bash
./setup.sh
```

The script runs `uv sync --python 3.12`, creating `.venv` and installing this
package, NumPy, and Matplotlib. It also generates `uv.lock`, which can be committed
to share dependency versions. Internet access is needed for initial downloads.
No environment activation is required.

## Use case: HELIOS EIFF

Place your scan in `data/helios_eiff/`. The original scan is local data and is
not included in the GitHub repository.

```bash
# Open the original sample's filename from data/helios_eiff/.
uv run hsi-helios-eiff

# Or open a specific file.
uv run hsi-helios-eiff data/helios_eiff/your_scan.eiff

# Save a preview without opening a desktop window.
uv run hsi-helios-eiff --save outputs/helios_eiff_preview.png
```

Move the band slider to browse the cube. Click a pixel to view its spectrum.
The Colormap button cycles through Viridis, Inferno, Gray, Plasma, Magma, and
Cividis. A red point and thin dotted line mark the selected band on the spectrum.

The spectrum uses **estimated wavenumber (cm⁻¹)** derived from the embedded
wavelength table. The scale is inferred and remains unconfirmed by vendor format
documentation. Stored intensities are displayed without claiming reflectance units.
See [the HELIOS EIFF notes](docs/use_cases/helios_eiff.md) for the byte layout,
conversion, validation, and limitations.

## Export the decoded cube

Export to **ENVI Standard** (binary raster + `.hdr`) and/or **NRRD**, without
opening the viewer:

```bash
uv run hsi-helios-eiff-export data/helios_eiff/your_scan.eiff \
  --envi outputs/scan.bip --nrrd outputs/scan.nrrd
```

ENVI defaults to BIP; `--interleave bil` or `--interleave bsq` selects another
layout. NRRD defaults to gzip; `--nrrd-encoding raw` disables compression.
Stored intensities and dtype are preserved. Exported wavelengths carry the
inferred-scale note; `--omit-wavelengths` leaves them out. Existing exports
require `--overwrite`. See [format choices, Python API, and axis conventions](docs/export.md).

## Layout

```text
data/
  helios_eiff/             # Local scan files; ignored by Git.
docs/
  use_cases/helios_eiff.md # Camera/format notes.
outputs/                  # Generated previews and arrays; ignored by Git.
src/
  wkp_hsi/
    helios_eiff/
      reader.py           # Chunk decoding and wavelength table.
      viewer.py           # Interactive display and PNG export.
pyproject.toml            # Package, dependencies, and viewer command.
setup.sh                  # uv initialization.
```

## Add another camera or format

Add a sibling package such as `src/wkp_hsi/another_format/`, with its reader and
viewer. Keep format notes in `docs/use_cases/` and local scans in a matching
`data/` subdirectory. Register another viewer command in
`[project.scripts]` in `pyproject.toml`, then run `uv sync`.

Readers return NumPy arrays; the HELIOS cube uses
`cube[scan_line, spatial_pixel, band]`. Keep each reader's assumptions documented
in its use case. There is currently no shared format registry or processing engine.

`.gitignore` excludes all local data and outputs plus common large formats such
as EIFF, TIFF, ENVI cubes, NumPy arrays, MATLAB files, HDF5, NetCDF, and archives.

## Verification in the original workspace

The HELIOS scan was decoded and rendered in full. Viewer callbacks were checked
for band selection, pixel selection, and colormap changes. Initial package
downloads were unavailable in the restricted workspace, so rendering was also
checked with the already-installed dependencies:

```bash
PYTHONPATH=src uv run --no-project python -m wkp_hsi.helios_eiff.viewer \
  --save outputs/helios_eiff_preview.png
```
