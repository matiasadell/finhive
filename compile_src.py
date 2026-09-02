import os
from pathlib import Path


s = []

kw = "--**//\\**--"

base = Path(__file__).parent / "src"

def make_file(p: Path):
    if p.is_dir():
        for pp in os.listdir(str(p)):
            make_file(p / pp)
    else:
        _ = open(p,"r",encoding="utf-8").read()
        _ = f"{kw}\n{_}\n{kw}\n"
        s.append(_)

make_file(base)

open("compiled.txt","w",encoding="utf-8").write("".join(s))

        
