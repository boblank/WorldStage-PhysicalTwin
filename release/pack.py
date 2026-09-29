"""Build the reviewable standalone source + prebuilt WorldStage release ZIP."""
from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'demo-3d'
OUT = ROOT / 'release/worldstage-3h.zip'

files = [ROOT / 'README.md']
files += list((ROOT / 'docs').glob('*.md'))
files += [DEMO / name for name in ('README.md', 'index.html', 'lab.html', 'worldgen.html', 'vite.config.mjs', 'package.json', 'package-lock.json')]
for folder in ('src', 'studio', 'skills', 'dist', 'examples', 'public'):
    files += list((DEMO / folder).rglob('*'))
files = sorted({path for path in files if path.is_file() and '__pycache__' not in path.parts and not path.name.endswith('.pyc') and not ('dist' in path.parts and 'worldgen' in path.parts)}, key=lambda path: str(path.relative_to(ROOT)))
assert (DEMO / 'dist/lab.html') in files and (DEMO / 'examples/skill-benchmark/browser_trajectory.json.gz') in files
with ZipFile(OUT, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        info = ZipInfo(str(path.relative_to(ROOT)), date_time=(2026, 9, 29, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
(OUT.parent / 'SHA256SUMS.txt').write_text(f'{digest}  {OUT.name}\n')
print(f'{OUT} ({OUT.stat().st_size} bytes, {len(files)} files)')
print(digest)
