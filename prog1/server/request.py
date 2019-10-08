import logging
import mimetypes
import threading
import urllib
from email.utils import formatdate
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from socket import socket
from typing import ByteString, Tuple


class HttpRequest:
    """Parse and handle HTTP requests."""

    def __init__(self, request: ByteString, logger: logging.Logger):
        """Construct an HTTP request from the raw bytes.

        :param request: The bytestring of the request.
        :param logger: The logger to use for messages related to this request.
        """
        # NOTE: Avoid creating a new logger for each request with the same name, because that
        # results in logging the same message many times.
        self.logger: logging.Logger = logger
        self.logger.debug("Handling HttpRequest in thread %s", threading.get_ident())

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
        self.logger.info("Response to (%s:%s) - %s", *address, response.split(b"\r\n")[0])
        connection.send(response)

    def handle(self, webroot: Path, connection: socket, address: Tuple[str, int]):
        """Handle HTTP requests.

        :param webroot: The directory to serve content out of
        :param connection: The connection corresponding to this request.
        :param address: The client's address and port.
        """
        if self.status is not None:
            self.logger.error("Failed to parse requestline")
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
            return

        self.logger.info("Request from (%s:%s) - %s", *address, self.requestline)

        # Handle POST and GET messages (required by the HTTP/1.1 standard)
        if self.method == b"GET":
            response = self.handle_GET(webroot)
            self.send(connection, address, response)
        elif self.method == b"POST":
            response = self.handle_POST()
            self.send(connection, address, response)

    def handle_GET(self, webroot: Path) -> ByteString:
        """Handle GET requests.

        Attempt to serve content out of the given webroot. If a file cannot be found, serve the
        404.html page located in the default webroot. Currently, this 404.html page is hard coded,
        and cannot be modified.

        If a directory is requested, the server looks for an index.html file located in that
        directory. If one is not found, one is generated with a link to each item in the directory.

        :param webroot: The directory to serve content out of.
        :return: The HTTP response as raw bytes.
        """
        # Determine if the request-URI is absolute or relative.
        # NOTE: This is tricky, as it requires determining if the network host is present.
        # Here, we assume that every path is relative to the webroot.
        uri = self.uri.decode("utf-8", errors="ignore")
        uri = urllib.parse.unquote(uri)
        # pathlib.Path.joinpath() shits its pants when the request URI begins with a `/`...
        self.path = webroot / Path(uri).relative_to("/")
        _path = self.path.resolve()

        # If URI is a directory, look for index.html or generate one if autoindex is set.
        if _path.is_dir():
            _path = _path / "index.html"
            # If the index doesn't exist, attempt to generate one.
            if not _path.exists():
                self.logger.debug("Generating index for %s", _path.parent)
                body = self.generate_index(webroot, _path.parent)
                self.status = HTTPStatus.OK
                return self.response(self.status, body=body)
        if not _path.exists():
            # The webroot is configurable, and I don't feel like trying to setup a default 404.html
            # file, unless the user has their own.
            _path = Path(__file__).parent.parent / "www" / "404.html"
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
        """Handle POST requests.

        Since it's well outside the scope of the assignment, and I'm rapidly running
        out of time, ignore POST requests, even though the HTTP/1.1 standard requires
        they be supported.
        """
        self.logger.error("error: %s - %s - %s - POST requests unsupported.")

        return self.response(HTTPStatus.OK, headers=None, body=None)

    @staticmethod
    def generate_index(webroot, directory: Path):
        """Generate an index file for the given directory."""
        body = "<!DOCTYPE html><html><head><title>Index</title></head><body>\n"
        body += f"<p>Autogenerated index for <code>/{directory.relative_to(webroot)}</code></p>\n"
        body += "<ul>\n"

        # Don't traverse out of the webroot.
        if directory != webroot:
            # BUG: Getting the right paths is tricky. Sometimes they seem to be relative to the
            # current file, and sometimes they seem relative to the webroot.
            body += f'\t<li><a href="/{directory.relative_to(webroot).parent}">..</a></li>\n'

        for item in directory.iterdir():
            body += f'\t<li><a href="/{item.relative_to(webroot)}">{item.relative_to(directory)}</a></li>\n'

        body += "</ul>\n</body></html>"

        return body.encode("utf-8")
