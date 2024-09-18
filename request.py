import io
import socket
import typing
from collections import defaultdict
from headers import Headers

# BodyReader class definition
class BodyReader(io.IOBase):
    def __init__(self, sock: socket.socket, *, buff: bytes = b"", bufsize: int = 16_384) -> None:
        self._sock = sock
        self._buff = buff
        self._bufsize = bufsize

    def readable(self) -> bool:
        return True

    def read(self, n: int) -> bytes:
        """Read up to n number of bytes from the request body."""
        while len(self._buff) < n:
            data = self._sock.recv(self._bufsize)
            if not data:
                break
            self._buff += data

        res, self._buff = self._buff[:n], self._buff[n:]
        return res
    

# Request Class definition
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
            print(f"Request Line: {request_line}")
        except StopIteration:
            raise ValueError("Request line missing.")

        try:
            method, path, _ = request_line.split(" ")
        except ValueError:
            raise ValueError(f"Malformed request line {request_line!r}.")

        headers = Headers()
        buff = b""
        while True:
            try:
                line = next(lines)
                print(f"Header Line: {line.decode('ascii')}") 
            except StopIteration as e:
                # StopIteration.value contains the return value of the generator.
                buff = e.value
                break

            try:
                name, _, value = line.decode("ascii").partition(":")
                headers.add(name, value.lstrip())
            except ValueError:
                raise ValueError(f"Malformed header line {line!r}.")

        body = BodyReader(sock, buff=buff)
        return cls(method=method.upper(), path=path, headers=headers, body=body)


# Updated iter_lines to handle partial and complete lines
def iter_lines(sock: socket.socket, bufsize: int = 16_384) -> typing.Generator[bytes, None, bytes]:
    buff = b""
    while True:
        try:
            data = sock.recv(bufsize)
        except socket.timeout:
            print("Socket receive timeout, no data received within the specified time.")
            if buff:
                yield buff
            return
        except socket.error as e:
            print(f"Socket error: {e}")
            if buff:
                yield buff
            return

        if not data:
            if buff:
                if b"\r\n" in buff:
                    while b"\r\n" in buff:
                        i = buff.find(b"\r\n")
                        line, buff = buff[:i], buff[i + 2:]
                        if line:
                            yield line
                if buff:
                    yield buff
            return

        buff += data
        while b"\r\n" in buff:
            i = buff.find(b"\r\n")
            line, buff = buff[:i], buff[i + 2:]
            if line:
                yield line

