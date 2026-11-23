"""A stand-in for PyPhenom 2.1.0's tier-0 API (names and shapes from docs/discovery/pyphenom_api.txt; values from the
XL's probe of 2026-11-23), so tests run phenom_translator.adapter.PhenomAdapter's own code without the instrument.
Enums print as PyPhenom does ('PyPhenom.InstrumentMode.Operational'); high tension is negative; the Property
getters refuse the wrong type, as PyPhenom does. CALLS records every method called, for the tier tests."""

__version__ = "2.1.0-stub"
CALLS = []
CONNECT_ARGS = []


class _E:
    def __init__(self, enum, name):
        self.enum, self.name = enum, name

    def __str__(self):
        return f"PyPhenom.{self.enum}.{self.name}"

    __repr__ = __str__


class _O:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _r(a, b):
    return _O(begin=a, end=b)


class Features:
    Spectroscopy, Stitching, ParticleMetric, RoughnessReconstruction = 1, 2, 4, 8
    AsbestosDetection, LiveVideo, FastSpectrum, EdsMap, ResolutionMeasurement = 16, 32, 64, 128, 512


class SampleHolderType:
    @staticmethod
    def Name(t):
        return {100: "XL Manual Height", 1: "Standard"}.get(int(t), "Unknown")


def HasLicense(features):
    CALLS.append("HasLicense")
    return False


PROPS = {"HighTension.Analysis": -15000.0, "EDX.WdOptimalLowerBound": 0.0045, "EDX.Detector.Window": "C2",
         "Features.CustomSpotSizeAllowed": True, "SpotSize.Map": 5.1, "MultiStage.Count": 0}


class _Spectrometer:
    def GetStatus(self):
        CALLS.append("Spectrometer.GetStatus")
        return _O(accumulationTime=0.0, detectorTemperature=234.70000000000002, fastCount=0, realTime=0.0,
                  slowCount=0)


class Phenom:
    STATE = {"instrument": "Operational", "operational": "LiveSem"}

    def __init__(self, *args):
        CONNECT_ARGS.append(args)
        self.Spectrometer = _Spectrometer()

    def __getattribute__(self, name):
        if name[0].isupper() and name != "Spectrometer" and name != "STATE":
            CALLS.append(name)
        return object.__getattribute__(self, name)

    def GetInstrumentMode(self):
        return _E("InstrumentMode", self.STATE["instrument"])

    def GetOperationalMode(self):
        return _E("OperationalMode", self.STATE["operational"])

    def GetSemDeviceMode(self):
        return _E("SemMode", "Imaging")

    def GetDoorStatus(self):
        return _E("DoorStatus", "Closed")

    def GetSampleHolder(self):
        return _O(holderID="0183a2111d0000d3", holderType=100, status=_E("SampleHolderStatus", "Present"))

    def GetStageModeAndPosition(self):
        return _O(mode=_E("StageNavigationMode", "Rest"), position=_O(x=6.02434271662765e-05, y=0.003988864624543326),
                  target=_O(x=0.0, y=0.0))

    def GetStageStroke(self):
        return _O(SemX=_r(-0.05, 0.05), SemY=_r(-0.05, 0.05), NavCamX=_r(-0.05, 0.05), NavCamY=_r(-0.05, 0.05))

    def GetHFW(self):
        return 0.000877216182013485

    def GetHFWRange(self):
        return _r(2.4714285714285713e-06, 0.000877216182013485)

    def GetSemHighTension(self):
        return -15000.0

    def GetSemHighTensionRange(self):
        return _r(-20500.0, -4800.0)

    def GetSemSpotSize(self):
        return 5.1

    def GetSemSpotSizeRange(self):
        return _r(0.0, 5.8)

    def SemGetEmissionCurrent(self):
        return 4.0300000000000004e-05

    def GetSemWD(self):
        return 0.0063

    def GetSemWDRange(self):
        return _r(0.001, 0.06)

    def SemHasSed(self):
        return True

    def SemGetSedState(self):
        return _E("SedState", "Enabled")

    def SemGetVacuumChargeReductionState(self):
        return _O(isStable=True, pressureEstimate=0.1, progress=None, target=_E("VacuumChargeReduction", "Off"))

    def SemGetAllowedVacuumChargeReduction(self):
        return [_E("VacuumChargeReduction", n) for n in ("Off", "Low", "High")]

    def GetExclusiveAccessStatus(self):
        return _O(isExclusive=False, message="")

    def GetSemViewingMode(self):
        sp = _O(center=_O(x=0.0, y=0.0), detector=_E("DetectorMode", "All"), hdr=False, nFrames=4, scale=1.0,
                size=_O(width=960, height=540))
        return _O(scanMode=_E("ScanMode", "Imaging"), scanParams=sp)

    def SemGetBlankBeamState(self):
        return _E("SemBlankState", "Unblanked")

    def IsAcquiringSpectrum(self):
        return False

    def GetInstrumentHealth(self):
        return _O(DoorOpen=False, ElectronicsOK=True, ImageEngineOK=True, NavCamOK=True, OpticsOK=True, SampleOK=True,
                  SourceOK=True, StageOK=True, SystemOK=True, VacuumOK=True, ElectronicsAR=False)

    def GetActivatedFeatures(self):
        return ["XL 100 x 100 mm stage"]

    def GetPropertyNames(self):
        return list(PROPS)

    def _prop(self, name, kind):
        v = PROPS[name]
        if type(v) is not kind:
            raise RuntimeError(f"Property {name} is not of type {kind.__name__}")
        return v

    def GetPropertyDouble(self, name):
        return self._prop(name, float)

    def GetPropertyInt(self, name):
        return self._prop(name, int)

    def GetPropertyBool(self, name):
        return self._prop(name, bool)

    def GetPropertyString(self, name):
        return self._prop(name, str)
