"""Make a safe copy before UPDATE/DELETE practice."""
from pathlib import Path
import shutil
from db_location import get_db_path

source = get_db_path()
destination = source.with_name(source.stem + "_DML_PRACTICE" + source.suffix)
if not source.exists():
    raise SystemExit(f"Database not found: {source}")
shutil.copy2(source, destination)
print(f"Practice copy created: {destination}")
print("Use THIS copy for UPDATE/DELETE practice.")
