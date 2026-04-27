import argparse
import sys

from .tui import run
from .worktree import latest_session_id, list_session_ids, new_thread_id


def main() -> None:
    parser = argparse.ArgumentParser(prog="clawd")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument(
        "-c",
        "--continue",
        dest="continue_",
        action="store_true",
        help="resume the most recent session",
    )
    grp.add_argument(
        "-r",
        "--resume",
        metavar="ID",
        help="resume the named session",
    )
    grp.add_argument(
        "-l",
        "--list",
        dest="list_",
        action="store_true",
        help="list existing sessions and exit",
    )
    args = parser.parse_args()

    if args.list_:
        ids = list_session_ids()
        if not ids:
            print("no sessions yet")
            return
        for sid in ids:
            print(sid)
        return

    if args.continue_:
        thread_id = latest_session_id()
        if thread_id is None:
            print("no sessions to resume", file=sys.stderr)
            sys.exit(1)
    elif args.resume:
        thread_id = args.resume
    else:
        thread_id = new_thread_id()

    run(thread_id)
