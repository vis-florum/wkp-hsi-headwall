"""Display an EVK HELIOS EIFF scan. Run: uv run hsi-helios-eiff [file]."""

import argparse
from pathlib import Path

import numpy as np

from .reader import read_eiff, read_wavelengths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path,
                        default=Path("data/helios_eiff/ABS_PC_ABSPC_Referenzen_1.eiff"))
    parser.add_argument("--save", type=Path, help="Save a PNG instead of opening a window")
    args = parser.parse_args()

    # Agg can render a PNG without a desktop/display server.
    import matplotlib
    if args.save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, Slider

    cube = read_eiff(args.file)
    lines, pixels, bands = cube.shape
    wavelengths_nm = read_wavelengths(args.file)
    assert len(wavelengths_nm) == bands
    # A wavelength in nm becomes cm by multiplying by 1e-7.
    # Spectroscopic wavenumber is its reciprocal, in cm^-1 (not angular k).
    wavenumbers = 1e7 / wavelengths_nm
    print(f"Loaded {lines} lines × {pixels} pixels × {bands} bands, {cube.dtype}")
    print(f"Stored sample range: {cube.min()} to {cube.max()}")
    print(f"Estimated wavelength range: {wavelengths_nm[0]:.3f}–"
          f"{wavelengths_nm[-1]:.3f} nm (embedded table / 40; scale inferred)")

    fig, (image_ax, spectrum_ax) = plt.subplots(1, 2, figsize=(11, 7))
    fig.subplots_adjust(bottom=0.23, wspace=0.35)
    band = bands // 2
    # Stretch the displayed contrast only; the cube retains its original values.
    low, high = np.percentile(cube[:, :, band], (2, 98))
    image = image_ax.imshow(cube[:, :, band], cmap="viridis", vmin=low, vmax=high,
                            aspect="auto", interpolation="nearest")
    image_ax.set(xlabel="Spatial pixel", ylabel="Scan line",
                 title=f"Band {band} (~{wavelengths_nm[band]:.1f} nm)")
    fig.colorbar(image, ax=image_ax, label="Stored intensity")

    y, x = lines // 2, pixels // 2
    spectrum, = spectrum_ax.plot(wavenumbers, cube[y, x, :])
    # Place a red circle on the spectrum at the band displayed in the image.
    band_marker, = spectrum_ax.plot([wavenumbers[band]], [cube[y, x, band]], "ro",
                                    markersize=8, zorder=3)
    # A full-height guide makes the selected slice easy to locate on the axis.
    band_line = spectrum_ax.axvline(wavenumbers[band], color="red",
                                   linestyle=":", linewidth=0.8, zorder=1)
    marker, = image_ax.plot(x, y, "r+", markersize=10)
    spectrum_ax.set(xlabel="Estimated wavenumber (cm⁻¹)", ylabel="Stored intensity",
                    title=f"Pixel (line {y}, x {x})")
    # Keep scan-band order: low band indices have high wavenumbers.
    spectrum_ax.invert_xaxis()
    # The slider still selects discrete band indices; only the plotted x axis
    # uses physical coordinates. Intensity remains in stored counts.
    slider = Slider(fig.add_axes([0.16, 0.07, 0.68, 0.03]), "Band", 0, bands - 1,
                    valinit=band, valstep=1)
    colormaps = ["viridis", "inferno", "gray", "plasma", "magma", "cividis"]
    colormap_button = Button(fig.add_axes([0.36, 0.12, 0.28, 0.045]),
                             "Colormap: viridis")

    def change_colormap(event):
        # Cycle through the list. Updating the image also updates its colorbar.
        index = colormaps.index(image.get_cmap().name)
        name = colormaps[(index + 1) % len(colormaps)]
        image.set_cmap(name)
        colormap_button.label.set_text(f"Colormap: {name}")
        fig.canvas.draw_idle()

    def change_band(value):
        band = int(value)
        plane = cube[:, :, band]
        image.set_data(plane)
        image.set_clim(*np.percentile(plane, (2, 98)))
        image_ax.set_title(f"Band {band} (~{wavelengths_nm[band]:.1f} nm)")
        band_marker.set_data([wavenumbers[band]], [spectrum.get_ydata()[band]])
        band_line.set_xdata([wavenumbers[band], wavenumbers[band]])
        fig.canvas.draw_idle()

    def show_pixel(event):
        if event.inaxes == image_ax and event.button == 1:
            x, y = int(round(event.xdata)), int(round(event.ydata))
            if 0 <= x < pixels and 0 <= y < lines:
                spectrum.set_ydata(cube[y, x, :])
                band = int(slider.val)
                band_marker.set_data([wavenumbers[band]], [cube[y, x, band]])
                spectrum_ax.relim()
                spectrum_ax.autoscale_view()
                spectrum_ax.set_title(f"Pixel (line {y}, x {x})")
                marker.set_data([x], [y])
                fig.canvas.draw_idle()

    slider.on_changed(change_band)
    colormap_button.on_clicked(change_colormap)
    fig.canvas.mpl_connect("button_press_event", show_pixel)
    fig.suptitle("EVK HELIOS — move the band slider; click an image pixel")
    if args.save:
        fig.savefig(args.save, dpi=150)
        print(f"Saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
