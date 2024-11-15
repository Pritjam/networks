import argparse
import json
from typing import Dict, List, Optional, Tuple
import random
import socket
import time

ALPHA = 0.7


# Note: In this starter code, we annotate types where
# appropriate. While it is optional, both in python and for this
# course, we recommend it since it makes programming easier.

# The maximum size of the data contained within one packet
PAYLOAD_SIZE = 1200

# The maximum size of a packet including all the JSON formatting
PACKET_SIZE = 1500


class Receiver:
    def __init__(self):
        # TODO: Initialize any variables you want here, like the receive buffer
        # The buffer where we store ranges (and data for ranges) to handle
        # reordering and whatever. should be sorted by increasing seqNum

        # a buffer of ((start, end), str)
        self.buffer = []
        # The last seq num given to the app.
        self.lastSeqNum = 0
        # The list of chunks that are acknowledged
        self.acknowledged = []

    def data_packet(
        self, seq_range: Tuple[int, int], data: str
    ) -> Tuple[List[Tuple[int, int]], str]:
        """This function is called whenever a data packet is
        received. `seq_range` is the range of sequence numbers
        received: It contains two numbers: the starting sequence
        number (inclusive) and ending sequence number (exclusive) of
        the data received. `data` is a binary string of length
        `seq_range[1] - seq_range[0]` representing the data.

        It should output the list of sequence number ranges to
        acknowledge and any data that is ready to be sent to the
        application. Note, data must be sent to the application
        _reliably_ and _in order_ of the sequence numbers. This means
        that if bytes in sequence numbers 0-10000 and 11000-15000 have
        been received, only 0-10000 must be sent to the application,
        since if we send the latter bytes, we will not be able to send
        bytes 10000-11000 in order when they arrive. The solution
        layer must hide hide all packet reordering and loss.

        The ultimate behavior of the program should be that the data
        sent by the sender should be stored exactly in the same order
        at the receiver in a file in the same directory. No gaps, no
        reordering. You may assume that our test cases only ever send
        printable ASCII characters (letters, numbers, punctuation,
        newline etc), so that terminal output can be used to debug the
        program.
        """
        print("fuck")
        # handle the incoming packet
        # if it is immediately before first packet, handle that (coalesce)
        if not self.acknowledged:
            self.acknowledged.append(seq_range)
            self.buffer.append((seq_range, data))
        elif seq_range[1] == self.acknowledged[0][0]:
            self.acknowledged[0] = (seq_range[0], self.acknowledged[0][1])
            self.buffer.append((seq_range, data))
        # if it is before the first packet, insert at beginning
        elif seq_range[1] < self.acknowledged[0][0]:
            self.acknowledged.insert(0, seq_range)
            self.buffer.append((seq_range, data))
        # if it is immediately after the last packet, handle that (coalesce)
        elif seq_range[0] == self.acknowledged[-1][1]:
            self.acknowledged[-1] = (self.acknowledged[-1][0], seq_range[1])
            self.buffer.append((seq_range, data))
        # if it is after the last packet, append
        elif seq_range[0] > self.acknowledged[-1][1]:
            self.acknowledged.append(seq_range)
            self.buffer.append((seq_range, data))
        # otherwise, we have to iterate
        else:
            for i in range(len(self.acknowledged) - 1):
                # if incoming packet overlaps completely with an ack'd packet
                if (
                    seq_range[0] >= self.acknowledged[i][0]
                    and seq_range[1] <= self.acknowledged[i][1]
                ):
                    break
                # if incoming packet belongs in between this packet and the next
                if (
                    seq_range[0] >= self.acknowledged[i][1]
                    and seq_range[1] <= self.acknowledged[i + 1][0]
                ):
                    self.buffer.append((seq_range, data))
                    # full coalesce
                    if (
                        seq_range[0] == self.acknowledged[i][1]
                        and seq_range[1] == self.acknowledged[i + 1][0]
                    ):
                        temp = self.acknowledged.pop(i + 1)
                        self.acknowledged[i] = (self.acknowledged[i][0], temp[1])
                    # coalesce with prev
                    elif seq_range[0] == self.acknowledged[i][1]:
                        self.acknowledged[i] = (self.acknowledged[i][0], seq_range[1])
                    # coalesce w next
                    elif seq_range[1] == self.acknowledged[i + 1][0]:
                        self.acknowledged[i + 1] = (
                            seq_range[0],
                            self.acknowledged[i + 1][1],
                        )
                    # no coalescing, just an insert
                    else:
                        self.acknowledged.insert(i + 1, seq_range)
                    break

        # now that we've handled adding this packet to the ack list, we need to see if there's any data to return

        self.buffer.sort(key=lambda x: x[0][0])
        data_to_return = ""
        while self.buffer and self.lastSeqNum == self.buffer[0][0][0]:
            done_pckt = self.buffer.pop(0)
            data_to_return += done_pckt[1]
            self.lastSeqNum = done_pckt[0][1]

        return (self.acknowledged, data_to_return)

    def finish(self):
        """Called when the sender sends the `fin` packet. You don't need to do
        anything in particular here. You can use it to check that all
        data has already been sent to the application at this
        point. If not, there is a bug in the code. A real solution
        stack will deallocate the receive buffer. Note, this may not
        be called if the fin packet from the sender is locked. You can
        read up on "TCP connection termination" to know more about how
        TCP handles this.

        """

        print(f"range sent to app: 0 - {self.lastSeqNum}")
        if self.buffer:
            print(chr(sum(range(ord(min(str(not ())))))))
            print("buffer aint empty, something wrong :(")
            print(self.buffer)
        return


class Sender:
    def __init__(self, data_len: int):
        """`data_len` is the length of the data we want to send. A real
        solution will not force the application to pre-commit to the
        length of data, but we are ok with it.

        """
        # TODO: Initialize any variables you want here, for instance a
        # data structure to keep track of which packets have been
        # sent, acknowledged, detected to be lost or retransmitted

        # a dictionary: {(start, end): dupacks}
        # where:
        #   (start, end) is the packet that is in flight
        #   dupacks is the number of ACKs where that packet hasn't been ack'd
        self.inflight_packets = {}

        # mapping from packet_id -> send_time
        self.packet_send_times = dict()

        self.rtt_avg = 0.1
        self.rtt_var = 0.0


        self.lost_packets = False
        self.cwnd = PACKET_SIZE

        # sorted list of chunks that need to be sent still.
        self.send_queue = [(0, data_len)]

    def timeout(self):
        """Called when the sender times out."""
        # TODO: Read the relevant code in `start_sender` to figure out
        # what you should do here

        # Here, we assume that every packet that is in-flight is dropped.
        # Notice that in start_sender, their inflight is reset to 0.
        # This implies that every inflight packet needs to be resent.

        # every packet that's in-flight is assumed lost
        for packet in self.inflight_packets:
            self.send_queue.append(packet)

        self.send_queue.sort(key=lambda x: x[0])
        self.inflight_packets = {}

    def ack_packet(self, sacks: List[Tuple[int, int]], packet_id: int) -> int:
        """Called every time we get an acknowledgment. The argument is a list
        of ranges of bytes that have been ACKed. Returns the number of
        payload bytes new that are no longer in flight, either because
        the packet has been acked (measured by the unique ID) or it
        has been assumed to be lost because of dupACKs. Note, this
        number is incremental. For example, if one 100-byte packet is
        ACKed and another 500-byte is assumed lost, we will return
        600, even if 1000s of bytes have been ACKed before this.

        """
        ret = 0
        this_rtt = (
            time.monotonic()
            - self.packet_send_times[packet_id]
        )
        self.packet_send_times.pop(packet_id)
        self.rtt_avg = ALPHA * this_rtt + (1 - ALPHA) * self.rtt_avg
        self.rtt_var = ALPHA * abs(this_rtt - self.rtt_avg) + (1 - ALPHA) * self.rtt_var
        # for each in-flight packet, see if it is now ack'd or dropped
        counter = len(self.inflight_packets)
        for packet in sorted(self.inflight_packets.keys(), key=lambda x: x[0]):
            counter -= 1
            for ack in sacks:
                if packet[0] >= ack[0] and packet[1] <= ack[1]:
                    # this inflight packet is good to go, it is no longer inflight
                    self.inflight_packets.pop(packet)
                    # print("=====Packet is ACKd, adding its size: ", packet)
                    ret += packet[1] - packet[0]
                    break
            # if we reach this point, then that inflight packet hasn't been ack'd yet
            # so we will increment it's dupack counter
            else:
                # self.inflight_packets[packet] += 1
                if self.inflight_packets[packet] > 2:
                    # 3 dupacks means probably lost packet, add back to send queue
                    # print("=====Assuming packet is dropped: ", packet)
                    self.lost_packets = True
                    self.inflight_packets.pop(packet)
                    self.send_queue.append(packet)
                    self.send_queue.sort(key=lambda x: x[0])
                    ret += packet[1] - packet[0]
        assert counter == 0
        return ret

    def send(self, packet_id: int) -> Optional[Tuple[int, int]]:
        """Called just before we are going to send a data packet. Should
        return the range of sequence numbers we should send. If there
        are no more bytes to send, returns a zero range (i.e. the two
        elements of the tuple are equal). Returns None if there are no
        more bytes to send, and _all_ bytes have been
        acknowledged. Note: The range should not be larger than
        `payload_size` or contain any bytes that have already been
        acknowledged

        """
        # print("FULLSEND")

        if not self.send_queue:
            if not self.inflight_packets:
                return None
            return (0, 0)

        # take the highest-priority item to send
        to_send = self.send_queue.pop(0)

        # if that packet is too big, split it and keep the second half in the send queue
        if to_send[1] - to_send[0] > PAYLOAD_SIZE:
            self.send_queue.insert(0, (to_send[0] + PAYLOAD_SIZE, to_send[1]))
            to_send = (to_send[0], to_send[0] + PAYLOAD_SIZE)
        # now track it as in_flight
        assert to_send not in self.inflight_packets
        self.inflight_packets[to_send] = 0
        # print(f'trying to send: {to_send}')
        self.packet_send_times[packet_id] = time.monotonic()
        return to_send

    def get_cwnd(self) -> int:
        if self.lost_packets:
            self.cwnd /= 2
            self.lost_packets = False
        else:
            self.cwnd += 1
        return self.cwnd

    def get_rto(self) -> float:
        return self.rtt_avg + 4 * self.rtt_var


def start_receiver(ip: str, port: int):
    """Starts a receiver thread. For each source address, we start a new
    `Receiver` class. When a `fin` packet is received, we call the
    `finish` function of that class.

    We start listening on the given IP address and port. By setting
    the IP address to be `0.0.0.0`, you can make it listen on all
    available interfaces. A network interface is typically a device
    connected to a computer that interfaces with the physical world to
    send/receive packets. The WiFi and ethernet cards on personal
    computers are examples of physical interfaces.

    Sometimes, when you start listening on a port and the program
    terminates incorrectly, it might not release the port
    immediately. It might take some time for the port to become
    available again, and you might get an error message saying that it
    could not bind to the desired port. In this case, just pick a
    different port. The old port will become available soon. Also,
    picking a port number below 1024 usually requires special
    permission from the OS. Pick a larger number. Numbers in the
    8000-9000 range are conventional.

    Virtual interfaces also exist. The most common one is `localhost',
    which has the default IP address of `127.0.0.1` (a universal
    constant across most machines). The Mahimahi network emulator also
    creates virtual interfaces that behave like real interfaces, but
    really only emulate a network link in software that shuttles
    packets between different virtual interfaces.

    """

    receivers: Dict[str, Tuple[Receiver, Any]] = {}
    received_data = ""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.bind((ip, port))

        while True:
            data, addr = server_socket.recvfrom(PACKET_SIZE)
            if addr not in receivers:
                receivers[addr] = Receiver()

            received = json.loads(data.decode())
            if received["type"] == "data":
                # Format check. Real code will have much more
                # carefully designed checks to defend against
                # attacks. Can you think of ways to exploit this
                # transport layer and cause problems at the receiver?
                # This is just for fun. It is not required as part of
                # the assignment.
                assert type(received["seq"]) is list
                assert (
                    type(received["seq"][0]) is int and type(received["seq"][1]) is int
                )
                assert type(received["payload"]) is str
                assert len(received["payload"]) <= PAYLOAD_SIZE

                # Deserialize the packet. Real transport layers use
                # more efficient and standardized ways of packing the
                # data. One option is to use protobufs (look it up)
                # instead of json. Protobufs can automatically design
                # a byte structure given the data structure. However,
                # for an internet standard, we usually want something
                # more custom and hand-designed.
                sacks, app_data = receivers[addr].data_packet(
                    tuple(received["seq"]), received["payload"]
                )
                # Note: we immediately write the data to file
                # receivers[addr][1].write(app_data)

                # Send the ACK
                server_socket.sendto(
                    json.dumps(
                        {"type": "ack", "sacks": sacks, "id": received["id"]}
                    ).encode(),
                    addr,
                )

            elif received["type"] == "fin":
                receivers[addr].finish()
                del receivers[addr]

            else:
                assert False


def start_sender(ip: str, port: int, data: str, recv_window: int, simloss: float):
    sender = Sender(len(data))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        # So we can receive messages
        client_socket.connect((ip, port))
        # When waiting for packets when we call receivefrom, we
        # shouldn't wait more than 500ms

        # Number of bytes that we think are inflight. We are only
        # including payload bytes here, which is different from how
        # TCP does things
        inflight = 0
        packet_id = 0
        wait = False

        while True:
            # Get the congestion condow
            cwnd = sender.get_cwnd()

            # Do we have enough room in recv_window to send an entire
            # packet?
            if inflight + PACKET_SIZE <= min(recv_window, cwnd) and not wait:
                seq = sender.send(packet_id)
                if seq is None:
                    # We are done sending
                    client_socket.send('{"type": "fin"}'.encode())
                    break
                elif seq[1] == seq[0]:
                    # No more packets to send until loss happens. Wait
                    wait = True
                    continue

                assert seq[1] - seq[0] <= PAYLOAD_SIZE
                assert seq[1] <= len(data)

                # Simulate random loss before sending packets
                if random.random() < simloss:
                    pass
                else:
                    # Send the packet
                    client_socket.send(
                        json.dumps(
                            {
                                "type": "data",
                                "seq": seq,
                                "id": packet_id,
                                "payload": data[seq[0] : seq[1]],
                            }
                        ).encode()
                    )

                inflight += seq[1] - seq[0]
                packet_id += 1

            else:
                wait = False
                # Wait for ACKs
                try:
                    rto = sender.get_rto()
                    client_socket.settimeout(rto)
                    received_bytes = client_socket.recv(PACKET_SIZE)
                    received = json.loads(received_bytes.decode())
                    assert received["type"] == "ack"

                    if random.random() < simloss:
                        continue

                    inflight -= sender.ack_packet(received["sacks"], received["id"])
                    assert inflight >= 0
                except socket.timeout:
                    inflight = 0
                    print("Timeout")
                    sender.timeout()


def main():
    parser = argparse.ArgumentParser(description="Transport assignment")
    parser.add_argument(
        "role",
        choices=["sender", "receiver"],
        help="Role to play: 'sender' or 'receiver'",
    )
    parser.add_argument(
        "--ip", type=str, required=True, help="IP address to bind/connect to"
    )
    parser.add_argument(
        "--port", type=int, required=True, help="Port number to bind/connect to"
    )
    parser.add_argument(
        "--sendfile",
        type=str,
        required=False,
        help="If role=sender, the file that contains data to send",
    )
    parser.add_argument(
        "--recv_window", type=int, default=15000000, help="Receive window size in bytes"
    )
    parser.add_argument(
        "--simloss",
        type=float,
        default=0.0,
        help="Simulate packet loss. Provide the fraction of packets (0-1) that should be randomly dropped",
    )

    args = parser.parse_args()

    if args.role == "receiver":
        start_receiver(args.ip, args.port)
    else:
        if args.sendfile is None:
            print("No file to send")
            return

        with open(args.sendfile, "r") as f:
            data = f.read()
            start_sender(args.ip, args.port, data, args.recv_window, args.simloss)


if __name__ == "__main__":
    main()
