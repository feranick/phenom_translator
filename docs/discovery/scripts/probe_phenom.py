"""The XL's state, read only (Get* calls only: nothing moves or changes) -> stdout and phenom_version.xml.
    py -3.12 probe_phenom.py > phenom_probe.txt
Remove the license username from the output before committing it.
"""
import PyPhenom as ppi

p = ppi.Phenom()


def show(label, fn):
    try:
        print(f"{label}: {fn()}")
    except Exception as e:
        print(f"{label}: ERROR {e!r}")


rng = lambda r: (r.begin, r.end)  # noqa: E731
show("licenses", lambda: [(l.instrumentId, l.username) for l in ppi.GetLicenses()])
show("activated features", p.GetActivatedFeatures)
show("instrument mode", p.GetInstrumentMode)
show("operational mode", p.GetOperationalMode)
show("SEM mode", p.GetSemDeviceMode)
show("door", p.GetDoorStatus)
show("holder", lambda: (lambda h: (h.holderID, h.holderType, h.status))(p.GetSampleHolder()))
show("stage", lambda: (lambda s: (s.mode, s.position.x, s.position.y))(p.GetStageModeAndPosition()))
show("stroke SEM", lambda: (lambda s: (rng(s.SemX), rng(s.SemY)))(p.GetStageStroke()))
show("HFW range", lambda: rng(p.GetHFWRange()))
show("kV now / range", lambda: (p.GetSemHighTension(), rng(p.GetSemHighTensionRange())))
show("spot size range", lambda: rng(p.GetSemSpotSizeRange()))
show("WD range", lambda: rng(p.GetSemWDRange()))
show("has SED", p.SemHasSed)
show("charge reduction allowed", p.SemGetAllowedVacuumChargeReduction)
show("exclusive access", lambda: (lambda s: (s.isExclusive, s.message))(p.GetExclusiveAccessStatus()))
show("multi-axis stage", lambda: [(c.id, rng(c.range)) for c in p.MultiStageGetCapabilities()])
show("EDS status", lambda: (lambda s: (s.detectorTemperature, s.realTime))(p.Spectrometer.GetStatus()))
show("properties", p.GetPropertyNames)
vi = p.versionInfo
open("phenom_version.xml", "w", encoding="utf-8").write(str(vi() if callable(vi) else vi))
