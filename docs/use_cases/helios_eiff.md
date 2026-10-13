# EVK HELIOS camera: EIFF use case

## What is inside this file?

These details come from inspecting the actual file, rather than an official EIFF
specification. The file is 164,995,620 bytes. Embedded device strings identify
`EVK-Helios-EQ-32`, `EVK DI Kerschhaggl GmbH`.

| Item | Observed content |
| --- | --- |
| Scan lines | 2,376 |
| Spatial pixels per line | 312 |
| Spectral bands per pixel | 248 |
| Sample storage | Little-endian unsigned 16-bit integers |
| Sample range in the complete scan | 0–4095 |
| Decoded cube shape | `(2376, 312, 248)` |
| Decoded cube size | 367,690,752 bytes, approximately 351 MiB |
| Ordering inside one line | Pixel 0's 248 bands, then pixel 1's 248 bands, etc. |

This is a line-scan cube: successive scan lines build the image in the direction
of motion. Selecting one band gives a 2D image. Selecting one pixel gives a
248-value spectrum. The saved preview shows three sample pieces. Display aspect
is chosen to fit the window; physical pixel spacing is not established.

### Byte layout used by the reader

Each chunk has a **10-byte ASCII name**, an **8-byte big-endian payload length**,
then its payload. Chunks follow each other immediately, including odd lengths;
there is no alignment padding in this file.

`LIST`, `PROP`, and `FORM` are containers: their payload starts with a 10-byte
subtype, followed by nested chunks. The top container's subtype is `SPEHLIOS`.

| Leaf name | Interpretation |
| --- | --- |
| `EVKSTNRD` | 54-byte header containing image dimensions |
| `PROPINFO` | Property information; not needed for viewing |
| `EVKDVINF` | Compressed device information, including UTF-16-LE strings |
| `EVKWAVTB` | Compressed wavelength table; scale inferred as 1/40 nm per unit |
| `EVKROIBI` | Additional property, not interpreted |
| `EVKMODEL` | Additional property, not interpreted |
| `EVKMACOL` | Additional property, not interpreted |
| `BODY` | Compressed samples for one scan line; 2,376 such chunks |

Inside the `EVKSTNRD` payload, zero-based byte slices `[6:10]`, `[10:14]`, and
`[26:30]` give bands, spatial pixels, and scan lines as big-endian integers.

Compressed leaves have a 9-byte wrapper followed by a standard **zlib** stream.
Wrapper bytes `[4:8]` give the decompressed length as a little-endian integer.
The other wrapper fields are not needed here. Every `BODY` expands to 154,752
bytes, exactly `312 × 248 × 2`. The reader checks the declared decompressed
length for each line and checks that the decoded line count matches the header.

The wavelength property expands to 9,224 bytes. At offset 8, it contains 248
increasing little-endian 32-bit integers, from 37,163 to 68,087, followed by
additional data. Its header bytes `[6:8]` contain the band count as a
little-endian integer. Dividing the table values by 40 gives **929.075–1702.175
nm**, with approximately **3.125 nm** spacing. This matches the 929–1702 nm
range in the manufacturer's [HELIOS EC32 data sheet](https://www.clearview-imaging.com/hubfs/EVK-Datasheets/EVK_HELIOS-EC32_Data-sheet_EN_V03-22.pdf),
supporting the interpretation as wavelengths with a scale of 0.025 nm per unit.
The camera in this file is an EQ32; the EC32 sheet supplies supporting range
evidence, not an EIFF encoding specification. The scale remains **inferred**,
and the axis is labelled **Estimated wavenumber** accordingly.

The viewer reads the actual per-band table rather than interpolating the
advertised endpoints. It converts wavelength to spectroscopic wavenumber:

```python
wavelength_nm = stored_table_value / 40.0  # Inferred EIFF unit scale.
wavenumber_cm_inverse = 1e7 / wavelength_nm
frequency_THz = 299792.458 / wavelength_nm # Optional alternative coordinate.
```

Wavenumber decreases from approximately 10,763.4 to 5,874.8 cm⁻¹ as band index
increases. The plot runs from high to low wavenumber to retain band order.
For example, band 124 is approximately 1317.2 nm, or 7591.9 cm⁻¹. The file does
not need to store separate frequency or wavenumber tables: these coordinates
follow from wavelength. Confirming the EIFF scale with EVK/Headwall or a
SQALAR export is still needed before treating the coordinates as verified
calibration values.

Stored intensity calibration is also unverified. Values are displayed as stored
counts, not reflectance percentages. The image uses a 2nd–98th percentile
contrast stretch for the selected band; the original cube and plotted spectrum
retain their stored values.

## Access the array yourself

The reading function is independent of the plotting code:

```python
from pathlib import Path
from wkp_hsi.helios_eiff import read_eiff

cube = read_eiff(Path("data/helios_eiff/ABS_PC_ABSPC_Referenzen_1.eiff"))
image = cube[:, :, 124]       # One band: scan lines × spatial pixels.
spectrum = cube[1188, 156, :] # One pixel: all 248 bands.

# Optional: save the decoded cube in NumPy's documented format.
import numpy as np
np.save("outputs/scan.npy", cube)
```

## Other routes and documentation

I did not find a public EIFF specification or a documented public EIFF reader
in the searches performed. This implementation is based on the supplied scan;
other EIFF variants may use different layouts or compression.

- **EVK SQALAR** is the manufacturer's software for recording data and working
  with HELIOS cameras. The manufacturer's [HELIOS EQ32 product page](https://2023.evk.biz/en/products-services/hyperspectral-camera/evk-helios-eq-32/)
  describes that integration and specifies 248 bands over 930–1700 nm. SQALAR
  is a useful route for comparing this rendering against the original software
  and asking EVK/Headwall to confirm the wavelength scale and intensity units.
- **Vendor export** is another route to standard data. A vendor
  [EVK catalogue](https://www.ads-img.co.jp/wp-content/uploads/evk_catalog.pdf)
  lists MATLAB `.mat` export for SQALAR. Availability and the exact exported
  content should be checked in the installed version; export was not tested here.
- **Live camera acquisition** is a separate task. The manufacturer's EQ32 page
  lists GigE Vision/GenICam. Those interfaces are not required to read this saved file.

Validation: decoded all 2,376 image blocks successfully, checked their expanded
sizes, checked the header line count, measured the complete stored value range,
and rendered and visually inspected `preview.png`. Programmatically exercised
the slider at bands 0 and 247 and an image-click event, confirming that the
spectrum updates to the selected pixel. Desktop interaction was not manually
exercised in this environment.
