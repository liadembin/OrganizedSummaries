from dbManager import Summary, DbManager
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

# from dbManager import DbManager
import pickle
import threading
from typing import Dict

PEPPER = b"PEPPER"
id_per_sock = {}
ids_per_summary_id = {}
net_per_sock = {}
lock_per_sock: Dict[socket.socket, threading.Lock] = {}
doc_changes_lock = threading.Lock()


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
        events = db_manager.get_events(loged.id) if loged else []
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
        summaries = db_manager.get_all_user_can_access(
            db_manager.get_id_per_sock(net.sock)
        )
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

        # scan if id exists, then remove
        for key, value in ids_per_summary_id.items():
            if id in value:
                value.remove(id)
                break
        if summ.id not in ids_per_summary_id:
            ids_per_summary_id[summ.id] = [id]
            spawn_summary_thread(summ, id, net, summ.id)
        else:
            ids_per_summary_id[summ.id].append(id)

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
        for key, value in ids_per_summary_id.items():
            if id in value:
                value.remove(id)
                break
        if id not in ids_per_summary_id:
            ids_per_summary_id[summ.id] = []
            spawn_summary_thread(summ, id, net, summ.id)
        ids_per_summary_id[summ.id].append(id)

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


# def handle_get_document_changes(db_manager) -> Callable:
#     def handle_inner(document_id, net: networkManager.NetworkManager) -> bool:
#         id = db_manager.get_id_per_sock(net.sock)
#         if id == -1:
#             print("NOT logged in")
#             net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
#             return True
#         changes = [
#             {"username": "u1", "position": 1, "content": "hello", "type": "insert"}
#         ]
#         # db_manager.get_document_changes(document_id)
#         net.send_message(
#             net.build_message(
#                 "TAKEDOCUMENTCHANGES",
#                 [json.dumps({"changes": changes})],
#             )
#         )
#         return False
#
#     return handle_inner
#

doc_changes = {}


def handle_update_document(db_manager) -> Callable:
    def handle_inner(changes, net: networkManager.NetworkManager) -> bool:
        global doc_changes
        global documents
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        # save into the dict
        # let the thread handle
        document_id = -1
        for k, v in ids_per_summary_id.items():
            if id in v:
                document_id = k
                break
        if document_id == -1:
            # net.send_message(net.build_message("ERROR", ["NO DOCUMENT OPENED"]))
            print("User hasnt oppened a document")
            net.send_message(net.build_message("INFO", ["NO DOCUMENT OPENED"]))
            return False
        print("Appending to Doc changes: ", doc_changes)
        with doc_changes_lock:
            if document_id not in doc_changes:
                doc_changes[document_id] = {}
            if id not in doc_changes[document_id]:
                doc_changes[document_id][id] = []
            if changes:
                doc_changes[document_id][id].append(changes)
        # print("Appended to Doc changes: ", doc_changes)
        return False

    return handle_inner


def handle_share_summary(db_manager: DbManager) -> Callable:
    def handle_inner(username, net: networkManager.NetworkManager) -> bool:
        id = db_manager.get_id_per_sock(net.sock)
        if id == -1:
            print("NOT logged in")
            net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
            return True
        summary_id = -1
        for k, v in ids_per_summary_id.items():
            if id in v:
                summary_id = k
                break
        if summary_id == -1:
            net.send_message(net.build_message("ERROR", ["NO SUMMARY OPENED"]))
            return True
        user_id = db_manager.get_id_by_username(username)
        if user_id == -1:
            net.send_message(net.build_message("ERROR", ["USER NOT FOUND"]))
            return True
        succsess = db_manager.share_summary(summary_id, id, user_id, "edit")
        if not succsess:
            net.send_message(net.build_message("ERROR", ["FAILED TO SHARE"]))
            return True
        net.send_message(net.build_message("SHARE_SUCCESS", []))
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
    # net.add_handler("GET_DOCUMENT_CHANGES", handle_get_document_changes(db_manager))
    net.add_handler("UPDATEDOC", handle_update_document(db_manager))
    net.add_handler("SHARESUMMARY", handle_share_summary(db_manager))
    net_per_sock[sock] = net
    sock.settimeout(0.5)
    while True:
        with lock_per_sock[sock]:
            try:
                exited = net.wait_recv()
                if exited:
                    print("Exiting thread")
                    return
            except socket.timeout:
                pass


def update_coordinates(sid, change_id, change_type, start, end, offset):
    """
    Update coordinates of other pending changes based on the applied change

    Parameters:
    - sid: Summary ID
    - change_id: ID of the current change being processed
    - change_type: Type of change (INSERT, DELETE, UPDATE)
    - start: Start position of the change
    - end: End position of the change
    - offset: The amount by which positions shift (positive or negative)
    """

    for other_id, other_changes in doc_changes[sid].items():
        if other_id == change_id:
            continue

        for other_change in other_changes:
            # Handle each change type's coordinate updates
            if change_type == "INSERT":
                # For inserts, all positions at or after start point are shifted
                if other_change["cord"][0] >= start:
                    other_change["cord"][0] += offset
                if other_change["cord"][1] >= start:
                    other_change["cord"][1] += offset

            elif change_type == "DELETE":
                # For deletes, positions after end shift backward
                # Positions between start and end collapse to start
                if other_change["cord"][0] >= end:
                    other_change["cord"][0] += offset
                elif other_change["cord"][0] > start:
                    other_change["cord"][0] = start

                if other_change["cord"][1] >= end:
                    other_change["cord"][1] += offset
                elif other_change["cord"][1] > start:
                    other_change["cord"][1] = start

            elif change_type == "UPDATE":
                # For updates, positions after end shift by the size difference
                if other_change["cord"][0] >= end:
                    other_change["cord"][0] += offset

                if other_change["cord"][1] >= end:
                    other_change["cord"][1] += offset


def summary_thread(sid, db_manager):
    try:
        sid = int(sid)
        with doc_changes_lock:
            doc: Summary = db_manager.get_summary(sid)
            doc_content: str = doc.content if doc and doc.content else ""
            # print(doc_changes)
            while ids_per_summary_id[sid]:
                # print(ids_per_summary_id)
                # print(
                #     f"Currently we have: {len(ids_per_summary_id[sid])} people to edit {sid}"
                # )
                while not doc_changes.get(sid, []):
                    # print("Still no changes")
                    # print(doc_changes, doc_changes[sid])
                    time.sleep(2)
                print("Processing changes")
                print(doc_changes[sid])
                # Process one batch of changes at a time
                for change_id, changes in list(doc_changes[sid].items()):
                    # Process each change in this batch
                    for change in changes:
                        change = json.loads(change)["changes"]
                        if not change:
                            print("No change, skipping")
                            continue
                        change = change[0]
                        print("Applying change: ", change)
                        start, end = change["cord"]
                        change_type = change["type"]
                        content = change.get("cont", "")
                        # Apply the change to document content
                        if change_type == "INSERT":
                            doc_content = (
                                doc_content[:start] + content + doc_content[start:]
                            )
                            offset = len(content)

                        elif change_type == "DELETE":
                            doc_content = doc_content[:start] + doc_content[end:]
                            offset = start - end

                        # elif change_type == "UPDATE":
                        else:
                            doc_content = (
                                doc_content[:start] + content + doc_content[end:]
                            )
                            offset = len(content) - (end - start)

                        # Update coordinates for all other pending changes
                        update_coordinates(
                            sid, change_id, change_type, start, end, offset
                        )

                    # Save the updated document
                    print("Final content: ", doc_content)

                    # db_manager.save_summary(sid, doc_content)

                    # Remove processed changes
                    del doc_changes[sid][change_id]
                    # ids_per_summary_id[sid].remove(change_id)
                    print("Sending changes: ")
                    print(doc_content)
                    for id in ids_per_summary_id[sid]:
                        # reverse the dict to get the sock per id
                        sock_per_id = {v: k for k, v in id_per_sock.items()}
                        with lock_per_sock[sock_per_id[id]]:
                            net = net_per_sock[sock_per_id[id]]
                            net.send_message(
                                net.build_message(
                                    "TAKEUPDATE",
                                    [doc_content],
                                )
                            )
                    print("Finished updating")
            return
    except Exception as e:
        print("Error in summary thread: ", e)
        raise e
        summary_thread(sid, db_manager)


def spawn_summary_thread(summ, id, net, sid):
    global threads
    db_manager = DbManager()
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
    thread = Thread(target=summary_thread, args=(sid, db_manager))
    thread.start()
    threads.append(thread)


def main(sock, crypt):
    sock.listen(5)
    global threads
    threads = []
    while True:
        print("Listening....")
        client_sock, addr = sock.accept()
        print(f"Connection from {addr}")
        lock_per_sock[client_sock] = threading.Lock()
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
        print("Using existing key")
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
