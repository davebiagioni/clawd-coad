import argparse
import sys

from .tui import run
from .worktree import latest_session_id, list_session_ids, new_thread_id


def _resolve_thread_id(args: argparse.Namespace) -> str:
    if getattr(args, "continue_", False):
        thread_id = latest_session_id()
        if thread_id is None:
            print("no sessions to resume", file=sys.stderr)
            sys.exit(1)
        return thread_id
    if getattr(args, "resume", None):
        return args.resume
    return new_thread_id()


def _add_session_flags(parser: argparse.ArgumentParser) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="clawd")
    sub = parser.add_subparsers(dest="cmd")

    _add_session_flags(parser)
    parser.add_argument(
        "-l",
        "--list",
        dest="list_",
        action="store_true",
        help="list existing sessions and exit",
    )

    serve_p = sub.add_parser("serve", help="run the optional web frontend")
    _add_session_flags(serve_p)
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()

    if args.list_:
        ids = list_session_ids()
        if not ids:
            print("no sessions yet")
            return
        for sid in ids:
            print(sid)
        return

    thread_id = _resolve_thread_id(args)

    if args.cmd == "serve":
        try:
            from .web.server import serve
        except ImportError:
            print(
                "the web frontend needs the [web] extra: uv pip install -e '.[web]'",
                file=sys.stderr,
            )
            sys.exit(1)
        serve(thread_id, host=args.host, port=args.port)
        return

    run(thread_id)
