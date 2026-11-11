"""Verify complete, current French catalogs; requires GNU gettext on PATH."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
source = root / "locales/fr/LC_MESSAGES/django.po"
for selection in ("--untranslated", "--only-fuzzy"):
    result = subprocess.run(["msgattrib", selection, "--no-obsolete", "--no-wrap", str(source)], check=True, capture_output=True, text=True)
    if re.search(r'^msgid "[^"\n]', result.stdout, re.MULTILINE):
        raise SystemExit(f"Incomplete French catalog ({selection}).")
compiled = subprocess.run(["msgfmt", "--check", "-o", "-", str(source)], check=True, capture_output=True).stdout
if compiled != source.with_suffix(".mo").read_bytes():
    raise SystemExit("Compiled French catalog is stale; run manage.py compilemessages -l fr.")
print("French catalog is complete and compiled output is current.")
