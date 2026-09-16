#!/usr/bin/env python3
"""Static server for yolo-pose-web with wasm / mjs MIME (Python 3.6+)."""

import argparse
import mimetypes
import socketserver
from http.server import HTTPServer, SimpleHTTPRequestHandler


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()

    mimetypes.add_type("application/javascript", ".mjs")
    mimetypes.add_type("application/wasm", ".wasm")

    httpd = ThreadingHTTPServer((args.bind, args.port), SimpleHTTPRequestHandler)
    print("yolo-pose-web http://%s:%s/" % (args.bind, args.port))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
