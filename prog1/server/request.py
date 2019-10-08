import logging
import mimetypes
from email.utils import formatdate
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
        # The raw request-URI
        self.uri: bytes = None
        # The request-URI resolved into a path.
        self.path: Path = None
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

        self.method, self.uri, self.version = tokens

        for line in self.request.readlines():
            line = line.strip()
            # Find the first ": " substring in the line.
            idx = line.find(b": ")
            if idx != -1:
                header, value = line[:idx], line[idx + 2 :]
                self.headers[header] = value

    @staticmethod
    def response(status: HTTPStatus, headers: dict = None, body: ByteString = None) -> ByteString:
        """Generate the HTTP response with the given content."""
        response = f"HTTP/1.1 {status.value} {status.phrase}\r\n"

        headers = dict() if headers is None else headers
        if "Content-Length" not in headers:
            headers["Content-Length"] = "0" if body is None else str(len(body))

        if "Date" not in headers:
            headers["Date"] = formatdate(timeval=None, localtime=False, usegmt=True)

        if "Server" not in headers:
            headers["Server"] = "httpserver.py/0.1 (class project)"

        if "Connection" not in headers:
            headers["Connection"] = "Closed"

        if "Content-Encoding" not in headers:
            headers["Content-Encoding"] = "utf-8"

        # Default to HTML content if not set manually.
        if "Content-Type" not in headers:
            headers["Content-Type"] = "text/html"

        for header, value in headers.items():
            response += header + ": " + value + "\r\n"

        response += "\r\n"
        response = response.encode("utf-8")
        response += b"" if body is None else body

        return response

    def send(self, connection, address, response):
        """Send the given HTTP response message."""
        # Log only the response line.
        self.logger.info("Response (%s:%s) - %s", *address, response.split(b"\r\n")[0])
        connection.send(response)

    def handle(self, webroot: Path, connection: socket, address: Tuple[str, int]):
        # Parsing failed.
        if self.status is not None:
            response = self.response(self.status, headers=None, body=None)
            self.send(connection, address, response)

        if self.method not in {b"GET", b"POST"}:
            self.status = HTTPStatus.METHOD_NOT_ALLOWED
            response = self.response(self.status, headers=None, body=None)
            self.send(connection, address, response)
            return

        if self.version.lower() not in {b"http/1.0", b"http/1.1"}:
            self.status = HTTPStatus.HTTP_VERSION_NOT_SUPPORTED
            response = self.response(self.status, headers=None, body=None)
            self.send(connection, address, response)

        self.logger.info("Request (%s:%s) - %s", *address, self.requestline)

        # Handle POST and GET messages (required by the HTTP/1.1 standard)
        if self.method == b"GET":
            response = self.handle_GET(webroot)
            self.send(connection, address, response)
        elif self.method == b"POST":
            response = self.handle_POST()
            self.send(connection, address, response)

    def handle_GET(self, webroot: Path) -> ByteString:
        # Determine if the request-URI is absolute or relative.
        # NOTE: This is tricky, as it requires determining if the network host is present.
        # Here, we assume that every path is relative to the webroot.
        uri = self.uri.decode("utf-8", errors="ignore")
        # pathlib.Path.joinpath() shits its pants when the request URI begins with a `/`...
        if uri.startswith("/"):
            uri = uri[1:]

        self.path = webroot / uri
        _path = self.path.resolve()

        # If URI is a directory, look for index.html or generate one if autoindex is set.
        if _path.is_dir():
            self.logger.info("Requested directory. Redirecting to site index.")
            _path = webroot / "index.html"
        if not _path.exists():
            _path = webroot / "404.html"
            self.status = HTTPStatus.NOT_FOUND
        else:
            self.status = HTTPStatus.OK

        headers = dict()
        mime, encoding = mimetypes.guess_type(str(_path))
        if mime is not None:
            headers["Content-Type"] = mime
        if encoding is not None:
            headers["Content-Encoding"] = encoding

        with open(_path, "rb") as f:
            # Must open as binary because the HTTP server doesn't care about its content, only raw bytes.
            return self.response(self.status, headers=headers, body=f.read())

    def handle_POST(self) -> ByteString:
        self.logger.error("error: %s - %s - %s - POST messages unsupported.")

        return self.response(HTTPStatus.OK, headers=None, body=None)
