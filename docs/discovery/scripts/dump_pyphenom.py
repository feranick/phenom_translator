"""Every class and function of PyPhenom with its docstring -> pyphenom_api.txt. Offline: does not connect.
    py -3.12 dump_pyphenom.py
"""
import inspect

import PyPhenom as ppi

with open("pyphenom_api.txt", "w", encoding="utf-8") as f:
    f.write(f"PyPhenom {ppi.__version__} {ppi.__file__}\n")
    for name, obj in sorted(vars(ppi).items()):
        if name.startswith("_"):
            continue
        f.write(f"\n== {name} ({type(obj).__name__})\n{(inspect.getdoc(obj) or '').strip()}\n")
        if inspect.isclass(obj):
            for m, mo in sorted(vars(obj).items()):
                if not m.startswith("__"):
                    f.write(f"  .{m}: {(inspect.getdoc(mo) or '').strip()}\n")
