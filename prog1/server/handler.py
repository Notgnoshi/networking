import logging
from multiprocessing.pool import ThreadPool
from pathlib import Path
from queue import Queue

from .logger import formatter
from .request import HttpRequest


class HttpRequestHandler:
    """Handle HTTP requests."""

    def __init__(self, queue: Queue, webroot: Path, verbose: bool):
        """Create an HTTP request handler.

        :param queue: A queue of HTTP requests to handle.
        :param verbose: Increase output verbosity.
        """
        self.requests = queue
        self.webroot = webroot
        self.is_canceled = False

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.setLevel("DEBUG" if verbose else "INFO")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self.pool: ThreadPool = None

    def start(self):
        """Start the request handler thread pool."""
        self.logger.debug("Starting HTTP request handler...")
        # TODO: Start off with one worker thread. Expand when good and ready.
        self.pool = ThreadPool(1, self.worker)

    def worker(self):
        """Worker to asynchronously consume the requests queue."""
        while not self.is_canceled:
            connection, address = self.requests.get(block=True, timeout=None)
            data = connection.recv(1024)
            request = HttpRequest(data, verbose=True)
            request.handle(self.webroot, connection, address)
            # Closing the connection early results in a large number of retransmissions?
            # TODO: Close the connection once the response has been sent.
            # connection.close()

    def stop(self):
        """Stop the HTTP request handler."""
        self.logger.debug("Stopping HTTP request handler...")
        self.is_canceled = True
