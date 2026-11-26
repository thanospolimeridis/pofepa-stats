#!/usr/bin/env python3
"""Build portable HTML and a GitHub Pages-ready static directory, offline."""
import hashlib
import json
from pathlib import Path
import shutil

from validate import validate

ROOT = Path(__file__).resolve().parents[1]


def build():
    raw = (ROOT / "data/catalog.json").read_bytes()
    data = json.loads(raw)
    validate(data)
    data["version"] = (ROOT / "VERSION").read_text().strip()
    data["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    data["ranking_index"] = "https://www.pofepa.gr/piiotanualphakappaepsilonsigmaf-alphaxiiotaomicronlambdaomicrongammaetasigmaetasigmaf.html"
    html = (ROOT / "src/template.html").read_text()
    for marker, filename in [("STYLE", "style.css"), ("CORE", "core.js"), ("APP", "app.js")]:
        html = html.replace(f"/*{marker}*/", (ROOT / "src" / filename).read_text())
    # A literal </script> or HTML delimiter in source text cannot break out.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = html.replace("/*DATA*/", payload)
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text(html, encoding="utf-8")
    (dist / "offline.html").write_text(html, encoding="utf-8")
    (dist / ".nojekyll").touch()
    (dist / "coverage.json").write_text(json.dumps(data["coverage"], ensure_ascii=False, indent=2), encoding="utf-8")
    (dist / "provenance.json").write_text(json.dumps({"dataset_sha256": data["dataset_sha256"], "sources": data["sources"], "issues": data["issues"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {dist / 'index.html'} ({len(html.encode()):,} bytes); {len(data['matches']):,} singles matches.")


if __name__ == "__main__":
    build()
