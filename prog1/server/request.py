import logging
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from socket import socket
from typing import ByteString, Tuple

from .logger import formatter


class HttpRequest:
    """Parse and handle HTTP requests."""

    def __init__(self, request: ByteString, verbose=False):
        """Construct an HTTP request from the raw bytes.

        :param request: The bytestring of the request.
        :param verbose: Increase output verbosity, defaults to False
        """
        self.request = BytesIO(request)

        self.error_code = self.error_message = None
        self.client_address = None
        self.requestline = self.request.readline()
        self.method = None
        self.path = None
        self.version = None
        self.headers = dict()

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.setLevel("DEBUG" if verbose else "INFO")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self.parse_request()

    def parse_request(self):
        """Parse the HTTP/1.1 request.

        See https://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html for details on how to parse
        HTTP requests. This method only
        """
        # Parse the request line.
        tokens = self.requestline.strip().split()
        if len(tokens) != 3:
            self.logger.error("Failed to parse request: '%s'", self.requestline)
            self.status = HTTPStatus.BAD_REQUEST
            return
        method, uri, version = tokens

        # Only support GET, POST (both required), and HEAD methods.
        if method not in {b"GET", b"POST", b"HEAD"}:
            self.logger.error("Unsupported HTTP method: '%s'", method)
            self.status = HTTPStatus.METHOD_NOT_ALLOWED
            return
        self.method = method

        self.path = uri

        # This isn't a fully compliant HTTP server for either versions,
        # but accept HTTP 1.0 and 1.1 requests.
        if version.lower() not in {b"http/1.0", b"http/1.1"}:
            self.logger.error("Unsupported HTTP version: '%s'", version)
            self.status = HTTPStatus.HTTP_VERSION_NOT_SUPPORTED
            return
        self.version = version

        for line in self.request.readlines():
            line = line.strip()
            # Find the first ": " substring in the line.
            idx = line.find(b": ")
            if idx != -1:
                header, value = line[:idx], line[idx + 2 :]
                self.headers[header] = value

    def handle(self, webroot: Path, connection: socket, address: Tuple[str, int]):
        # TODO: Better logging?
        # TODO: Log both the request and the response.
        self.logger.info("(%s:%s) - %s %s %s", *address, self.method, str(self.path), self.version)
