"""PyPhenom's submodules (Application, Spectroscopy, Processing, Stitch, Features, ...) -> pyphenom_modules.txt.
Offline: does not connect.
    py -3.12 dump_modules.py
"""
import inspect

import PyPhenom as ppi


def desc(o):
    if inspect.isclass(o) or callable(o) or isinstance(o, property):
        return (inspect.getdoc(o) or "").strip()
    return repr(o)[:120]


with open("pyphenom_modules.txt", "w", encoding="utf-8") as f:
    for mn, m in sorted(vars(ppi).items()):
        if not inspect.ismodule(m):
            continue
        f.write(f"\n##### {mn}\n")
        for name, obj in sorted(vars(m).items()):
            if name.startswith("_"):
                continue
            f.write(f"\n== {mn}.{name} ({type(obj).__name__})\n{desc(obj)}\n")
            if inspect.isclass(obj):
                for a, ao in sorted(vars(obj).items()):
                    if not a.startswith("__") and a not in ("names", "values"):
                        f.write(f"  .{a}: {desc(ao)}\n")
