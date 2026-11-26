#!/usr/bin/env python3
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def build_hashes():
    subprocess.run([sys.executable, str(ROOT/'scripts/build.py')], cwd=ROOT, check=True)
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'index.html', *sorted((ROOT/'dist').rglob('*'))] if p.is_file()}

if __name__=='__main__':
    if build_hashes()!=build_hashes():
        raise SystemExit('Build is not reproducible')
    print('Build outputs are byte-identical.')
