#!/usr/bin/env python3
"""A simple HTTP server demonstrating basic understanding of sockets and HTTP."""

import argparse
from pathlib import Path

from server import HttpServer


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--port", "-p", type=int, default=8080, help="The port to listen on.")
    parser.add_argument(
        "--host", "-l", type=str, default="localhost", help="The address to bind to."
    )
    parser.add_argument(
        "--webroot",
        type=Path,
        default=Path(__file__).resolve().parent / "www",
        help="The server root directory to serve content from.",
    )
    parser.add_argument(
        "--threads", "-t", type=int, default=2, help="Number of HTTP request handler threads."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False, help="Increase output verbosity."
    )

    return parser.parse_args()


def main(args):
    server = HttpServer(
        port=args.port,
        address=args.host,
        webroot=args.webroot,
        threads=args.threads,
        verbose=args.verbose,
    )

    try:
        server.run()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main(parse_args())
