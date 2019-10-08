import logging
import pathlib
from queue import Queue

from .handler import HttpRequestHandler
from .listener import HttpListener
from .logger import formatter


class HttpServer:
    """A simple HTTP server."""

    def __init__(self, port: int, address: str, webroot: pathlib.Path, verbose: bool):
        """Create a simple HTTP server to serve content from the given webroot.

        :param port: The port to listen to connections on.
        :param address: The address to bind to. To accept connections from the outside, set to 0.0.0.0
        :param webroot: The root directory to serve content from.
        :param verbose: Increase output verbosity.
        """
        self.port = port
        self.address = address
        self.webroot = webroot.resolve()

        if not self.webroot.exists():
            raise ValueError("The webroot must exist.")

        self.is_canceled = False

        self.requests = Queue()
        self.listener = HttpListener(self.port, self.address, self.requests, verbose)
        self.handler = HttpRequestHandler(self.requests, self.webroot, verbose)

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.setLevel("DEBUG" if verbose else "INFO")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def run(self):
        """Start the background daemons and wait while they run."""
        self.listener.start()
        self.handler.start()
        # Block the main thread while the others do their work.
        while True:
            pass

    def stop(self):
        """Stop the background daemons."""
        self.logger.debug("Stopping server...")
        self.listener.stop()
        self.handler.stop()
