"""Check axis ordering, metadata and lossless export without extra dependencies."""

import gzip
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import numpy as np

from wkp_hsi.export import write_envi, write_nrrd
from wkp_hsi.helios_eiff.export import main


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cube = (np.arange(30).reshape(2, 3, 5) * 137).astype(">u2")
        self.wavelengths = np.array([929.075, 932.2, 935.4, 938.5, 941.6])

    def test_envi_interleaves_and_endianness(self):
        for interleave, shape, axes in [
            ("bip", (2, 3, 5), (0, 1, 2)),
            ("bil", (2, 5, 3), (0, 2, 1)),
            ("bsq", (5, 2, 3), (1, 2, 0)),
        ]:
            with self.subTest(interleave=interleave):
                path, hdr = write_envi(self.root / interleave, self.cube,
                                      interleave=interleave, wavelengths_nm=self.wavelengths,
                                      wavelength_note="Inferred")
                data = np.fromfile(path, dtype="<u2").reshape(shape).transpose(axes)
                np.testing.assert_array_equal(data, self.cube)
                header = hdr.read_text()
                for field in ["samples = 3", "lines = 2", "bands = 5",
                              "data type = 12", "byte order = 0", "wavelength note = {Inferred}"]:
                    self.assertIn(field, header)
                values = header.split("wavelength = {")[1].split("}")[0]
                np.testing.assert_array_equal(np.fromstring(values, sep=","), self.wavelengths)

    def test_nrrd_axis_order_and_encodings(self):
        for encoding in ("raw", "gzip"):
            with self.subTest(encoding=encoding):
                path = write_nrrd(self.root / f"{encoding}.nrrd", self.cube,
                                  wavelengths_nm=self.wavelengths, encoding=encoding)
                header, payload = path.read_bytes().split(b"\n\n", 1)
                self.assertIn(b"sizes: 3 2 5", header)
                self.assertIn(b"kinds: domain domain domain", header)
                if encoding == "gzip":
                    payload = gzip.decompress(payload)
                np.testing.assert_array_equal(
                    np.frombuffer(payload, dtype="<u2").reshape(5, 2, 3).transpose(1, 2, 0), self.cube)

    def test_types_noncontiguous_arrays(self):
        for dtype in ("u1", "i2", "i4", "f4", "f8", "u2", "u4", "i8", "u8"):
            cube = self.cube.astype(dtype)[:, ::-1, :]
            path, _ = write_envi(self.root / dtype, cube)
            np.testing.assert_array_equal(
                np.fromfile(path, dtype=np.dtype(dtype).newbyteorder("<")).reshape(cube.shape), cube)

    def test_validation_before_writing(self):
        for cube, wavelengths in [(np.zeros((2, 3)), None),
                                  (np.zeros((2, 0, 3)), None),
                                  (self.cube.astype(bool), None),
                                  (self.cube, [1, 2]),
                                  (self.cube, [1, 2, 3, 4, float("nan")])]:
            with self.subTest(shape=cube.shape), self.assertRaises(ValueError):
                write_envi(self.root / "invalid", cube, wavelengths_nm=wavelengths)
        self.assertFalse((self.root / "invalid").exists())

    def test_existing_header_prevents_data_write(self):
        path = self.root / "scan.bip"
        hdr = Path(str(path) + ".hdr")
        hdr.write_text("keep")
        with self.assertRaises(FileExistsError):
            write_envi(path, self.cube)
        self.assertFalse(path.exists())
        write_envi(path, self.cube, overwrite=True)
        self.assertTrue(hdr.read_text().startswith("ENVI\n"))

    def test_nrrd_overwrite(self):
        path = write_nrrd(self.root / "scan.nrrd", self.cube)
        with self.assertRaises(FileExistsError):
            write_nrrd(path, self.cube)
        write_nrrd(path, self.cube, overwrite=True)

    def test_cli_requires_output_and_protects_input(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            main(["scan.eiff"])
        self.assertEqual(exc.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            main(["scan.eiff", "--envi", "scan.eiff", "--overwrite"])
        self.assertEqual(exc.exception.code, 2)

    def test_independent_nrrd_reader_if_installed(self):
        try:
            import nrrd
        except ImportError:
            self.skipTest("Optional pynrrd is not installed")
        for encoding in ("raw", "gzip"):
            path = write_nrrd(self.root / f"external_{encoding}.nrrd", self.cube,
                              wavelengths_nm=self.wavelengths, encoding=encoding)
            cube, header = nrrd.read(str(path), index_order="C")
            np.testing.assert_array_equal(cube.transpose(1, 2, 0), self.cube)
            self.assertEqual(cube.dtype, np.dtype("uint16"))
            self.assertEqual(header["kinds"], ["domain", "domain", "domain"])
            np.testing.assert_array_equal(header["sizes"], [3, 2, 5])
            np.testing.assert_allclose(header["space origin"], [0, 0, self.wavelengths[0]])
            step = (self.wavelengths[-1] - self.wavelengths[0]) / 4
            np.testing.assert_allclose(header["space directions"], np.diag([1, 1, step]))
            self.assertEqual(header["space units"], ["pixel", "scan_line", "nm"])
            np.testing.assert_array_equal(
                np.fromstring(header["wavelengths_nm"], sep=" "), self.wavelengths)


if __name__ == "__main__":
    unittest.main()
