import socket

# Define server address and port
server_address = ('0.0.0.0', 25565)

# Create a UDP socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind(server_address)
    print(f"Listening on {server_address}")

    while True:
        # Receive data from the client
        data, address = sock.recvfrom(1024)  # buffer size is 1024 bytes
        print(f"Received message from {address}: {data.decode()}")
