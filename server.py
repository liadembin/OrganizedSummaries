import base64
import datetime
import json
import os
# from dbManager import DbManager
import pickle
import socket
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from threading import Thread
from typing import Dict, Optional

import dotenv
from Crypto.PublicKey import RSA
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import cryptManager
import networkManager
import OCRManager
from dbManager import DbManager, Summary
from OCRManager import ExtractText

PEPPER = b"PEPPER"
id_per_sock = {}
ids_per_summary_id = {}
net_per_sock = {}
# lock_per_sock: Dict[socket.socket, threading.Lock] = {}
# doc_changes_lock = threading.Lock()
lock_per_doc = {}
historic_id_per_sock = {}
handlers_per_sock_per_path = {}
doc_changes = {}
EVENT_DAY_REMIND = 7
USE_MYSQL = True
user_cursors = {}
change_history = {}
user_selections = {}


class LockType(Enum):
    """Types of document locks"""

    CHARACTER = 1  # Lock individual characters
    WORD = 2  # Lock entire words
    LINE = 3  # Lock entire lines


LOCK_GRANULARITY = LockType.CHARACTER  # Can be changed to WORD or LINE
ENABLE_OPERATIONAL_TRANSFORM = not not True  # Enable advanced conflict resolution
MAX_HISTORY_LENGTH = 100


@dataclass
class UserState:
    id: int
    net: networkManager.NetworkManager
    historic_id: Optional[int] = None  # ID of the historic summary being accessed


state_per_sock: Dict[socket.socket, UserState] = {}


def handle_key_exchange(
    sock, crypt: cryptManager.CryptManager
) -> networkManager.NetworkManager | None:
    net: networkManager.NetworkManager = networkManager.NetworkManager(sock, crypt, {})
    # print("Public rsa key: ", crypt.get_public_key())
    net.send_message_plain(
        net.build_message("KEY", [crypt.get_public_key()], do_size=True)
    )
    while not net.has_received():
        time.sleep(0.1)
    plain = net.recv_message_plain()
    if plain == b"" or plain == "":
        print("Client disconnected during key exchange")
        return None
    public_key = net.get_message_params(plain.decode())[0]
    crypt.aes_key = base64.b64decode(crypt.decrypt_rsa(base64.b64decode(public_key)))
    net.crypt_manager = crypt
    return net


def handle_login(
    db_manager: DbManager, username, password, *, net: networkManager.NetworkManager
) -> bool:
    salt = db_manager.get_salt(username)
    if salt is None:
        net.send_message(net.build_message("LOGIN_FAIL", []))
        return False
    password = net.crypt_manager.hash_pass(password, salt, PEPPER)
    loged = db_manager.authenticate_user(username, password)
    if loged:
        id_per_sock[net.sock] = loged.id
        state_per_sock[net.sock] = UserState(loged.id, net, None)
    events = db_manager.get_events(loged.id) if loged else []
    # print("Eve: ", events)
    N_days_from_today = datetime.datetime.now() + datetime.timedelta(
        days=EVENT_DAY_REMIND
    )
    print(N_days_from_today)
    print(events)
    net.send_message(
        net.build_message(
            "LOGIN_SUCCESS" if loged else "LOGIN_FAIL",
            (
                []
                if not loged
                else [
                    base64.b64encode(pickle.dumps(eve)).decode()
                    for eve in filter(
                        lambda x: x["event_date"] <= N_days_from_today,
                        events,
                    )
                ]
            ),
        )
    )
    return False


def handle_register(
    db_manager: DbManager, username, password, *, net: networkManager.NetworkManager
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


def handle_summaries(db_manager, *a, net: networkManager.NetworkManager) -> bool:
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    summaries = db_manager.get_all_user_can_access(db_manager.get_id_per_sock(net.sock))
    net.send_message(
        net.build_message(
            "TAKESUMMARIES",
            [base64.b64encode(pickle.dumps(summ)).decode() for summ in summaries],
        )
    )
    return False


def handle_save(
    db_manager, title, summary, font, *, net: networkManager.NetworkManager
) -> bool:
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    print("Saving title: ", title)
    # net.send_message(net.build_message("ERROR",["ASD"]))
    if title == "":
        sid = -1
        for k, v in ids_per_summary_id.items():
            if db_manager.get_id_per_sock(net.sock) in v:
                sid = k
                break
        print(f"Updating, {sid=}")
        db_manager.update_summary(sid, summary, font)

    else:
        db_manager.insert_summary(
            title, summary, db_manager.get_id_per_sock(net.sock), font
        )
    net.send_message(net.build_message("SAVE_SUCCESS", [""]))
    return False


def handle_event(
    db_manager, title, datetime_str, *, net: networkManager.NetworkManager
) -> bool:
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True

    db_manager.insert_event(db_manager.get_id_per_sock(net.sock), title, datetime_str)
    even = db_manager.get_event(db_manager.get_id_per_sock(net.sock), title)
    net.send_message(
        net.build_message(
            "EVENT_SUCCESS", [base64.b64encode(pickle.dumps(even)).decode()]
        )
    )
    return False


def handle_delete_event(
    db_manager, event_id, *, net: networkManager.NetworkManager
) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)

    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True

    success = db_manager.delete_event(event_id, user_id)

    if success:
        net.send_message(net.build_message("DELETE_SUCCESS", [str(event_id)]))
    else:
        net.send_message(
            net.build_message("ERROR", ["Failed to delete event or event not found"])
        )

    return False


def handle_file(db_manager, path, *, net: networkManager.NetworkManager) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    # with open(f"./data/{id}/tmp/{path}", "rb") as jf
    if not os.path.exists(f"./data/{user_id}/tmp"):
        print("Path does not exist")
        os.makedirs(f"./data/{user_id}/tmp", exist_ok=False)
    if user_id not in handlers_per_sock_per_path:
        handlers_per_sock_per_path[user_id] = {}
    if path in handlers_per_sock_per_path[user_id]:
        net.send_message(net.build_message("ERROR", ["FILE ALREADY EXISTS(rn)"]))
        return True
    handlers_per_sock_per_path[user_id][path] = open(
        f"./data/{user_id}/tmp/{path}", "wb"
    )
    return False


def handle_chunk(db_manager, path, data, net: networkManager.NetworkManager) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    # resuse handle later.... (matter of adding a global dict of id,
    # that leads to dict of path to file handle then seeing if it exists
    if (
        user_id not in handlers_per_sock_per_path
        or path not in handlers_per_sock_per_path[user_id]
    ):
        net.send_message(net.build_message("ERROR", ["NO FILE OPENED"]))
        return True
    f = handlers_per_sock_per_path[user_id][path]
    f.write(base64.b64decode(data))
    return False


def handle_end(db_manager, path, net: networkManager.NetworkManager) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if db_manager.get_is_sock_logged(net.sock) == -1:
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    if (
        user_id not in handlers_per_sock_per_path
        or path not in handlers_per_sock_per_path[user_id]
    ):
        net.send_message(net.build_message("ERROR", ["NO FILE OPENED"]))
        return True
    f = handlers_per_sock_per_path[user_id][path]
    f.close()
    del handlers_per_sock_per_path[user_id][path]
    return False


def handle_ocr(db_manager, path, net: networkManager.NetworkManager) -> bool:
    # in real life we would have to prevent the RFI LFI
    # but for now we just assume the path is safe
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    if "." in path or ".." in path or path.startswith("/") or path.startswith("\\"):
        net.send_message(net.build_message("ERROR", ["INVALID PATH"]))
        return True
    real_path = f"./data/{db_manager.get_id_per_sock(net.sock)}/tmp/{path}"
    text = ExtractText(real_path)
    net.send_message(net.build_message("FILECONTENT", [text]))
    return False


def handle_summary(db_manager, summary, net: networkManager.NetworkManager) -> bool:
    # id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    summ = OCRManager.summarize_paragraph(
        summary, summary.count(".") - 2 if summary.count(".") > 2 else 1
    )
    net.send_message(net.build_message("SUMMARY", [summ]))
    return False


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


def handle_export(db_manager, content, ext, net: networkManager.NetworkManager) -> bool:
    # id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    # currently avaliable formats: txt,pdf,md,html
    if ext not in ["txt", "pdf", "md", "html"]:
        net.send_message(net.build_message("ERROR", ["INVALID FORMAT"]))
        return True
    file_bytes = handle_build_file(db_manager, content, ext)
    net.send_message(
        net.build_message("EXPORTED", [base64.b64encode(file_bytes).decode()])
    )
    return False


def handle_get_summary(db_manager, sid, net: networkManager.NetworkManager) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    summ: Summary = db_manager.get_summary(sid)
    if summ is None:
        net.send_message(net.build_message("ERROR", ["SUMMARY NOT FOUND"]))
        return True
    with open(summ.path_to_summary, "rb") as f:
        data = f.read()

    net.send_message(
        net.build_message(
            "TAKESUMMARY",
            [base64.b64encode(pickle.dumps({"data": data, "summ": summ})).decode()],
        )
    )

    # scan if id exists, then remove
    for _, value in ids_per_summary_id.items():
        if user_id in value:
            value.remove(user_id)
            break
    if summ.id not in ids_per_summary_id:
        ids_per_summary_id[summ.id] = [user_id]
        spawn_summary_thread(summ, user_id, net, summ.id)
    else:
        ids_per_summary_id[summ.id].append(user_id)

    return False


# Add this function to your server.py file
def handle_get_summary_by_link(
    db_manager, link, net: networkManager.NetworkManager
) -> bool:
    # id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    print("Checking db")
    summ: Summary = db_manager.get_summary_by_link(link)
    # print("Sending summary: ", summ)
    if summ is None:
        net.send_message(net.build_message("ERROR", ["SUMMARY NOT FOUND"]))
        return True

    # with open(summ.path_to_summary, "rb") as f:
    #     data = f.read()
    # print("Data: ", data)
    net.send_message(
        # net.build_message("TAKESUMMARY", [base64.b64encode(data).decode()])
        # net.build_message("TAKESUMMARY",[base64.b64encode(pickle.dumps({"data": data, "summ": summ})).decode() ])
        net.build_message("TAKESUMMARYLINK", [str(summ.id)])
    )
    # for key, value in ids_per_summary_id.items():
    #     if id in value:
    #         value.remove(id)
    #         break
    # if id not in ids_per_summary_id:
    #     ids_per_summary_id[summ.id] = []
    #     spawn_summary_thread(summ, id, net, summ.id)
    # ids_per_summary_id[summ.id].append(id)
    #
    return False


def handle_get_events(db_manager, *a, net: networkManager.NetworkManager) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True

    events = db_manager.get_events(user_id)
    print(f"Found {len(events)} events for user {user_id}")

    net.send_message(
        net.build_message(
            "TAKEEVENTS",
            [base64.b64encode(pickle.dumps(event)).decode() for event in events],
        )
    )
    return False


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


def handle_update_document(
    db_manager, changes, net: networkManager.NetworkManager
) -> bool:
    global doc_changes
    global documents
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    # save into the dict
    # let the thread handle
    document_id = -1
    for k, v in ids_per_summary_id.items():
        if user_id in v:
            document_id = k
            break
    if document_id == -1:
        # net.send_message(net.build_message("ERROR", ["NO DOCUMENT OPENED"]))
        print("User hasnt oppened a document")
        net.send_message(net.build_message("INFO", ["NO DOCUMENT OPENED"]))
        return False
    # print("Appending to Doc changes: ", doc_changes)
    with lock_per_doc[document_id]:  # doc_changes_lock:
        if document_id not in doc_changes:
            doc_changes[document_id] = {}
        if user_id not in doc_changes[document_id]:
            doc_changes[document_id][user_id] = []
        # print(type(changes))
        # print("changes: ", changes)
        # print("changes[changes]: ", changes["changes"])

        if json.loads(changes)["changes"]:
            doc_changes[document_id][user_id].append(changes)
            # print("Appended: ", changes)
            # print("\n\n\n")
        # else:
        # print("No changes to append? ")
    # print("Appended to Doc changes: ", doc_changes)
    return False


def handle_share_summary(
    db_manager: DbManager, username, net: networkManager.NetworkManager
) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    summary_id = -1
    for k, v in ids_per_summary_id.items():
        if user_id in v:
            summary_id = k
            break
    if summary_id == -1:
        net.send_message(net.build_message("ERROR", ["NO SUMMARY OPENED"]))
        return True
    user_id = db_manager.get_id_by_username(username)
    if user_id == -1:
        net.send_message(net.build_message("ERROR", ["USER NOT FOUND"]))
        return True
    succsess = db_manager.share_summary(summary_id, user_id, user_id, "edit")
    if not succsess:
        net.send_message(net.build_message("ERROR", ["FAILED TO SHARE"]))
        return True
    net.send_message(net.build_message("SHARE_SUCCESS", []))
    return False


def handle_get_graph(db_manager, *_, net: networkManager.NetworkManager) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    sid = -1
    for k, v in ids_per_summary_id.items():
        if user_id in v:
            sid = k
            break
    if sid == -1:
        net.send_message(net.build_message("ERROR", ["NO SUMMARY OPENED"]))
        return True
    print("Getting graph for: ", sid)
    graph = db_manager.get_graph(sid)
    net.send_message(
        net.build_message("TAKEGRAPH", [base64.b64encode(pickle.dumps(graph)).decode()])
    )
    return False


def handle_saving_events(
    db_manager, jsoned_events, net: networkManager.NetworkManager
) -> bool:
    user_id = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    # print("Saving events: ", jsoned_events)
    events = pickle.loads(base64.b64decode(jsoned_events))  # json.loads(jsoned_events)
    # print(events)
    print(events)
    for event in events:
        db_manager.insert_event(user_id, event["event_title"], event["event_date"])
    net.send_message(net.build_message("INFO", ["Event successfully added"]))
    return False


def get_historic_list(db_manager, *_, net: networkManager.NetworkManager) -> bool:
    #_= db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    sid = -1
    for k, v in ids_per_summary_id.items():
        if db_manager.get_id_per_sock(net.sock) in v:
            sid = k
            break
    if sid == -1:
        net.send_message(net.build_message("ERROR", ["NO SUMMARY OPENED"]))
        return True
    # read the directory save/{sid}/ (read sub directorys which are all timestamps)
    dirs = os.listdir(f"save/{sid}/")
    net.send_message(
        net.build_message(
            "HISTORICLIST", [base64.b64encode(pickle.dumps(dirs)).decode()]
        )
    )
    return False


def load_historic_summary(
    db_manager, timestamp, net: networkManager.NetworkManager
) -> bool:
    uid = db_manager.get_id_per_sock(net.sock)
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    sid = -1
    for k, v in ids_per_summary_id.items():
        if db_manager.get_id_per_sock(net.sock) in v:
            sid = k
            break
    if sid == -1:
        net.send_message(net.build_message("ERROR", ["NO SUMMARY OPENED"]))
        return True
    # read the directory save/{sid}/{timestamp}/ (read sub directorys which are all timestamps)
    if not db_manager.can_access(sid, db_manager.get_id_per_sock(net.sock)):
        net.send_message(net.build_message("ERROR", ["NO PERMISSION"]))
        return True

    with open(f"save/{sid}/{timestamp}/summary.md", "rb") as f:
        data = f.read()
    # remove the user from the queues
    for _, value in ids_per_summary_id.items():
        if uid in value:
            value.remove(uid)
            break
    # remove the user from the doc_changes
    summ: Summary = db_manager.get_summary(sid)
    summ.content = data.decode()
    historic_id_per_sock[db_manager.get_id_per_sock(net.sock)] = summ.id
    net.send_message(
        net.build_message(
            "TAKEHIST",
            [base64.b64encode(pickle.dumps({"data": data, "summ": summ})).decode()],
        )
    )
    return False


def handle_historic_graph(
    db_manager, timestamp, net: networkManager.NetworkManager
) -> bool:
    if not db_manager.get_is_sock_logged(net.sock):
        print("NOT logged in")
        net.send_message(net.build_message("ERROR", ["NOT LOGGED IN"]))
        return True
    uid = db_manager.get_id_per_sock(net.sock)
    if uid not in historic_id_per_sock:
        print("NO HISTORIC ID for: ", net.sock)
        print(historic_id_per_sock)
        net.send_message(net.build_message("ERROR", ["NO HISTORIC ID"]))
        return True
    sid = historic_id_per_sock[uid]

    # check premission of user to access the sumamry
    if not db_manager.can_access(sid, db_manager.get_id_per_sock(net.sock)):
        net.send_message(net.build_message("ERROR", ["NO PERMISSION"]))
        return True
    # read the directory save/{sid}/{timestamp}/graph.pkl
    # format as:("%Y%m%d%H%M%S") from YYYY-MM-DD HH:MM:SS
    dt_obj = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    timestampftm = dt_obj.strftime("%Y%m%d%H%M%S")
    with open(f"save/{sid}/{timestampftm}/graph.pkl", "rb") as f:
        data = f.read()
    dumped_data = base64.b64encode(data).decode()
    net.send_message(net.build_message("TAKEGRAPH", [dumped_data]))
    return False


def handle_import_gcal(db_manage, *_, net: networkManager.NetworkManager) -> bool:

    creds = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", scopes=["https://www.googleapis.com/auth/calendar.readonly"]
    ).run_local_server(port=0)

    service = build("calendar", "v3", credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + "Z"

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    items = events_result.get("items", [])

    events = []
    for e in items:
        dt_str = e["start"].get("dateTime", e["start"].get("date"))
        dt = datetime.datetime.fromisoformat(dt_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)

        events.append(
            {
                "event_title": e.get("summary", "No Title"),
                "event_date": dt,
                "createTime": datetime.datetime.now(),
            }
        )

    encoded = base64.b64encode(pickle.dumps(events)).decode()
    net.send_message(net.build_message("GCAL_EVENTS", [encoded]))
    return False


def thread_main(sock, addr, crypt):
    net: networkManager.NetworkManager | None = handle_key_exchange(sock, crypt)
    if net is None:
        print("Client disconnected during key exchange")
        return
    net.set_lock(threading.Lock())
    print("Finished key exchange for: ", addr)
    db_manager = DbManager()
    db_manager.id_per_sock = id_per_sock
    # with open("db_config.json", "rb") as f:
    #     db_manager.connect_to_db(json.loads(f.read()))
    if USE_MYSQL:
        db_manager.connect_to_db(
            {
                "host": os.getenv("DB_HOST"),
                "user": os.getenv("DB_USERNAME"),
                "password": (os.getenv("DB_PASSWORD")),
                "database": os.getenv("DB_NAME"),
                "port": os.getenv("DB_PORT"),
            }
        )
    else:
        db_manager.connect_to_sqlite({"db_type": "sqlite", "database": "dbconved.db"})
    net.add_handler("EXIT", lambda: True)
    net.add_handler("LOGIN", handle_login)
    net.add_handler("REGISTER", handle_register)
    net.add_handler("GETSUMMARIES", handle_summaries)
    net.add_handler("SAVE", handle_save)
    net.add_handler("ADDEVENT", handle_event)
    net.add_handler("FILE", handle_file)
    net.add_handler("CHUNK", handle_chunk)
    net.add_handler("END", handle_end)
    net.add_handler("GETFILECONTENT", handle_ocr)
    net.add_handler("SUMMARIZE", handle_summary)
    net.add_handler("EXPORT", handle_export)
    net.add_handler("GETSUMMARY", handle_get_summary)
    net.add_handler("GETEVENTS", handle_get_events)
    net.add_handler("DELETEEVENT", handle_delete_event)
    net.add_handler("GETSUMMARYLINK", handle_get_summary_by_link)
    # net.add_handler("GET_DOCUMENT_CHANGES", handle_get_document_changes)
    net.add_handler("UPDATEDOC", handle_update_document)
    net.add_handler("SHARESUMMARY", handle_share_summary)
    net.add_handler("GETGRAPH", handle_get_graph)
    net.add_handler("SAVE_EVENTS", handle_saving_events)
    net.add_handler("GETHISTORICLIST", get_historic_list)
    net.add_handler("LOADHISTORIC", load_historic_summary)
    net.add_handler("HISTORICGRAPH", handle_historic_graph)
    net.add_handler("IMPORT_GCAL", handle_import_gcal)
    net_per_sock[sock] = net
    sock.settimeout(0.5)
    try:
        while True:
            # with lock_per_sock[sock]:
            try:
                exited = net.recv_handle_server(db_manager)  # net.wait_recv()
                if exited:
                    print("Exiting thread")

                    for _, value in ids_per_summary_id.items():

                        if id_per_sock[sock] in value:
                            value.remove(id_per_sock[sock])
                            break
                    if sock in id_per_sock:
                        del id_per_sock[sock]
                    # delete from ids_per_summary_id
                    return
                # time.sleep(1)
            except socket.timeout:
                print("Timeout lock outght to free")
                
    finally:
        if sock in id_per_sock:
            del id_per_sock[sock]
        # delete from ids_per_summary_id
        # with doc_changes_lock:
        for _, value in ids_per_summary_id.items():
            if id_per_sock[sock] in value:
                value.remove(id_per_sock[sock])
                break


def update_insert_coordinates(change_data, start, offset):
    """Update coordinates for INSERT operations"""
    start_pos, end_pos = change_data["cord"]

    # For inserts, shift positions at or after the insertion point
    if start_pos >= start:
        change_data["cord"][0] += offset
    if end_pos >= start:
        change_data["cord"][1] += offset


def update_delete_coordinates(change_data, start, end, offset):
    """Update coordinates for DELETE operations"""
    start_pos, end_pos = change_data["cord"]

    # For deletes, handle positions based on their relation to deleted segment
    if start_pos >= end:
        # Position is after the deleted segment, shift backward
        change_data["cord"][0] += offset
    elif start_pos > start:
        # Position is within deleted segment, collapse to start
        change_data["cord"][0] = start

    if end_pos >= end:
        # End position is after deleted segment
        change_data["cord"][1] += offset
    elif end_pos > start:
        # End position is within deleted segment
        change_data["cord"][1] = start


def update_update_coordinates(change_data, end, offset):
    """Update coordinates for UPDATE operations"""
    start_pos, end_pos = change_data["cord"]

    # For updates, shift positions after the update point by offset
    if start_pos >= end:
        change_data["cord"][0] += offset
    if end_pos >= end:
        change_data["cord"][1] += offset


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
    # Skip if there are no changes for this summary
    if sid not in doc_changes:
        return

    # Process each pending change in the document
    for other_id, other_changes in doc_changes[sid].items():
        # Skip the current change being applied
        if other_id == change_id:
            continue

        for other_change in other_changes:
            if change_type == "INSERT":
                update_insert_coordinates(other_change, start, offset)
            elif change_type == "DELETE":
                update_delete_coordinates(other_change, start, end, offset)
            elif change_type == "UPDATE":
                update_update_coordinates(other_change, end, offset)


# def apply_change(doc_content, change):
#     """Apply a single change to the document content"""
#     start, end = change["cord"]
#     change_type = change["type"]
#     content = change.get("cont", "")
#
#     if change_type == "INSERT":
#         # Insert content at the specified position
#         new_content = doc_content[:start] + content + doc_content[start:]
#         offset = len(content)
#     elif change_type == "DELETE":
#         # Remove content between start and end
#         new_content = doc_content[:start] + doc_content[end:]
#         offset = start - end
#     else:  # UPDATE
#         # Replace content between start and end
#         new_content = doc_content[:start] + content + doc_content[end:]
#         offset = len(content) - (end - start)
#
#     return new_content, offset, change_type, start, end


def process_changes(sid, doc_content):
    """Process all pending changes for a summary"""
    changes_processed = False

    # Process each batch of changes (one change_id at a time)
    for change_id, changes in list(doc_changes[sid].items()):
        for change_data in changes:
            # Parse the change data
            change_obj = json.loads(change_data)["changes"]
            if not change_obj:
                print("Empty change object, skipping")
                continue

            # Process the first change in the batch
            change = change_obj[0]
            print(f"Applying change: {change}")

            # Apply the change
            doc_content, offset, change_type, start, end = apply_change(
                doc_content, change
            )

            # Update coordinates of all other pending changes
            update_coordinates(sid, change_id, change_type, start, end, offset)

        # Remove processed changes
        del doc_changes[sid][change_id]
        changes_processed = True

    return doc_content, changes_processed


# def send_updates_to_users(sid, doc_content):
#     """Send updated content to all connected users"""
#     connected_users = ids_per_summary_id[sid]
#     print(f"Sending updates to {len(connected_users)} connected users")
#
#     for user_id in connected_users:
#         try:
#             # Get the socket associated with this user
#             sock_per_id = {v: k for k, v in id_per_sock.items()}
#             user_socket = sock_per_id[user_id]
#
#             # Send the updated content
#             net = net_per_sock[user_socket]
#             update_message = net.build_message(
#                 "TAKEUPDATE",
#                 [
#                     base64.b64encode(
#                         json.dumps({"doc_content": doc_content}).encode()
#                     ).decode()
#                 ],
#             )
#             net.send_message(update_message)
#             print(f"Update sent to user {user_id}")
#         except Exception as e:
#             print(f"Error sending update to user {user_id}: {e}")


def get_lock_boundaries(content, position, lock_type=LockType.CHARACTER):
    """
    Determine the boundaries of the lock based on the lock type.
    Returns a tuple (start, end) for the lock region.
    """
    if not content:
        return (0, 1)

    position = max(0, min(len(content) - 1, position))

    if lock_type == LockType.CHARACTER:
        return (position, position + 1)

    if lock_type == LockType.WORD:
        start = position
        while start > 0 and content[start - 1].isalnum():
            start -= 1
        end = position
        while end < len(content) and content[end].isalnum():
            end += 1
        return (start, end)

    if lock_type == LockType.LINE:
        start = content.rfind("\n", 0, position) + 1
        end = content.find("\n", position)
        end = end if end != -1 else len(content)
        return (start, end)

    return (position, position + 1)


def transform_position(pos, change_type, change_start, change_end, content_length):
    """
    Operational transformation for positions based on a change
    Adjusts a position after a change has been applied
    """
    if change_type == "INSERT":
        if pos >= change_start:
            return pos + content_length
    if change_type == "DELETE":
        if pos > change_end:
            return pos - (change_end - change_start)
        if pos > change_start:
            return change_start
    if change_type == "UPDATE":
        if pos > change_end:
            return pos + (content_length - (change_end - change_start))
        if pos > change_start:
            # If position was inside the update region, place it proportionally in the new content
            relative_pos = (pos - change_start) / (change_end - change_start)
            return change_start + int(content_length * relative_pos)

    return pos


def transform_change(change, prior_change):
    """
    Apply operational transformation to adjust a change based on a prior change
    """
    start, end = change["cord"]
    prior_start, prior_end = prior_change["cord"]
    prior_type = prior_change["type"]
    prior_content_len = len(prior_change.get("cont", ""))

    # Transform start and end positions
    new_start = transform_position(
        start, prior_type, prior_start, prior_end, prior_content_len
    )
    new_end = transform_position(
        end, prior_type, prior_start, prior_end, prior_content_len
    )

    # Update the change coordinates
    change["cord"] = [new_start, new_end]
    return change


def process_changes2(sid, doc_content):
    """Process all pending changes for a summary using operational transformation"""
    changes_processed = False
    all_changes = []

    # Gather all changes across all change_ids into a single queue
    for change_id, changes in list(doc_changes[sid].items()):
        for change_data in changes:
            change_obj = json.loads(change_data)

            # Extract client info
            client_id = change_obj.get("client_id", "unknown")
            user_id = change_obj.get("user_id", "unknown")

            # Process cursor/selection updates
            if "cursor" in change_obj:
                user_cursors[sid][client_id] = change_obj["cursor"]

            if "selection" in change_obj:
                user_selections[sid][client_id] = change_obj["selection"]

            # Process text changes
            for change in change_obj.get("changes", []):
                if not change:
                    continue

                # Add metadata to the change
                change["change_id"] = change_id
                change["client_id"] = client_id
                change["user_id"] = user_id
                change["timestamp"] = time.time()

                all_changes.append(change)

    # Clear the pending changes since we've copied them
    doc_changes[sid].clear()

    if not all_changes:
        return doc_content, False

    # Sort changes by timestamp if available
    all_changes.sort(key=lambda x: x.get("timestamp", 0))

    # Process all changes in order with conflict resolution
    for change in all_changes:
        start, end = change["cord"]
        change_type = change["type"]
        content = change.get("cont", "")
        change_id = change["change_id"]
        client_id = change["client_id"]
        user_id = change["user_id"]

        try:
            # Apply operational transformation if enabled
            if ENABLE_OPERATIONAL_TRANSFORM and change_history.get(sid, []):
                # Apply transformations based on recent history
                for prior_change in change_history[sid]:
                    change = transform_change(change, prior_change)

                # Get updated coordinates after transformation
                start, end = change["cord"]

            # Apply the change
            if change_type == "INSERT":
                doc_content = doc_content[:start] + content + doc_content[start:]
            elif change_type == "DELETE":
                doc_content = doc_content[:start] + doc_content[end:]
            elif change_type == "UPDATE":
                doc_content = doc_content[:start] + content + doc_content[end:]
            import copy

            # Record in history
            change_copy = copy.deepcopy(change)
            change_history[sid].append(change_copy)

            # Limit history size
            if len(change_history[sid]) > MAX_HISTORY_LENGTH:
                change_history[sid] = change_history[sid][-MAX_HISTORY_LENGTH:]

            # Update all user cursors and selections based on this change
            update_cursors_and_selections(
                sid, client_id, change_type, start, end, len(content)
            )

            changes_processed = True
            print(
                f"Applied change type {change_type} at position {start}-{end} for change ID {change_id} from user {user_id}"
            )

        except Exception as e:
            print(f"Error applying change: {e}")

    return doc_content, changes_processed


def update_cursors_and_selections(
    sid, originating_client_id, change_type, start, end, content_length
):
    """
    Update all users' cursors and selections based on a change that was just applied
    This keeps everyone's cursor in a sensible position after text changes
    """
    # Skip the originating client as they'll update their own cursor
    for client_id in user_cursors.get(sid, {}):
        if client_id == originating_client_id:
            continue

        # Update cursor position
        if client_id in user_cursors[sid]:
            cursor_pos = user_cursors[sid][client_id]
            user_cursors[sid][client_id] = transform_position(
                cursor_pos, change_type, start, end, content_length
            )

    # Update selections
    for client_id in user_selections.get(sid, {}):
        if client_id == originating_client_id:
            continue

        if client_id in user_selections[sid]:
            sel_start, sel_end = user_selections[sid][client_id]

            # Transform both edges of the selection
            new_sel_start = transform_position(
                sel_start, change_type, start, end, content_length
            )
            new_sel_end = transform_position(
                sel_end, change_type, start, end, content_length
            )

            user_selections[sid][client_id] = [new_sel_start, new_sel_end]


def apply_change(doc_content, change):
    """Apply a single change to the document content"""
    start, end = change["cord"]
    change_type = change["type"]
    content = change.get("cont", "")

    if change_type == "INSERT":
        # Insert content at the specified position
        new_content = doc_content[:start] + content + doc_content[start:]
        offset = len(content)
    elif change_type == "DELETE":
        # Remove content between start and end
        new_content = doc_content[:start] + doc_content[end:]
        offset = start - end
    else:  # UPDATE
        # Replace content between start and end
        new_content = doc_content[:start] + content + doc_content[end:]
        offset = len(content) - (end - start)

    return new_content, offset, change_type, start, end


def send_updates_to_users(sid, doc_content):
    """Send document updates to all connected users including cursor positions"""
    # Implementation depends on the websocket/communication framework
    print("Sockets: ", ids_per_summary_id[sid])
    for client_id in ids_per_summary_id.get(sid, set()):
        try:
            # Create a snapshot of all other users' cursors and selections
            other_cursors = {
                cid: pos
                for cid, pos in user_cursors.get(sid, {}).items()
                if cid != client_id
            }
            other_selections = {
                cid: sel
                for cid, sel in user_selections.get(sid, {}).items()
                if cid != client_id
            }

            # Get recent changes for this document
            recent_changes = change_history.get(sid, [])[-5:]  # Last 5 changes

            # Assume we have a send_message function that sends to specific clients
            sock = {v: k for k, v in id_per_sock.items()}.get(client_id, None)
            net = net_per_sock.get(sock)
            if net is None:
                print(f"No network manager found for client {client_id}")
                continue
                # base64.b64encode(
                #     json.dumps({"doc_content": doc_content}).encode()
                # ).decode()
            js = json.dumps(
                {
                    "type": "document_update",
                    "summary_id": sid,
                    "doc_content": doc_content,
                    "cursors": other_cursors,
                    "selections": other_selections,
                    "recent_changes": recent_changes,
                }
            )
            print("Sending: ", js)
            net.send_message(
                net.build_message(
                    "TAKEUPDATE",
                    [base64.b64encode(js.encode()).decode()],
                )
            )
            # print("Final state: \n", doc_content)
        except Exception as e:
            print(f"Error sending update to client {client_id}: {e}")


def summary_thread(sid, db_manager):
    """
    Main thread function that processes document changes for a given summary ID
    """
    doc_content = ""
    try:
        sid = int(sid)
        print(f"Starting summary thread for: {sid}")

        # Initialize document content from database
        with lock_per_doc[sid]:  # doc_changes_lock:
            doc = db_manager.get_summary(sid)
            doc_content = doc.content if doc and doc.content else ""
            if sid not in user_cursors:
                user_cursors[sid] = {}
            if sid not in user_selections:
                user_selections[sid] = {}
            if sid not in change_history:
                change_history[sid] = []
        print("Entering the processing loop")

        # Continue as long as clients are connected to this summary
        while ids_per_summary_id[sid]:
            changes_found = False
            with lock_per_doc[sid]:
                if sid in doc_changes and doc_changes[sid]:
                    changes_found = True
            if not changes_found:
                time.sleep(0.5)
                continue
            with lock_per_doc[sid]:
                if sid not in doc_changes or not doc_changes[sid]:
                    continue
                doc_content, changes_processed = process_changes2(sid, doc_content)
                if changes_processed:
                    print("Changes processed successfully")
            if changes_processed:
                send_updates_to_users(sid, doc_content)
                print("All users updated successfully")
            else:
                print("NO updated")
        return

    except Exception as e:
        print(f"Error in summary thread: {e}")
        import traceback

        traceback.print_exc()

        # Attempt to restart the thread on error
        summary_thread(sid, db_manager)

    finally:
        print(f"Summary thread terminated for summary ID: {sid}")
        # Save final document state before exiting
        try:
            db_manager.save_summary(sid, doc_content)
            print(f"Final document state saved for summary {sid}")
        except Exception as e:
            print(f"Failed to save final state: {e}")


def spawn_summary_thread(summ, uid, net, sid):
    global threads
    db_manager = DbManager()
    db_manager.connect_to_db(
        {
            "host": os.getenv("DB_HOST"),
            "user": os.getenv("DB_USERNAME"),
            "password": (os.getenv("DB_PASSWORD")),
            "database": os.getenv("DB_NAME"),
            "port": os.getenv("DB_PORT"),
        }
    )
    lock_per_doc[sid] = threading.Lock()
    thread = Thread(target=summary_thread, args=(sid, db_manager))
    thread.start()
    # thread.join()
    threads.append(thread)


def main(sock, crypt, t1):
    sock.listen(5)
    global threads
    threads = []
    while True:
        t2 = time.time()
        print("Starting up time: ", t2 - t1)
        print("Listening....")
        client_sock, addr = sock.accept()
        print(f"Connection from {addr}")
        # lock_per_sock[client_sock] = threading.Lock()
        crypt = cryptManager.CryptManager(rsa_key)
        thread = Thread(target=thread_main, args=(client_sock, addr, crypt))
        thread.start()
        threads.append(thread)
    for th in threads:
        th.join()


if __name__ == "__main__":
    print("Done importing")
    t1 = time.time()
    # read a .env file
    dotenv.load_dotenv()
    if USE_MYSQL:
        print("Using mysql")
    else:
        print("Using sqlite")
    if USE_MYSQL and not all(
        [
            os.getenv("DB_PASSWORD"),
            os.getenv("DB_USERNAME"),
            os.getenv("DB_HOST"),
            os.getenv("DB_PORT"),
            os.getenv("DB_NAME"),
        ]
    ):
        print("make sure all env variables are defined.")
        sys.exit()
    elif not USE_MYSQL and not os.path.isfile("dbconved.db"):
        print("Create the db")
        sys.exit()

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

    main(sock, rsa_key, t1)
