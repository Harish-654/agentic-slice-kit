#!/usr/bin/env python3
"""
manage_accounts.py - the recovery path for student accounts. There is no email, so this is how a forgotten
password is dealt with, and how a student who used the tutor BEFORE accounts existed gets their history back.

    python scripts/manage_accounts.py list
    python scripts/manage_accounts.py reset Asha       give an existing account a new password (ends its sign-ins)
    python scripts/manage_accounts.py claim Mithran    attach a NEW account to a name that already has history

Why `claim` is not something a student can do themselves: a name with history is locked at sign-up, so nobody
can take over someone else's progress by getting there first. Running `claim` says "yes, this person really is
Mithran". Do it only once you have checked.

It works on the database the server uses: $SLICE_DB, or run.db in the current folder. The password is asked
for without echo, so it does not land in your shell history.
"""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from demo.tutor import accounts          # noqa: E402
from slice.store import Store            # noqa: E402


def ask() -> str:
    first = getpass.getpass("New password: ")
    if first != getpass.getpass("Again: "):
        sys.exit("The two passwords differ. Nothing was changed.")
    return first


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("list", "reset", "claim") or (argv[0] != "list" and len(argv) != 2):
        print(__doc__)
        return 2
    db = os.environ.get("SLICE_DB", "run.db")
    store = Store(db)
    accounts._ready(store)
    try:
        if argv[0] == "list":
            rows = store.db.execute("SELECT name, created_at FROM accounts ORDER BY created_at").fetchall()
            for r in rows:
                print(f"{r['name']:30s} created {__import__('datetime').datetime.fromtimestamp(r['created_at']):%Y-%m-%d %H:%M}")
            print(f"{len(rows)} account(s) in {db}")
        elif argv[0] == "reset":
            accounts.set_password(store, argv[1], ask())
            print(f"Password reset for {argv[1]}. Their sign-ins have been ended.")
        else:
            name = accounts.create(store, argv[1], ask(), claim_history=True)
            print(f"Account {name!r} now owns that name and its earlier history.")
    except accounts.AccountError as e:
        print(f"Not done: {e}")
        return 1
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
