import logging
import threading
from multiprocessing.pool import ThreadPool
from pathlib import Path
from queue import Queue

from .logger import formatter
from .request import HttpRequest


class HttpRequestHandler:
    """Handle HTTP requests."""

    def __init__(self, queue: Queue, webroot: Path, threads: int, verbose: bool):
        """Create an HTTP request handler.

        :param queue: A queue of HTTP requests to handle.
        :param webroot: The directory to serve content from.
        :param threads: The number of threads to use to handle requests.
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

        self.threads = threads
        self.pool: ThreadPool = None

    def start(self):
        """Start the request handler thread pool."""
        self.logger.debug("Starting HTTP request handler...")
        self.pool = ThreadPool(processes=self.threads, initializer=self.worker, initargs=(self,))

    @staticmethod
    def worker(handler: "HttpRequestHandler"):
        """Worker to asynchronously consume the requests queue."""
        handler.logger.debug(
            "Starting HTTP request handler worker in thread %s...", threading.get_ident()
        )
        while not handler.is_canceled:
            connection, address = handler.requests.get(block=True, timeout=None)
            data = connection.recv(2048)
            request = HttpRequest(data, handler.logger)
            request.handle(handler.webroot, connection, address)
            connection.close()

    def stop(self):
        """Stop the HTTP request handler."""
        self.logger.debug("Stopping HTTP request handler...")
        self.is_canceled = True
