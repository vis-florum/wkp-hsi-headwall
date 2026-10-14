"""Convert a HELIOS EIFF scan to ENVI and/or NRRD without opening a viewer."""

import argparse
from pathlib import Path

from wkp_hsi.export import write_envi, write_nrrd
from .reader import read_eiff, read_wavelengths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--envi", type=Path, help="Binary raster path (writes an accompanying .hdr)")
    parser.add_argument("--nrrd", type=Path, help="Attached .nrrd output path")
    parser.add_argument("--interleave", choices=("bip", "bil", "bsq"), default="bip")
    parser.add_argument("--nrrd-encoding", choices=("raw", "gzip"), default="gzip")
    parser.add_argument("--omit-wavelengths", action="store_true",
                        help="Export band indices only, omitting the inferred EIFF wavelengths")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing exports")
    args = parser.parse_args(argv)
    if not (args.envi or args.nrrd):
        parser.error("provide --envi and/or --nrrd")
    outputs = ([args.envi, Path(str(args.envi) + ".hdr")] if args.envi else [])
    if args.nrrd:
        outputs.append(args.nrrd)
    if len({p.resolve() for p in outputs}) != len(outputs):
        parser.error("export paths must be distinct")
    if args.file.resolve() in {p.resolve() for p in outputs}:
        parser.error("an output cannot replace the input scan")
    for path in outputs:
        if path.exists() and not args.overwrite:
            parser.error(f"output exists: {path}; use --overwrite to replace it")
    if args.envi and args.envi.suffix.lower() == ".hdr":
        parser.error("--envi must name a binary raster, not a .hdr")
    if args.nrrd and args.nrrd.suffix.lower() != ".nrrd":
        parser.error("--nrrd must have a .nrrd extension")
    try:
        cube = read_eiff(args.file)
        wavelengths = None if args.omit_wavelengths else read_wavelengths(args.file)
        if not args.omit_wavelengths and wavelengths is None:
            parser.error("scan has no wavelength table; use --omit-wavelengths")
        metadata = dict(wavelengths_nm=wavelengths, overwrite=args.overwrite,
                        wavelength_note="" if args.omit_wavelengths else
                        "Inferred EIFF wavelength scale: embedded table / 40 nm; vendor confirmation pending")
        if args.envi:
            paths = write_envi(args.envi, cube, interleave=args.interleave, **metadata)
            print("Saved ENVI: " + ", ".join(map(str, paths)))
        if args.nrrd:
            print(f"Saved NRRD: {write_nrrd(args.nrrd, cube, encoding=args.nrrd_encoding, **metadata)}")
    except (OSError, ValueError, AssertionError) as exc:
        parser.exit(1, f"Export failed: {exc}\n")
    print(f"Exported {cube.shape} {cube.dtype}; stored intensities preserved")


if __name__ == "__main__":
    main()
