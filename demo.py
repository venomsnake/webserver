import socket

HOST = "127.0.0.1"
PORT = 9001  # Ensure this port is free

RESPONSE = b"""\
HTTP/1.1 200 OK\r
Content-Type: text/html\r
Content-Length: 15\r
\r
<h1>Hello!</h1>"""

def main():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((HOST, PORT))
            server_sock.listen(5)
            print(f"Listening on {HOST}:{PORT}....")

            # Set a timeout for accepting connections
            server_sock.settimeout(10)  # 10 seconds timeout

            try:
                client_sock, client_addr = server_sock.accept()
                print(f"New connection from {client_addr}.")

                with client_sock:
                    print("Sending response...")
                    client_sock.sendall(RESPONSE)
                    print("Response sent successfully.")
            except socket.timeout:
                print("No connections received within the timeout period.")

    except socket.error as se:
        print(f"Socket error: {se}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
