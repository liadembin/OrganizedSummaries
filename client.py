import login_frame
import wx
import socket
import cryptManager
import sys
import networkManager
import base64
from wx import adv


def handle_key_exchange(sock: socket.socket):
    # recv rsa
    # send aes
    net = networkManager.NetworkManager(sock, cryptManager.CryptManager(rsa_key=2), {})
    net.crypt_manager.generate_aes_key()
    rsa_pub_msg = net.recv_message_plain().decode()
    rsa_pub_key = base64.b64decode(net.get_message_params(rsa_pub_msg)[0])
    print("THE RSA PUB \n", rsa_pub_key)
    print("The aes key ive chosen: ", net.crypt_manager.aes_key)
    aes_encrypted = net.crypt_manager.encrypt_rsa(
        base64.b64encode(net.crypt_manager.aes_key), rsa_pub_key
    )
    net.send_message_plain(
        net.build_message(
            "KEY", [base64.b64encode(aes_encrypted).decode()], do_size=True
        )
    )
    return net


def main(sock: socket.socket):
    net = handle_key_exchange(sock)
    print("Finished key exchange")
    app = wx.App()
    login_fram = login_frame.LoginFrame(net)
    login_fram.Show()
    # frame = main_frame.MainFrame(net,username)
    # frame.Show()
    app.MainLoop()
    # pass
    net.send_message(net.build_message("EXIT", []))
    net.sock.close()
    print("Exiting")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 12345
    sock = socket.socket()
    try:
        sock.connect((host, port))
        print("Connected to server")
    except Exception as e:
        print("Connection failed")
        raise e
    main(sock)
