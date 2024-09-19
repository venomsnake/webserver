import io
import socket
import typing

from .headers import Headers


class BodyReader(io.IOBase):
    def __init__(self, sock: socket.socket, *, buff: bytes = b"", bufsize: int = 16_384) -> None:
        self._sock = sock
        self._buff = buff
        self._bufsize = bufsize

    def readable(self) -> bool:  # pragma: no cover
        return True

    def read(self, n: int) -> bytes:
        """Read up to n bytes from the request body."""
        while len(self._buff) < n:
            try:
                data = self._sock.recv(self._bufsize)
                if not data:
                    break
                self._buff += data
            except socket.error as e:
                raise IOError(f"Socket error: {e}")

        res, self._buff = self._buff[:n], self._buff[n:]
        return res


class Request(typing.NamedTuple):
    method: str
    path: str
    headers: Headers
    body: BodyReader

    @classmethod
    def from_socket(cls, sock: socket.socket) -> "Request":
        """Read and parse the request from a socket object.

        Raises:
          ValueError: When the request cannot be parsed.
        """
        lines = iter_lines(sock)

        try:
            request_line = next(lines).decode("ascii")
        except StopIteration:
            raise ValueError("Request line missing.")
        except UnicodeDecodeError:
            raise ValueError("Request line contains non-ASCII characters.")

        try:
            method, path, _ = request_line.split(" ")
        except ValueError:
            raise ValueError(f"Malformed request line {request_line!r}.")

        headers = Headers()
        buff = b""
        while True:
            try:
                line = next(lines)
            except StopIteration as e:
                buff = e.value
                break

            try:
                name, value = line.decode("ascii").split(":", 1)
                headers.add(name.strip(), value.lstrip())
            except ValueError:
                raise ValueError(f"Malformed header line {line!r}.")

        body = BodyReader(sock, buff=buff)
        return cls(method=method.upper(), path=path, headers=headers, body=body)


def iter_lines(sock: socket.socket, bufsize: int = 16_384) -> typing.Generator[bytes, None, bytes]:
    """Given a socket, read CRLF-separated lines and yield each one.

    Stops when an empty line is found. Returns the remainder of the buffer after the empty line.
    """
    buff = b""
    while True:
        try:
            data = sock.recv(bufsize)
            if not data:
                return b""
            buff += data
        except socket.error as e:
            raise IOError(f"Socket error: {e}")

        while True:
            try:
                i = buff.index(b"\r\n")
                line, buff = buff[:i], buff[i + 2:]
                if not line:
                    return buff  # End of headers
                yield line
            except (IndexError, ValueError):
                break
