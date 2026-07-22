"""Assemble the standalone dashboard: inject engine.js + database JSON."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
tpl = (ROOT/"dashboard/vet_dashboard_template.html").read_text()
engine = (ROOT/"dashboard/engine.js").read_text()
data = (ROOT/"data_build/vet_db.json").read_text()
out = tpl.replace("/*__ENGINE__*/", engine).replace("/*__VET_DATA__*/", data)
dest = ROOT/"dashboard/VET_Dashboard.html"
dest.write_text(out)
print(f"{dest} ({dest.stat().st_size//1024} KB)")
