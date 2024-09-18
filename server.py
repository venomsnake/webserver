import mimetypes
import os
import socket
import typing
from request import Request
from response import Response
from threading import Thread
from queue import Queue, Empty

SERVER_ROOT = "www"

def serve_file(sock: socket.socket, path: str) -> None:
    """Given a socket and the relative path to a file (relative to
    SERVER_ROOT), send that file to the socket if it exists.  If the
    file doesn't exist, send a "404 Not Found" response.
    """
    if path == "/":
        path = "/index.html"

    # Create an absolute path to the file
    abspath = os.path.abspath(os.path.join(SERVER_ROOT, path.lstrip("/")))
    
    # Prevent access to files outside the SERVER_ROOT
    if not abspath.startswith(os.path.abspath(SERVER_ROOT)):
        response = Response(status="404 Not Found", content="Not Found")
        response.send(sock)
        return

    try:
        # Try to open the requested file
        with open(abspath, "rb") as f:
            content_type, encoding = mimetypes.guess_type(abspath)
            
            # Default content type if not detected
            if content_type is None:
                content_type = "application/octet-stream"
            
            # Include charset if there's an encoding
            if encoding is not None:
                content_type += f"; charset={encoding}"

            # Create a response with status 200 and send headers
            response = Response(status="200 OK", body=f)
            response.headers.add("content-type", content_type)
            response.send(sock)

            # `sendfile()` in the Response.send method handles file transfer,
            # no need for additional chunked reading and sending.
            
    except FileNotFoundError:
        # File not found, send 404 response
        response = Response(status="404 Not Found", content="Not Found")
        response.send(sock)
        return



class HTTPWorker(Thread):
    def __init__(self, connection_queue: Queue) -> None:
        super().__init__(daemon=True)

        self.connection_queue = connection_queue
        self.running = False

    def stop(self) -> None:
        self.running = False

    def run(self) -> None:
        self.running = True
        while self.running:
            try:
                client_sock, client_addr = self.connection_queue.get(timeout=1)
            except Empty:
                continue

            try:
                self.handle_client(client_sock, client_addr)
            except Exception as e:
                print(f"Unhandled error: {e}")
                continue
            finally:
                self.connection_queue.task_done()

    def handle_client(self, client_sock: socket.socket, client_addr: typing.Tuple[str, int]) -> None:
        with client_sock:
            client_sock.settimeout(10)  # Set a timeout to close idle connections
            keep_alive = True  # Flag to handle persistent connection

            while keep_alive:
                try:
                    request = Request.from_socket(client_sock)

                    # Check for 'Connection' header
                    connection_header = request.headers.get('connection', '').lower()

                    # Respond with 100 Continue if requested
                    if "100-continue" in request.headers.get("expect", ""):
                        response = Response(status="100 Continue")
                        response.send(client_sock)

                    # Handle body (if present)
                    try:
                        content_length = int(request.headers.get("content-length", "0"))
                    except ValueError:
                        content_length = 0

                    if content_length:
                        body = request.body.read(content_length)
                        print("Request body", body)

                    # Process the request (only GET supported in this case)
                    if request.method == "GET":
                        serve_file(client_sock, request.path)
                    else:
                        response = Response(status="405 Method Not Allowed", content="Method Not Allowed")
                        response.send(client_sock)

                    # Check if client wants to close the connection
                    if connection_header == "close":
                        keep_alive = False
                    else:
                        # Default behavior in HTTP/1.1 is to keep the connection open
                        keep_alive = True

                except socket.timeout:
                    # Close connection after a timeout
                    print(f"Connection timed out for {client_addr}")
                    break
                except Exception as e:
                    print(f"Failed to parse request: {e}")
                    response = Response(status="400 Bad Request", content="Bad Request")
                    response.send(client_sock)
                    break


class HTTPServer:
    def __init__(self, host="127.0.0.1", port=9000, worker_count=16) -> None:
        self.host = host
        self.port = port
        self.worker_count = worker_count
        self.worker_backlog = worker_count * 8
        self.connection_queue = Queue(self.worker_backlog)

    def serve_forever(self) -> None:
        workers = []
        for _ in range(self.worker_count):
            worker = HTTPWorker(self.connection_queue)
            worker.start()
            workers.append(worker)

        with socket.socket() as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self.host, self.port))
            server_sock.listen(self.worker_backlog)
            print(f"Listening on {self.host}:{self.port}...")
            print(f"Go to : http://{self.host}:{self.port}")

            while True:
                try:
                    self.connection_queue.put(server_sock.accept())
                except KeyboardInterrupt:
                    break

        for worker in workers:
            worker.stop()

        for worker in workers:
            worker.join(timeout=30)


server = HTTPServer()
server.serve_forever()
