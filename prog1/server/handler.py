import logging
import threading
from queue import Queue

from .logger import formatter


class HttpRequestHandler(threading.Thread):
    """Handle HTTP requests."""

    def __init__(self, queue: Queue, verbose: bool):
        """Create an HTTP request handler.

        :param queue: A queue of HTTP requests to handle.
        :param verbose: Increase output verbosity.
        """
        super().__init__(name="HttpRequestHandler", daemon=True)
        self.requests = queue
        self.is_canceled = False

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.setLevel("DEBUG" if verbose else "INFO")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        # TODO: Add a FileHandler?
        self.logger.addHandler(console_handler)

        self.logger.debug("Starting HTTP request handler...")

    def run(self):
        """Run the HTTP request handler in the background."""
        while not self.is_canceled:
            connection, address, request = self.requests.get(block=True, timeout=None)

            self.logger.info("(%s) - %s", address[0], request)

            connection.close()

    def stop(self):
        """Stop the HTTP request handler."""
        self.logger.debug("Stopping HTTP request handler...")
        self.is_canceled = True
