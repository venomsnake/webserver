"""
Refrence = https://defn.io/2018/02/25/web-app-from-scratch-01/
2018/03/04
2018/03/20

"""
import typing
import socket
import mimetypes
import os
from request import Request
from headers import Headers
import io

HOST = "localhost"
PORT = 9000

RESPONSE = b"""\
HTTP/1.1 200 OK
Content-type: text/html
Content-length: 15

<h1>Hello!</h1>""".replace(b"\n", b"\r\n")

BAD_REQUEST_RESPONSE = b"""\
HTTP/1.1 400 Bad Request
Content-type: text/plain
Content-length: 11

Bad Request""".replace(b"\n", b"\r\n")

NOT_FOUND_RESPONSE = b"""\
HTTP/1.1 404 Not Found
Content-type: text/plain
Content-length: 9

Not Found""".replace(b"\n", b"\r\n")

METHOD_NOT_ALLOWED_RESPONSE = b"""\
HTTP/1.1 405 Method Not Allowed
Content-type: text/plain
Content-length: 17

Method Not Allowed""".replace(b"\n", b"\r\n")

# Server root constant and serve file function to represent file pos

SERVER_ROOT = os.path.abspath("www")

FILE_RESPONSE_TEMPLATE = """\
HTTP/1.1 200 OK
Content-type: {content_type}
Content-length: {content_length}

""".replace("\n", "\r\n")

def serve_file(sock: socket.socket, path: str) -> None:
    """given socket and the relative path, send that file to the socket
       if file exists, if the file doesn't exist, send 404."""
    
    if path == "/":
        path = "index.html"

    abspath = os.path.normpath(os.path.join(SERVER_ROOT, path.lstrip("/")))
    if not abspath.startswith(SERVER_ROOT):
        sock.sendall(NOT_FOUND_RESPONSE)
        return
    
    try:
        with open(abspath, "rb") as f:
            #figure out its mime type and size (using os.fstat)
            stat = os.fstat(f.fileno())
            content_type, encoding = mimetypes.guess_type(abspath)
            if content_type is None:
                content_type = "application/octet-stream"

            if encoding is not None:
                content_type += f"; charset={encoding}"

            response_headers = FILE_RESPONSE_TEMPLATE.format(
                content_type=content_type,
                content_length=stat.st_size,
            ).encode("ascii")

            sock.sendall(response_headers)
            '''
            # Send the file content manually in chunks
            chunk_size = 4096
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sock.sendall(chunk)
            '''
            sock.sendfile(f)
                
    except FileNotFoundError:
        sock.sendall(NOT_FOUND_RESPONSE)
        return

# Response class definition

class Response:
    """An HTTP response.

    Parameters:
      status: The resposne status line (eg. "200 OK").
      headers: The response headers.
      body: A file containing the response body.
      content: A string representing the response body.  If this is
        provided, then body is ignored.
      encoding: An encoding for the content, if provided.
    """
    def __init__(
            self,
            status: str,
            headers: typing.Optional[Headers] = None,
            body: typing.Optional[typing.IO] = None,
            content: typing.Optional[str] = None,
            encoding: str = "utf-8"
    ) -> None:

        self.status = status.encode()
        self.headers = headers or Headers()

        if content is not None:
            self.body = io.BytesIO(content.encode(encoding))
        elif body is None:
            self.body = io.BytesIO()
        else:
            self.body = body

    def send(self,sock: socket.socket) -> None:
        """Respone to Socket."""

        raise NotImplementedError


with socket.socket() as server_sock:
    # This tells the kernel to reuse sockets that are in `TIME_WAIT` state.
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # This tells the socket what address to bind to.
    server_sock.bind((HOST, PORT))

    # Set timeout for connection
    server_sock.settimeout(20)

    # 0 is the number of pending connections the socket may have before
    # new connections are refused.  Since this server is going to process
    # one connection at a time, we want to refuse any additional connections.
    server_sock.listen(0)
    print(f"Listening on {HOST}:{PORT}...")

    #Accept the traffic and communicate with the client

    while True:

        client_sock, client_addr = server_sock.accept()
        print(f"New Con from {client_addr}.")

        # Using sendall to respond to the connection
        with client_sock:
            #for reqest_line in iter_lines(client_sock):print(request_line)
            try:
                request = Request.from_socket(client_sock)
                print(f"Received request: {request.method} {request.path}")

                ''' Implenting 100 continue
                '''
                if "100-continue" in request.headers.get("expect", ""):
                    client_sock.sendall(b"HTTP/1.1 100 Continue\r\n\r\n")

                try:
                    content_length = int(request.headers.get("content-length", "0"))
                except ValueError:
                    content_length = 0

                if content_length:
                    body = request.body.read(content_length)
                    print("Request body", body)

                if request.method != "GET":
                    client_sock.sendall(METHOD_NOT_ALLOWED_RESPONSE)
                    continue

                serve_file(client_sock, request.path)
            except Exception as e:
                print(f"Failed to parse request: {e}")
                client_sock.sendall(BAD_REQUEST_RESPONSE)