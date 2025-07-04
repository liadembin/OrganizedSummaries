import base64
import os
import select
import threading
import time
from socket import socket
from typing import Callable, Dict, List

from cryptManager import CryptManager


class NetworkManager:
    """
    A class to manage socket communication, build and parse messages, and handle incoming messages
    with custom handlers for specific message codes.
    """

    def __init__(
        self, sock: socket, crypt: CryptManager, handlers: Dict[str, Callable]
    ) -> None:
        """
        Initialize the SocketHandler class.

        :param sock: A socket object representing the connection.
        """
        self.sock = sock
        self.handlers: Dict[str, Callable] = handlers
        self.crypt_manager = crypt
        self.lock = threading.Lock()

    def _get_file_name(self, path: str) -> str:
        return os.path.basename(path)

    def send_file(self, path) -> None:
        name = self._get_file_name(path)
        self.send_message(self.build_message("FILE", [name], False))
        with open(path, "rb") as f:
            # read chunk of 1024 at a time
            chunk = f.read(1024)
            while chunk:
                self.send_message(
                    self.build_message(
                        "CHUNK", [name, base64.b64encode(chunk).decode()], False
                    )
                )
                chunk = f.read(1024)
        print("Finished chunking the file")
        self.send_message(self.build_message("END", [name], False))

    def build_message(self, code: str, params: List[str], do_size=False) -> str:
        """
        Build a formatted message string with a code and parameters.

        :param code: The message code.
        :param params: A list of parameters to include in the message.
        :return: A formatted message string.
        """
        payload = code + "~" + "~".join(params)
        return (f"{len(payload):10}" if do_size else "") + f"{payload}"

    def send_message_plain(self, message: str) -> None:
        """

        Send a message over the socket connection.

        :param message: The message string to send.
        """
        with self.lock:
            print(f"SEND>>>{message[: min(100, len(message))]}")
            self.sock.send(message.encode())

    def has_received(self) -> bool:
        """
        Check if a new message has been received.

        :return: True if a new message is available, otherwise False.
        """
        with self.lock:
            return self.sock in select.select([self.sock], [], [], 0)[0]

    def recv_handle(self) -> None:
        """
        Receive a message from the socket connection and handle it with the appropriate handler function.
        """
        try:
            if not self.has_received():
                # print("No message received.")
                return
            message = self.recv_message()
            code = self.get_message_code(message)
            if code in self.handlers.keys():
                print("Recived code: ", code)
                self.handlers[code](*self.get_message_params(message), net=self)
            else:
                print(f"Received message with unhandled code: {code}")
                return True
        # ConnectionResetError
        except ConnectionResetError:
            print("Connection reset by peer.")
            return True

    def recv_handle_server(self, *args) -> None:
        """
        Receive a message from the socket connection and handle it with the appropriate handler function.
        """
        try:
            if not self.has_received():
                # print("No message received.")
                return
            message = self.recv_message()
            code = self.get_message_code(message)
            if code in self.handlers.keys():
                print("Recived code: ", code)
                self.handlers[code](*args, *self.get_message_params(message), net=self)
            else:
                print(f"Received message with unhandled code: {code}")
                return True
        # ConnectionResetError
        except ConnectionResetError:
            print("Connection reset by peer.")
            return True

    def recv_handle_args(self, *args) -> bool:
        """
        Receive a message from the socket connection and handle it with the appropriate handler function.
        """
        if not self.has_received():
            # print("Received message.")
            # print("No message received.")
            return False
        message = self.recv_message()
        code = self.get_message_code(message)
        if code in self.handlers.keys():
            print("Recived code: ", code)
            self.handlers[code](*args, *self.get_message_params(message), net=self)
            return True
        else:
            print(f"Received message with unhandled code: {code}")
            print("Current codes:", self.handlers.keys())
            raise Exception("Unhandled code.")

    def set_lock(self, lock):
        self.lock = lock

    def wait_recv(self) -> None:
        """
        Wait for a message to be received, then handle it automatically.
        """
        while not self.has_received():
            time.sleep(0.1)
        return self.recv_handle()

    def add_handler(self, code: str, handler: Callable) -> None:
        """
        Add a handler function for a specific message code.

        :param code: The message code.
        :param handler: A callable function to handle messages with the specified code.
        """
        self.handlers[code] = handler

    def add_handlers(self, handlers: Dict[str, Callable]) -> None:
        """
        Add multiple handlers for different message codes.

        :param handlers: A dictionary of message codes and their respective handlers.
        """
        self.handlers.update(handlers)

    def get_message_code(self, message: str) -> str:
        """
        Extract the message code from a message string.

        :param message: The message string.
        :return: The extracted message code.
        """
        return message[: message.index("~")]

    def get_message_params(self, message: str) -> List[str]:
        """
        Extract the parameters from a message string.

        :param message: The message string.
        :return: A list of extracted parameters.
        """
        return message[message.index("~") + 1 :].split("~")

    def recv_message(self):
        """
        Receive a message from the socket connection.

        :return: The received message string.
        """
        # message = self.sock.recv(10).decode()

        message = self.recv_message_plain()
        payload, iv = self.get_message_params(message.decode())
        #  print(f"DECODING WITH: {iv} \n {self.crypt_manager.aes_key}")
        msg = self.crypt_manager.decrypt_data(
            base64.b64decode(payload), base64.b64decode(iv)
        ).decode()
        print("DECODE TO: ", msg[: min(60, len(msg))])
        return msg

    def recv_message_plain(self):
        size = b""
        with self.lock:
            while len(size) < 10:
                size += self.sock.recv(10 - len(size))
            size_int = int(size.decode())
            message = b""
            while len(message) < size_int:
                try:
                    message += self.sock.recv(size_int - len(message))
                except ConnectionResetError:
                    print("Connection reset by peer.")
                    return ""
                # except:
                #     print("Socket timeout.")
                except Exception as e:
                    print("Error: ", e)
                    # return ""
                    print("Socket timeout.")

            print(f"RECV>>>{size}{message[:30]}")
            return message

    def send_message(self, message: str) -> None:
        """
        Send a message over the socket connection.

        :param message: The message string to send.
        """
        #  print("ENCRYPTING WITH: ", self.crypt_manager.aes_key)
        arr = [
            base64.b64encode(d).decode()
            for d in self.crypt_manager.encrypt_data(message.encode())
        ]
        if self.lock:
            with self.lock:
                # print("IV: ", arr[1])
                print("Using lock.")
                self.sock.send(
                    self.build_message("ENCODED", arr, do_size=True).encode()
                )
                print(f"SEND>>>{message[: min(100, len(message))]}")
        else:
            self.sock.send(self.build_message("ENCODED", arr, do_size=True).encode())
            print(f"SEND>>>{message[: min(100, len(message))]}")


import base64
from unittest.mock import MagicMock, Mock

import pytest


# === Sample Mock CryptManager ===
class MockCryptManager:
    def __init__(self):
        self.aes_key = b"mockkey123456789"

    def encrypt_data(self, data: bytes):
        return (data[::-1], b"mockiv")

    def decrypt_data(self, data: bytes, iv: bytes):
        return data[::-1]


@pytest.fixture
def mock_sock():
    sock = Mock()
    sock.recv = MagicMock(
        side_effect=[
            b"0000000032",
            b"ENCODED~"
            + base64.b64encode(b"test")[::-1]
            + b"~"
            + base64.b64encode(b"mockiv"),
        ]
    )
    sock.send = MagicMock()
    return sock


@pytest.fixture
def net_mgr(mock_sock):
    return NetworkManager(sock=mock_sock, crypt=MockCryptManager(), handlers={})


# === Unit Tests ===


def test_build_message_without_size(net_mgr):
    msg = net_mgr.build_message("CODE", ["param1", "param2"])
    assert msg == "CODE~param1~param2"


def test_build_message_with_size(net_mgr):
    msg = net_mgr.build_message("CMD", ["x", "y"], do_size=True)
    assert msg.startswith("        ")  # 10 space-padded chars for length
    assert "CMD~x~y" in msg


def test_get_file_name(net_mgr):
    assert net_mgr._get_file_name("/some/path/file.txt") == "file.txt"


def test_get_message_code_and_params(net_mgr):
    msg = "CODE~arg1~arg2~arg3"
    assert net_mgr.get_message_code(msg) == "CODE"
    assert net_mgr.get_message_params(msg) == ["arg1", "arg2", "arg3"]


def test_send_message_encodes_correctly(net_mgr, mock_sock):
    net_mgr.send_message("hello world")
    args = mock_sock.send.call_args[0][0]
    assert isinstance(args, bytes)
    assert b"ENCODED" in args


def test_recv_message_decodes_correctly(net_mgr):
    # We will override recv_message_plain to return a known encoded message
    encoded = net_mgr.build_message(
        "ENCODED",
        [
            base64.b64encode(b"dlrow olleh").decode(),  # reversed 'hello world'
            base64.b64encode(b"mockiv").decode(),
        ],
        do_size=False,
    ).encode()

    net_mgr.recv_message_plain = lambda: encoded
    result = net_mgr.recv_message()
    assert result == "hello world"


def test_add_handler_and_call(net_mgr):
    called = {}

    def mock_handler(p1, net=None):
        called["p1"] = p1

    net_mgr.add_handler("TEST", mock_handler)
    net_mgr.handlers["TEST"]("value", net=net_mgr)
    assert called["p1"] == "value"


def test_add_handlers_bulk(net_mgr):
    h1 = lambda: None
    h2 = lambda: None
    net_mgr.add_handlers({"A": h1, "B": h2})
    assert net_mgr.handlers["A"] == h1
    assert net_mgr.handlers["B"] == h2


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", "--color=yes", "--tb=short"]))
