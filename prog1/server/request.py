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

        self.status = None
        self.parse_request()

    def parse_request(self):
        """Parse the HTTP/1.1 request.

        See https://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html for details on how to parse
        HTTP requests. This method only
        """
        # Parse the request line.
        tokens = self.requestline.strip().split()
        if len(tokens) != 3:
            self.logger.error("Failed to parse request line: '%s'", self.requestline)
            self.status = HTTPStatus.BAD_REQUEST
            return

        self.method, self.path, self.version = tokens

        for line in self.request.readlines():
            line = line.strip()
            # Find the first ": " substring in the line.
            idx = line.find(b": ")
            if idx != -1:
                header, value = line[:idx], line[idx + 2 :]
                self.headers[header] = value

    def handle(self, webroot: Path, connection: socket, address: Tuple[str, int]):
        # Parsing failed.
        if self.status is not None:
            response = self.response(self.status, headers=None, body=None)
            self.send(connection, response)

        # Parse the request line.
        # Determine if the request-URI is absolute or relative.
        # If the URI is relative, and the Host header is missing, send HTTPStatus.BAD_REQUEST
        # Determine if the URI exists
        # If URI is a directory, look for index.html or generate one if autoindex is set.
        # If URI is a file, send the file's raw bytes as a response

        self.logger.debug("(%s:%s) - %s - %s %s", *address, self.method, self.path, self.version)

    def handle_GET(self):
        pass

    def handle_POST(self):
        pass

    def response(
        self, status: HTTPStatus, headers: dict = None, body: ByteString = None
    ) -> ByteString:
        """Generate the HTTP response with the given content."""
        return b"HTTP/1.1 400 Bad request\r\n"

    def send(self, connection, response):
        """Send the given HTTP response message."""
        self.logger.debug("Sending: %s", response)
        connection.send(response)
