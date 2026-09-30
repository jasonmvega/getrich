"""Find the SQLite database students are already using.

Run starter scripts from the folder that contains the student's stock project.
If TRADING_DB is set, that path wins. Otherwise trading.db in the current
working directory is used. If there is exactly one other .db file in the
current directory, the student may choose it.
"""
import os
from pathlib import Path


def get_db_path():
    configured = os.getenv("TRADING_DB")
    if configured:
        return Path(configured).expanduser().resolve()

    cwd = Path.cwd()
    normal = cwd / "trading.db"
    if normal.exists():
        return normal

    candidates = [p for p in cwd.glob("*.db") if p.is_file()]
    if len(candidates) == 1:
        answer = input(f"Found {candidates[0].name}. Use it instead of trading.db? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            return candidates[0].resolve()

    return normal.resolve()
