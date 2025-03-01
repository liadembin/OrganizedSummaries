from dbManager import Summary
from OCRManager import ExtractText
import datetime
import json
from typing import Callable
import os
from Crypto.PublicKey import RSA
import socket
import OCRManager
import cryptManager
import networkManager
import sys
import time
from threading import Thread
import base64
from dbManager import DbManager
import pickle

PEPPER = b"PEPPER"
id_per_sock = {}


def handle_key_exchange(
    sock, crypt: cryptManager.CryptManager
) -> networkManager.NetworkManager:
    net: networkManager.NetworkManager = networkManager.NetworkManager(sock, crypt, {})
    print("Public rsa key: ", crypt.get_public_key())
    net.send_message_plain(
        net.build_message("KEY", [crypt.get_public_key()], do_size=True)
    )
    while not net.has_received():
        time.sleep(0.1)
    public_key = net.get_message_params(net.recv_message_plain().decode())[0]
    crypt.aes_key = base64.b64decode(crypt.decrypt_rsa(base64.b64decode(public_key)))
    print("Client aes: ", crypt.aes_key)
    net.crypt_manager = crypt
    return net


def handle_login(db_manager: DbManager) -> Callable:
    def handle_login_int(
        username, password, *, net: networkManager.NetworkManager
    ) -> bool:
        salt = db_manager.get_salt(username)
        if salt is None:
            net.send_message(net.build_message("LOGIN_FAIL", []))
            return False
        password = net.crypt_manager.hash_pass(password, salt, PEPPER)
        loged = db_manager.authenticate_user(username, password)
        if loged:
            id_per_sock[net.sock] = loged.id
        events = db_manager.get_events(loged.id)
        print("Eve: ", events)
        net.send_message(
            net.build_message(
                "LOGIN_SUCCESS" if loged else "LOGIN_FAIL",
                (
                    []
                    if not loged
                    else [
                        base64.b64encode(pickle.dumps(eve)).decode()
                        for eve in filter(
                            lambda x: x["event_date"] < datetime.datetime.now(),
                            events,
                        )
                    ]
                ),
            )
        )
        # net.send_message(net.build_message("LOGIN_FAIL", []))
        return False

    return handle_login_int


def handle_register(db_manager: DbManager) -> Callable:
    def handle_register_int(
        username, password, *, net: networkManager.NetworkManager
    ) -> bool:
        salt = net.crypt_manager.generate_random_bytes(16)
        password = net.crypt_manager.hash_pass(password, salt, PEPPER)
        succsses = db_manager.insert_user(username, password, salt)

        net.send_message(
            net.build_message("REGISTER_SUCCESS" if succsses else "REGISTER_FAIL", [])
        )
        if succsses:
            print(f"Registered user {username} with password {password}")
        return False

    return handle_register_int


def handle_summaries(db_manager) -> Callable:
    def handle_summaries_in(*a, net: networkManager.NetworkManager) -> bool:
        if db_manager.get_id_per_sock(net.sock) == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        summaries = db_manager.get_all_by_user(db_manager.get_id_per_sock(net.sock))
        net.send_message(
            net.build_message(
                "TAKESUMMARIES",
                [base64.b64encode(pickle.dumps(summ)).decode() for summ in summaries],
            )
        )
        return False

    return handle_summaries_in


def handle_save(db_manager) -> Callable:
    def handle_save_in(
        title, summary, font, *, net: networkManager.NetworkManager
    ) -> bool:
        if db_manager.get_id_per_sock(net.sock) == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True

        db_manager.insert_summary(
            title, summary, db_manager.get_id_per_sock(net.sock), font
        )
        net.send_message(net.build_message("SAVE_SUCCESS", []))
        return False

    return handle_save_in


def handle_event(db_manager) -> Callable:
    def handle_event_in(
        title, datetime_str, *, net: networkManager.NetworkManager
    ) -> bool:
        if db_manager.get_id_per_sock(net.sock) == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True

        db_manager.insert_event(
            db_manager.get_id_per_sock(net.sock), title, datetime_str
        )
        net.send_message(net.build_message("EVENT_SUCCESS", []))
        return False

    return handle_event_in


# 2. Add a handler for deleting events


def handle_delete_event(db_manager) -> Callable:
    def handle_delete_event_in(event_id, *, net: networkManager.NetworkManager) -> bool:
        user_id = db_manager.get_id_per_sock(net.sock)

        if user_id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True

        success = db_manager.delete_event(event_id, user_id)

        if success:
            net.send_message(net.build_message("DELETE_SUCCESS", []))
        else:
            net.send_message(
                net.build_message(
                    "ERROR", ["Failed to delete event or event not found"]
                )
            )

        return False

    return handle_delete_event_in


def handle_file(db_manager) -> Callable:
    def handle_inner(path, *, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        # with open(f"./data/{id}/tmp/{path}", "rb") as jf
        if not os.path.exists(f"./data/{id}/tmp"):
            print("Path does not exist")
            os.makedirs(f"./data/{id}/tmp", exist_ok=False)
        if id not in handlers_per_sock_per_path:
            handlers_per_sock_per_path[id] = {}
        if path in handlers_per_sock_per_path[id]:
            net.send_message(net.build_message("ERROR", ["FILE ALREADY EXISTS(rn)"]))
            return True
        handlers_per_sock_per_path[id][path] = open(f"./data/{id}/tmp/{path}", "wb")
        print("Opened file")
        return False

    return handle_inner


handlers_per_sock_per_path = {}


def handle_chunk(db_manager) -> Callable:
    def handle_inner(path, data, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        # resuse handle later.... (matter of adding a global dict of id,
        # that leads to dict of path to file handle then seeing if it exists
        if (
            id not in handlers_per_sock_per_path
            or path not in handlers_per_sock_per_path[id]
        ):
            net.send_message(net.build_message("ERROR", ["NO FILE OPENED"]))
            return True
        f = handlers_per_sock_per_path[id][path]
        f.write(base64.b64decode(data))
        return False

    return handle_inner


def handle_end(db_manager) -> Callable:
    def handle_inner(path, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        if (
            id not in handlers_per_sock_per_path
            or path not in handlers_per_sock_per_path[id]
        ):
            net.send_message(net.build_message("ERROR", ["NO FILE OPENED"]))
            return True
        f = handlers_per_sock_per_path[id][path]
        f.close()
        del handlers_per_sock_per_path[id][path]
        return False

    return handle_inner


def handle_ocr(db_manager) -> Callable:
    def handle_inner(path, net: networkManager.NetworkManager) -> bool:
        real_path = f"./data/{db_manager.get_id_per_sock(net.sock)}/tmp/{path}"
        text = ExtractText(real_path)
        net.send_message(net.build_message("FILECONTENT", [text]))
        return False

    return handle_inner


def handle_summary(db_manager) -> Callable:
    def handle_inner(summary, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        summ = OCRManager.summarize_paragraph(
            summary, summary.count(".") - 2 if summary.count(".") > 2 else 1
        )
        print(summ)
        net.send_message(net.build_message("SUMMARY", [summ]))
        return False

    return handle_inner


def build_pdf(content):
    return content


def build_md(content):
    return content


def build_html(content):
    return content


def handle_build_file(db_manager, content, ext):
    file_bytes = content.encode()
    if ext == "pdf":
        file_bytes = build_pdf(file_bytes)
    elif ext == "md":
        file_bytes = build_md(file_bytes)
    elif ext == "html":
        file_bytes = build_html(file_bytes)
    return file_bytes


def handle_export(db_manager) -> Callable:
    def handle_inner(content, ext, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        # currently avaliable formats: txt,pdf,md,html
        if ext not in ["txt", "pdf", "md", "html"]:
            net.send_message(net.build_message("ERROR", ["INVALID FORMAT"]))
            return True
        file_bytes = handle_build_file(db_manager, content, ext)
        net.send_message(net.build_message("EXPORTED", [base64.b64encode(file_bytes)]))
        return False

    return handle_inner


def handle_get_summary(db_manager) -> Callable:
    def handle_inner(sid, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        print("Checking db")
        summ: Summary = db_manager.get_summary(sid)
        print("Sending summary: ", summ)
        if summ is None:
            net.send_message(net.build_message("ERROR", ["SUMMARY NOT FOUND"]))
            return True
        print("Sending summary: ", summ)
        with open(summ.path_to_summary, "rb") as f:
            data = f.read()
        print("Data: ", data)

        net.send_message(
            net.build_message(
                "TAKESUMMARY",
                [base64.b64encode(pickle.dumps({"data": data, "summ": summ})).decode()],
            )
        )
        return False

    return handle_inner


# Add this function to your server.py file
def handle_get_summary_by_link(db_manager) -> Callable:
    def handle_inner(link, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        print("Checking db")
        summ: Summary = db_manager.get_summary_by_link(link)
        print("Sending summary: ", summ)
        if summ is None:
            net.send_message(net.build_message("ERROR", ["SUMMARY NOT FOUND"]))
            return True
        with open(summ.path_to_summary, "rb") as f:
            data = f.read()
        print("Data: ", data)
        net.send_message(
            net.build_message("TAKESUMMARY", [base64.b64encode(data).decode()])
        )
        return False

    return handle_inner


def handle_get_events(db_manager) -> Callable:
    def handle_inner(*a, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True

        events = db_manager.get_events(id)
        print(f"Found {len(events)} events for user {id}")

        net.send_message(
            net.build_message(
                "TAKEEVENTS",
                [base64.b64encode(pickle.dumps(event)).decode() for event in events],
            )
        )
        return False

    return handle_inner


def thread_main(sock, addr, crypt):
    net: networkManager.NetworkManager = handle_key_exchange(sock, crypt)
    print("Finished key exchange for: ", addr)
    db_manager = DbManager()
    db_manager.id_per_sock = id_per_sock
    # with open("db_config.json", "rb") as f:
    #     db_manager.connect_to_db(json.loads(f.read()))
    db_manager.connect_to_db(
        {
            "host": "localhost",
            "user": "root",
            "password": (
                os.getenv("DB_PASSWORD") if os.getenv("DB_PASSWORD") else "liad8888"
            ),
            "database": "finalproj",
            "port": 3306,
        }
    )
    net.add_handler("EXIT", lambda: True)
    net.add_handler("LOGIN", handle_login(db_manager))
    net.add_handler("REGISTER", handle_register(db_manager))
    net.add_handler("GETSUMMARIES", handle_summaries(db_manager))
    net.add_handler("SAVE", handle_save(db_manager))
    net.add_handler("ADDEVENT", handle_event(db_manager))
    net.add_handler("FILE", handle_file(db_manager))
    net.add_handler("CHUNK", handle_chunk(db_manager))
    net.add_handler("END", handle_end(db_manager))
    net.add_handler("GETFILECONTENT", handle_ocr(db_manager))
    net.add_handler("SUMMARIZE", handle_summary(db_manager))
    net.add_handler("EXPORT", handle_export(db_manager))
    net.add_handler("GETSUMMARY", handle_get_summary(db_manager))
    net.add_handler("GETEVENTS", handle_get_events(db_manager))
    net.add_handler("DELETEEVENT", handle_delete_event(db_manager))
    net.add_handler("GETSUMMARYLINK", handle_get_summary_by_link(db_manager))
    while True:
        exited = net.wait_recv()
        if exited:
            print("Exiting thread")
            return


def main(sock, crypt):
    sock.listen(5)
    threads = []
    while True:
        print("Listening....")
        client_sock, addr = sock.accept()
        print(f"Connection from {addr}")
        thread = Thread(target=thread_main, args=(client_sock, addr, crypt))
        thread.start()
        threads.append(thread)
    for th in threads:
        th.join()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 12345
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    if os.path.isfile("private.pem"):
        rsa_key = RSA.import_key(open("private.pem", "rb").read())
    else:
        rsa_key = RSA.generate(2048)
        with open("private.pem", "wb") as f:
            f.write(rsa_key.export_key())
    # rsa_key = (
    #     RSA.import_key(open("private.pem", "rb").read())
    #     if os.path.isfile("private.pem")
    #     else RSA.generate(2048)
    # )

    crypt = cryptManager.CryptManager(rsa_key)
    main(sock, crypt)
    main(sock, crypt)
