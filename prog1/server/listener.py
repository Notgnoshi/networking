import logging
import socket
import threading
from queue import Queue

from .logger import formatter


class HttpListener(threading.Thread):
    """A simple class to listen for HTTP requests."""

    # TODO: Add better typing.
    def __init__(self, port: int, address: str, queue: Queue, verbose):
        """Create an HTTP listener.

        :param port: The port to listen on.
        :param address: The address to bind to.
        :param verbose: Whether to increase output verbosity.
        """
        super().__init__(name="HttpListener", daemon=True)

        self.port = port
        self.address = address
        self.requests: Queue = queue
        self.is_canceled = False

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.setLevel("DEBUG" if verbose else "INFO")
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.address, self.port))
        # TODO: Commandline argument
        self.socket.listen(100)

        self.logger.debug("Starting HTTP listener at %s:%d...", self.address, self.port)

    def run(self):
        """Run the HTTP listener in the background."""
        while not self.is_canceled:
            connection, address = self.socket.accept()
            # Recv the data from the socket in another thread to avoid blocking this one as much as possible.
            self.requests.put_nowait((connection, address))

    def stop(self):
        """Stop the HTTP listener."""
        self.logger.debug("Stopping HTTP listener...")
        self.is_canceled = True
        self.socket.close()
