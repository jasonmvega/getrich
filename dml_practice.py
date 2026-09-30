"""
Type ONE UPDATE or DELETE query at a time below, then run this file.

IMPORTANT: This file always connects to the DML PRACTICE COPY, never your
real database. Run make_dml_practice_copy.py first if you haven't yet --
this file will tell you to if the copy doesn't exist.
"""
import sqlite3
from db_location import get_db_path

# This deliberately does NOT use get_db_path() directly -- DML practice
# always targets the _DML_PRACTICE copy, on purpose, so you can't
# accidentally UPDATE or DELETE your real data.
source = get_db_path()
DB = source.with_name(source.stem + "_DML_PRACTICE" + source.suffix)

if not DB.exists():
    raise SystemExit(
        f"{DB.name} does not exist yet. Run make_dml_practice_copy.py first, "
        "then run this file again."
    )

# Replace ONLY the SQL below after you have written/predicted it on paper.
# Start with SELECT to see the row before you change it, then switch to
# UPDATE or DELETE.
query = """
SELECT * FROM trades WHERE trade_id = 3;
"""

with sqlite3.connect(DB) as con:
    if query.strip().upper().startswith("SELECT"):
        rows = con.execute(query).fetchall()
        print(f"Database: {DB}")
        for row in rows:
            print(row)
    else:
        cursor = con.execute(query)
        con.commit()
        print(f"Database: {DB}")
        print(f"Rows affected: {cursor.rowcount}")
        print("Run a SELECT on the same trade_id to confirm the change.")
