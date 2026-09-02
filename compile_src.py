import os
from pathlib import Path


s = ""

kw = "--**//\\**--"

base = Path(__file__).parent / src

def make_file(p: Path):
    if p.isdir():
        for pp in os.listir(str(p)):
            make_file(p / pp)
    else:
        _ = open(p,"r").read()
        _ = f"{kw}\n{_}\n{kw}\n"
        s += _

make_file(base)

open("compiled.txt").write(s)

        
