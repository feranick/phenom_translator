"""Which calls the PPI license allows, tried on the PyPhenom simulator (touches nothing on the microscope).
    py -3.12 license_sim.py
Also run once:
    py -3.12 -c "import PyPhenom as ppi; print({n: ppi.HasLicense(getattr(ppi.Features, n)) for n in dir(ppi.Features) if not n.startswith('_')})"
The simulator enforces the license more strictly than the XL (raw EDS works on the XL without Spectroscopy).
"""
import PyPhenom as ppi

p = ppi.Phenom('Simulator', '', '')


def t(label, fn):
    try:
        r = fn()
        print(f"{label}: OK {type(r).__name__}")
    except Exception as e:
        print(f"{label}: {e!r}")


t("SemAcquireImage", lambda: p.SemAcquireImage(256, 256))
t("SemAutoFocus", lambda: p.SemAutoFocus())
t("RoughFocus", lambda: ppi.Application.RoughFocus(p))
t("Spectrometer status", lambda: p.Spectrometer.GetStatus())
t("AcquireSpectrum 1 s", lambda: p.AcquireSpectrum(1.0))
t("Identify", lambda: ppi.Spectroscopy.Identify(p.AcquireSpectrum(1.0)))
t("TileStitcher", lambda: ppi.Application.TileStitcher(2, 2, 256, 0.1, ppi.PixelType.Unsigned8))
