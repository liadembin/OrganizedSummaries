# Standard library imports first
import base64
import datetime
import difflib
import json
import os
import pickle
import threading
import time
import traceback
import unicodedata

# Third-party imports
import pdfkit
import wx
import wx.adv
import wx.html2

# First-party/local imports
from EventDiag import EventsDialog
from FontDiag import FontSelectorDialog
from GraphDial import GraphDialog
from HistoricList import HistoricListFrame
from networkManager import NetworkManager
from SummaryCarousell import SummaryCarousel


class MainFrame(wx.Frame):
    """Main application window for the document editor with HTML preview."""

    def __init__(self, net: NetworkManager, username):
        """Initialize the main frame.

        Args:
            net: NetworkManager instance for network communication
            username: Current user's username
        """
        super().__init__(None, title="App Dashboard", size=(800, 600))
        self.username = username
        # Initialize threading components
        self.sock_lock = threading.Lock()
        self.update_lock = threading.Lock()
        self.is_processing = threading.Event()

        # Initialize timers
        self.update_timer = wx.Timer(self)
        self.update_enable_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_doc, self.update_timer)
        # self.Bind(wx.EVT_TIMER, self.enable_listen, self.update_enable_timer)

        # Network and user setup
        net.set_lock(self.sock_lock)
        self.net = net
        self.username = username

        # Initialize state variables
        self.html_content = ""
        self.awaiting_update = False
        self.prev_content = ""
        self.last_char = " "
        self.last_update_time = 0
        self.UPDATE_THROTTLE_INTERVAL = 0.0
        self.cnt = 0
        self.historic = False
        self.picked_time = None

        # Initialize UI components
        self.carousel = None
        self.events_dialog = None

        # Set default font info
        self.current_font = {
            "name": "Arial",  # Changed from "Blackadder ITC" to more common font
            "url": None,
            "from_url": False,
        }
        self.username_label = None
        self.editor_panel = None
        self.editor: wx.TextCtrl | None = None
        self.html_panel = None
        self.html_window = None

        # Handler and dialog attributes
        self.handlers = {}
        self.dialog = None

        # Event-related attributes
        self.event_title = ""
        self.event_date = None
        self.event_time = None
        self.formatted_date = ""
        self.formatted_time = ""
        self.datetime_str = ""
        # Create UI
        self._create_ui()

        # Start listening thread
        self.listening_thread = threading.Thread(
            target=self.listen_for_changes, args=(self,), daemon=True
        )
        self.listening_thread.start()

        # Initialize HTML view
        self.update_html_view()

    def _create_ui(self):
        """Create the user interface components"""
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Create top controls
        hbox_top = self._create_top_controls(panel)
        vbox.Add(hbox_top, flag=wx.EXPAND | wx.ALL, border=10)

        # Create main content area
        self.splitter = self._create_main_content(panel)
        vbox.Add(self.splitter, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Create bottom controls
        hbox_bottom = self._create_bottom_controls(panel)
        vbox.Add(hbox_bottom, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10)

        panel.SetSizer(vbox)

    def _create_top_controls(self, panel):
        """Create the top control buttons"""
        hbox_top = wx.BoxSizer(wx.HORIZONTAL)

        # Username label
        self.username_label = wx.StaticText(panel, label=f"Username: {self.username}")
        hbox_top.Add(
            self.username_label,
            proportion=1,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=5,
        )

        # Button definitions with their event handlers
        buttons = [
            ("Share", self.share_summary),
            # ("See Linked", None),
            ("Browse Summaries", self.on_browse_data),
            ("Font Options", self.on_font_selector),
            ("See graph", self.on_graph),
            ("See History", self.on_historic),
            ("View Events", self.on_view_events),
        ]

        for label, handler in buttons:
            button = wx.Button(panel, label=label)
            if handler:
                button.Bind(wx.EVT_BUTTON, handler)
            hbox_top.Add(button, flag=wx.ALL, border=5)

        return hbox_top

    def _create_main_content(self, panel):
        """Create the main content area with editor and HTML view"""
        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)

        # Create editor panel
        self.editor_panel = wx.Panel(splitter)
        editor_sizer = wx.BoxSizer(wx.VERTICAL)

        self.editor = wx.TextCtrl(self.editor_panel, style=wx.TE_MULTILINE)
        self.editor.Bind(wx.EVT_TEXT, self.on_text_input)
        self.editor.Bind(wx.EVT_CHAR, self.on_char)

        # Set font
        font = wx.Font(
            12,
            wx.FONTFAMILY_DEFAULT,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL,
            False,
            self.current_font["name"],
        )
        self.editor.SetFont(font)

        refresh_button = wx.Button(self.editor_panel, label="Refresh HTML View")
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_html)

        editor_sizer.Add(self.editor, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        editor_sizer.Add(refresh_button, flag=wx.ALL, border=5)
        self.editor_panel.SetSizer(editor_sizer)

        # Create HTML panel
        self.html_panel = wx.Panel(splitter)
        html_sizer = wx.BoxSizer(wx.VERTICAL)
        self.html_window = wx.html2.WebView.New(self.html_panel)
        self.html_window.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self.on_link_clicked)
        html_sizer.Add(
            self.html_window, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
        )
        self.html_panel.SetSizer(html_sizer)

        # Set up splitter
        splitter.SplitVertically(self.editor_panel, self.html_panel)
        splitter.SetSashPosition(400)

        return splitter

    def _create_bottom_controls(self, panel):
        """Create the bottom control buttons"""
        hbox_bottom = wx.BoxSizer(wx.HORIZONTAL)

        buttons = [
            ("Export", self.show_export_menu),
            ("Import", self.show_import_menu),
            ("Summarize with LLM", self.on_summarize),
            ("Save", self.on_save),
        ]

        for label, handler in buttons:
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            hbox_bottom.Add(button, flag=wx.ALL, border=5)

        return hbox_bottom

    def on_graph(self, _):
        # print("Getting graph")
        if self.historic:
            self.net.send_message(
                self.net.build_message("HISTORICGRAPH", [str(self.picked_time)])
            )
            return
        self.net.send_message(self.net.build_message("GETGRAPH", []))

    def on_historic(self, _):
        self.net.send_message(self.net.build_message("GETHISTORICLIST", []))

    def handle_error(self, _, explaination, net):
        # wx.MessageBox(f"Error: {explaination}", "Error", wx.OK | wx.ICON_ERROR)
        wx.CallAfter(
            wx.MessageBox, f"Error: {explaination}", "Error", wx.OK | wx.ICON_ERROR
        )

    def handle_take_summaries(self, _, *params, net):
        summaries = []
        for summary in params:
            summ = pickle.loads(base64.b64decode(summary))
            summaries.append(summ)

        def show_summaries():
            if not summaries:
                wx.MessageBox(
                    "No summaries found.", "Info", wx.OK | wx.ICON_INFORMATION
                )
                return

            # Show carousel
            self.carousel = SummaryCarousel(summaries, self.net, self)
            self.carousel.ShowModal()
            self.carousel.Destroy()
            # print("Removed caroussle")

        wx.CallAfter(show_summaries)

    def handle_take_events(self, _, *params, net):
        events = []
        for event_data in params:
            event = pickle.loads(base64.b64decode(event_data))
            events.append(event)

        def show_events():
            if not events:
                wx.MessageBox("No events found.", "Info", wx.OK | wx.ICON_INFORMATION)
                return
            if self.events_dialog:
                self.events_dialog.Destroy()

            # Show events dialog
            self.events_dialog = EventsDialog(events, self, self.net, debug=True)
            self.events_dialog.ShowModal()
            # self.events_dialog.Destroy()
            # self.events_dialog = None

        wx.CallAfter(show_events)

    def handle_event_success(self, *params, net):
        wx.CallAfter(
            wx.MessageBox,
            f"Event '{self.event_title}' on {self.formatted_date} at {self.formatted_time} added.",
            "Success",
            wx.OK | wx.ICON_INFORMATION,
        )
        if not self.dialog:
            return
        wx.CallAfter(self.dialog.Destroy)

    def save_handlers(self, *params, net):
        print("Save, response: ", params)

    def on_file_content(self, *params, net):
        def update_editor():
            assert self.editor is not None
            self.editor.AppendText("~".join(params[1:]))
            self.update_html_view()

        wx.CallAfter(update_editor)

    def handle_graph(self, _, *params, net):
        """Handle graph data received from server"""
        if not params:
            wx.CallAfter(
                wx.MessageBox, "No graph data received", "Error", wx.OK | wx.ICON_ERROR
            )
            return

        try:
            # Deserialize the graph data
            graph_data = pickle.loads(base64.b64decode(params[0]))

            # Make sure we display something even if the list is empty
            if not graph_data:
                wx.CallAfter(
                    wx.MessageBox,
                    "No summaries found in the graph. Try creating or sharing more summaries.",
                    "Empty Graph",
                    wx.OK | wx.ICON_INFORMATION,
                )
                return

            def show_graph():
                # Create and show the graph dialog
                graph_dialog = GraphDialog(self, graph_data, self.net)
                if graph_dialog.ShowModal() == wx.ID_OK:
                    # If user selected a node and closed with "View", content is already requested
                    pass
                graph_dialog.Destroy()

            wx.CallAfter(show_graph)

        except Exception as e:
            wx.CallAfter(
                wx.MessageBox,
                f"Error processing graph data: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def on_summary_recived(self, _, *params, net):
        def update_summary():
            summ = params[0]
            assert self.editor is not None
            start, end = self.editor.GetSelection()
            self.editor.Replace(start, end, summ)
            self.update_html_view()

        wx.CallAfter(update_summary)

    def handle_gcal(self, _, *params, net):
        if not self.events_dialog:
            print("ERRROR!")
            return
        print("GOT A EVENTS LIST")
        self.events_dialog.on_gcal_events(self, params, net=net)

    def listen_for_changes(self, *_):
        """Optimized listening thread with better error handling"""
        self.handlers = {
            "ERROR": self.handle_error,
            "TAKESUMMARIES": self.handle_take_summaries,
            "SAVE_SUCCESS": self.save_handlers,
            "FILECONTENT": self.on_file_content,
            "SUMMARY": self.on_summary_recived,
            "TAKEEVENTS": self.handle_take_events,
            "INFO": self.handle_info,
            "TAKEUPDATE": self.take_update,
            "TAKEUPDATE2": self.take_update,
            "SHARE_SUCCESS": lambda a, *params, net: wx.CallAfter(
                wx.MessageBox,
                f"Summary shared with {params[0]}",
                "Success",
                wx.OK | wx.ICON_INFORMATION,
            ),
            "TAKEHIST": self.handle_take_hist,
            "TAKESUMMARY": self.handle_recived_summary,
            "TAKEGRAPH": self.handle_graph,
            "TAKESUMMARYLINK": self.handle_take_link,
            "HISTORICLIST": self.get_historic_list,
            "GCAL_EVENTS": self.handle_gcal,
        }

        self.net.add_handlers(self.handlers)
        self.net.sock.settimeout(0.5)
        while True:
            try:
                # Non-blocking receive with better error managementserver
                found_any = self.net.recv_handle_args(self)

                if not found_any:
                    time.sleep(0.1)  # Reduced sleep time

            except Exception as _:
                # print(f"Listening Thread Error: {e}")

                traceback.print_exc()
                time.sleep(1)  # Prevent tight error loop

    def share_summary(self, _):
        # print("Sharing summary")
        dialog = wx.TextEntryDialog(
            None, "Enter the username to share with:", "Share Summary"
        )
        if dialog.ShowModal() == wx.ID_OK:
            username = dialog.GetValue()
            # print("Sharing with: ", username)
            self.net.send_message(self.net.build_message("SHARESUMMARY", [username]))

        else:
            # print("Share canceled by user.")
            dialog.Destroy()

    def show_upcoming_events(self, events):
        # Ensure all event dates are datetime.date
        for event in events:
            if isinstance(event["event_date"], datetime.datetime):
                # Convert datetime to date
                event["event_date"] = event["event_date"].date()

        # Sort events by proximity to current date
        sorted_events = sorted(
            events, key=lambda x: abs((x["event_date"] - datetime.date.today()).days)
        )

        # Create dialog
        dialog = wx.Dialog(self, title="Upcoming Events", size=(500, 400))
        panel = wx.Panel(dialog)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Events list
        events_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        events_list.InsertColumn(0, "Title", width=200)
        events_list.InsertColumn(1, "Date", width=150)
        events_list.InsertColumn(2, "Days Away", width=120)

        for event in sorted_events:
            event_date = event["event_date"]  # Already converted to date
            days_away = (event_date - datetime.date.today()).days

            # Formatting label
            if days_away < 0:
                days_label = f"Happened {-days_away} days ago"
                color = wx.Colour(255, 0, 0)  # Red for past events
            elif days_away == 0:
                days_label = "Today"
                color = wx.Colour(0, 0, 255)  # Blue for today
            else:
                days_label = f"In {days_away} days"
                color = wx.Colour(0, 128, 0)  # Green for future events

            index = events_list.InsertItem(0, event["event_title"])
            events_list.SetItem(
                index, 1, event_date.strftime("%Y-%m-%d")
            )  # Convert date to string
            events_list.SetItem(index, 2, days_label)

            # Set text color
            for _ in range(3):
                events_list.SetItemTextColour(index, color)

        vbox.Add(events_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Continue button
        continue_button = wx.Button(panel, label="Continue")
        continue_button.Bind(wx.EVT_BUTTON, lambda _: dialog.EndModal(wx.ID_OK))
        vbox.Add(continue_button, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(vbox)

        dialog.ShowModal()

    def is_update_throttled(self):
        """Check if an update should be throttled based on time since last update"""
        current_time = time.time()
        if current_time - self.last_update_time < self.UPDATE_THROTTLE_INTERVAL:
            return True
        self.last_update_time = current_time
        return False

    def normalize_text(self, text):
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)  # Normalize unicode
        text = text.replace("\r\n", "\n").replace("\r", "").rstrip()
        return text

    def show_error_message(self, message, title="Error"):
        """Show error message in a thread-safe way"""
        wx.CallAfter(wx.MessageBox, message, title, wx.OK | wx.ICON_ERROR)

    def show_info_message(self, message, title="Info"):
        """Show info message in a thread-safe way"""
        wx.CallAfter(wx.MessageBox, message, title, wx.OK | wx.ICON_INFORMATION)

    def show_success_message(self, message, title="Success"):
        """Show success message in a thread-safe way"""
        wx.CallAfter(wx.MessageBox, message, title, wx.OK | wx.ICON_INFORMATION)

    def update_doc(self, _):
        """Update document with improved error handling and logic"""
        # Check various conditions that should prevent update
        if self.is_processing.is_set():
            print("Currently processing, skipping update")
            return

        if self.is_update_throttled():
            print("Update throttled")
            return

        # Reset counter
        self.cnt = 0

        try:
            with self.update_lock:
                old_text = self.normalize_text(self.prev_content)
                assert self.editor is not None
                new_text = self.normalize_text(self.editor.GetValue())

                # Detect if content has actually changed
                if old_text == new_text:
                    print("No changes detected")
                    self.send_changes([], False)
                    return
                # Calculate changes using diff
                changes = self._calculate_text_changes(old_text, new_text)

                # Send update if there are meaningful changes
                self.send_changes(changes, new_text)
                return
        except Exception as e:
            print(f"Error in update_doc: {e}")
            traceback.print_exc()
            return

    def _calculate_text_changes(self, old_text, new_text):
        """Calculate changes between old and new text"""
        matcher = difflib.SequenceMatcher(None, old_text, new_text)
        changes = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue

            change_type = {
                "replace": "UPDATE",
                "delete": "DELETE",
                "insert": "INSERT",
            }.get(tag, tag)

            content = new_text[j1:j2] if tag in ["replace", "insert"] else ""

            # Skip empty changes that aren't deletions
            if not content and tag != "delete":
                continue

            changes.append({"cord": [i1, i2], "type": change_type, "cont": content})

        return changes

    def send_changes(self, changes, new_text):
        # print("Found these changes: ", changes)
        payload = json.dumps({"changes": changes})
        try:
            self.net.send_message(self.net.build_message("UPDATEDOC", [payload]))
            if new_text:
                self.prev_content = new_text
            self.awaiting_update = True
        except Exception as _:
            # print(f"Error sending update: {e}")
            traceback.print_exc()

    def handle_info(self, _, *params, net):
        # print("Recived info: ", params)
        wx.CallAfter(
            wx.MessageBox,
            f"Info: {params[0]}",
            "Info",
            wx.OK | wx.ICON_INFORMATION,
        )

    def get_historic_list(self, _, pickled, net):
        historic = pickle.loads(base64.b64decode(pickled))
        print("Historic: ", historic)
        # list of timestamps formated like this(str):  timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # first paese the list, then sort
        parsed = [
            datetime.datetime.strptime(stamp, "%Y%m%d%H%M%S") for stamp in historic
        ]
        sorte = sorted(parsed)
        print(sorte)

        def create_frame(*_):
            frame = HistoricListFrame(
                self, "Historic List", sorte, self.on_historic_pick
            )
            frame.Show()
            # print("Showing historic list")

        wx.CallAfter(create_frame)

    def on_historic_pick(self, selected_datetime):
        print("Picked: ", selected_datetime)
        self.picked_time = selected_datetime
        self.load_historic(selected_datetime)

    def load_historic(self, selected_datetime):
        timestamp = selected_datetime.strftime("%Y%m%d%H%M%S")
        print("Loading: ", timestamp)
        self.net.send_message(self.net.build_message("LOADHISTORIC", [timestamp]))
        self.historic = True
        # print("Sent load historic message")

    def handle_take_link(self, _, link, net):
        # print("Requesting link with sid: ", link)
        self.net.send_message(self.net.build_message("GETSUMMARY", [link]))

    def take_update(self, _, *params, net):
        """Enhanced server update handler with input freezing"""
        try:
            # Indicate server update is in progress
            print("Update params: ")
            self.is_processing.set()

            # Decode update
            jsoned = json.loads(base64.b64decode(params[0]).decode())
            print("Unjsoned; ")
            print(jsoned)

            def update_ui():
                try:
                    # Disable editor during update
                    print("Disabling editor")
                    assert self.editor is not None
                    self.editor.Disable()

                    # Update content
                    new_content = jsoned["doc_content"]
                    print("Seting value")
                    self.editor.SetValue(new_content)
                    print("Set value")
                    self.prev_content = new_content
                    self.update_html_view()
                    print("UPDATED THE FUCKING UI")
                    # clear the file first

                    # with open("cont.txt","w") as f:
                    #     f.write(new_content)
                    # Re-enable editor after short delay
                    # wx.CallLater(1000, self.editor.Enable)
                    self.editor.Enable()
                    self.is_processing.clear()
                    # Clear update flags
                    self.awaiting_update = False
                    # self.is_processing.clear()

                except Exception as e:
                    print(f"UI Update Error: {e}")
                    assert self.editor is not None
                    self.editor.Enable()
                    self.is_processing.clear()
                    raise e

            # Ensure UI update happens on main thread
            wx.CallAfter(update_ui)

        except Exception as _:
            # print(f"Update Processing Error: {e}")
            traceback.print_exc()
            self.is_processing.clear()

    def on_font_selector(self, _):
        """Handle font selection with improved error handling"""
        dialog = FontSelectorDialog(self, self.net)

        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy()
            return

        try:
            font_name = dialog.selected_font
            from_url = dialog.from_url
            font_url = dialog.url_input.GetValue() if from_url else None
            font_path = dialog.custom_font_path if from_url else None

            # Store the selected font information
            self.current_font = {
                "name": font_name,
                "url": font_url,
                "from_url": from_url,
            }

            # Apply the font to the editor
            self._apply_font_to_editor(font_name)

            # Handle custom font upload if needed
            if from_url and font_path:
                print("Would upload font to server")  # Placeholder for server upload

            # Update the HTML view with the new font
            self.update_html_view()

        except Exception as e:
            print(f"Error in font selection: {e}")
            self.show_error_message(f"Error applying font: {str(e)}")
        finally:
            dialog.Destroy()

    def _apply_font_to_editor(self, font_name):
        """Apply font to editor with fallback handling"""
        try:
            font = wx.Font(
                12,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                False,
                font_name,
            )
            assert self.editor is not None
            self.editor.SetFont(font)
        except Exception as e:
            print(f"Error setting font {font_name}: {e}")
            # Fallback to Arial
            fallback_font = wx.Font(
                12,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                False,
                "Arial",
            )
            assert self.editor is not None
            self.editor.SetFont(fallback_font)
            self.current_font["name"] = "Arial"

    def on_char(self, event):
        keycode = event.GetKeyCode()
        if 32 <= keycode <= 126:  # Printable ASCII
            self.last_char = chr(keycode)
            # print("Current char:", self.last_char)
        event.Skip()

    def on_text_input(self, _):
        # Store current position and content
        assert self.editor is not None
        current_pos = self.editor.GetInsertionPoint()
        current_content = self.editor.GetValue()
        # Continue with existing functionality

        text_pos = current_pos - 1
        if text_pos < 2:
            self.update_html_view()
            return
        cont = current_content

        # Adjust for newlines
        text_pos -= 1 * cont.count("\n", 0, text_pos)
        if cont[text_pos] != "\n":
            # print("Re rendering")
            self.update_html_view()
            return
        prev_back_n = cont.rfind("\n", 0, text_pos - 1)
        if prev_back_n == -1:
            prev_back_n = 0
        # line = cont[prev_back_n:text_pos].strip()

        # if line.startswith("###"):
        # print("Found special line: ", line)
        # print("That's the special!!!!!!!!!!!")
        # print("Re rendering")
        self.update_html_view()

    def on_refresh_html(self, _):
        self.update_html_view()

    def update_html_view(self):
        """Convert text content to HTML and update the HTML window"""
        assert self.editor is not None
        content = self.editor.GetValue()
        html = self.convert_text_to_html(content)
        self.html_content = html
        # self.html_window.RunScript(f"document.innerHTML = '{html}'")
        assert self.html_window is not None
        self.html_window.SetPage(html, "about:blank")

    def html_to_text(self, content):
        """Convert HTML back to text with special markup

        This function reverses the convert_text_to_html function by extracting
        text and special markup from HTML content.
        """
        import re
        from html import unescape

        # Initialize result
        result = []

        # Extract body content (ignore head, styles, etc.)
        body_match = re.search(r"<body>(.*?)</body>", content, re.DOTALL)
        if not body_match:
            return ""  # No body found

        body_content = body_match.group(1)

        # Process tables
        in_table = False

        # Use a simple state machine to process the content
        i = 0
        content_length = len(body_content)

        while i < content_length:
            # Check for table start
            if "<table>" in body_content[i : i + 10].lower():
                in_table = True
                result.append("###table")
                i += 7  # Length of <table>
                continue

            # Check for table end
            if in_table and "</table>" in body_content[i : i + 10].lower():
                in_table = False
                result.append("###endtable")
                i += 8  # Length of </table>
                continue

            # Process table rows
            if in_table and "<tr>" in body_content[i : i + 5].lower():
                row_cells = []
                i += 4  # Skip <tr>

                # Extract cells from this row
                while (
                    i < content_length
                    and "</tr>" not in body_content[i : i + 6].lower()
                ):
                    if "<td>" in body_content[i : i + 5].lower():
                        i += 4  # Skip <td>
                        cell_content = ""
                        while (
                            i < content_length
                            and "</td>" not in body_content[i : i + 6].lower()
                        ):
                            cell_content += body_content[i]
                            i += 1
                        i += 5  # Skip </td>
                        row_cells.append(cell_content.strip())
                    else:
                        i += 1

                # Join cells with pipe symbol
                if row_cells:
                    result.append(" | ".join(row_cells))

                # Skip past </tr>
                while (
                    i < content_length
                    and "</tr>" not in body_content[i : i + 6].lower()
                ):
                    i += 1
                i += 5  # Skip </tr>
                continue

            # Process links
            if '<a href="internal:' in body_content[i : i + 20].lower():
                link_start = i + 16  # Position after 'internal:'
                link_end = body_content.find('">', i)
                if link_end != -1:
                    link_text = body_content[link_start:link_end]
                    result.append(f"###link {link_text}")
                    i = body_content.find("</a>", link_end) + 4
                    continue

            # Process bold text
            if "<span class='bold'>" in body_content[i : i + 20].lower():
                result.append("###bold")
                i += 19  # Length of <span class='bold'>
                continue

            if "</span>" in body_content[i : i + 10].lower() and "###bold" in result:
                result.append("###unbold")
                i += 7  # Length of </span>
                continue

            # Process paragraphs
            if "<p>" in body_content[i : i + 5].lower():
                i += 3  # Skip <p>
                para_content = ""
                while (
                    i < content_length and "</p>" not in body_content[i : i + 5].lower()
                ):
                    para_content += body_content[i]
                    i += 1
                i += 4  # Skip </p>

                # Reverse the &nbsp; replacement
                para_content = para_content.replace("&nbsp;", " ")

                # Unescape HTML entities
                para_content = unescape(para_content)

                result.append(para_content)
                continue

            # Move to next character if no patterns matched
            i += 1

        # Join all lines with newlines
        return "\n".join(result)

    def convert_text_to_html(self, content):
        """Convert text with special markup to HTML"""
        html = [
            "<!DOCTYPE html><html><head>",
            "<style>",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 4px solid #000; padding: 8px; }",
            "th { background-color: #f2f2f2; }",
            "a { color: blue; text-decoration: underline; cursor: pointer; }",
            ".bold { font-weight: bold; }",
        ]

        # Handle font setup - either from URL or system font
        if self.current_font["from_url"] and self.current_font["url"]:
            # For web fonts, use @font-face declaration
            font_url = self.current_font["url"]
            font_name = self.current_font["name"]
            # Remove any invalid characters from font name
            font_name = font_name.replace("|", "")

            html.append("@font-face {{")
            html.append(f"  font-family: '{font_name}';")
            html.append(f"  src: url('{font_url}');")
            html.append("}}")
            html.append(
                f"body {{ font-family: '{font_name}', sans-serif; margin: 20px; }}"
            )
        else:
            # For system fonts, just set the font-family
            font_name = self.current_font["name"].replace("|", "")  # .replace("@","")
            html.append(
                f"body {{ font-family: '{font_name}', sans-serif; margin: 20px; }}"
            )

        html.append("</style></head><body>")
        # print("Styling info: ", html)
        lines = content.split("\n")
        i = 0
        in_table = False
        table_html = []

        while i < len(lines):
            line = lines[i].strip()

            # Handle special commands
            if line.startswith("###"):
                cmd = line[3:].strip()

                if cmd.startswith("table"):
                    in_table = True
                    table_html = ["<table>"]
                    # Table header can be added here if needed

                elif cmd.startswith("endtable") and in_table:
                    in_table = False
                    table_html.append("</table>")
                    html.append("".join(table_html))

                elif cmd.startswith("link"):
                    # Extract link target
                    link_text = line[7:].strip()  # preserve case
                    html.append(f'<a href="internal:{link_text}">{link_text}</a>')

                elif cmd.startswith("bold"):
                    html.append("<span class='bold'>")

                elif cmd.startswith("unbold"):
                    html.append("</span>")

                # Other commands can be handled similarly

            else:
                # Regular text - handle paragraphs
                if in_table:
                    # Add to table if we're in a table context
                    # This is simplified - you'd need more logic for proper tables
                    cells = line.split("|")
                    if len(cells) > 1:
                        table_html.append("<tr>")
                        for cell in cells:
                            table_html.append(f"<td>{cell.strip()}</td>")
                        table_html.append("</tr>")
                else:
                    # Regular paragraph
                    if line:
                        # Replace spaces with &nbsp; for preserving multiple spaces
                        formatted_line = line.replace("  ", " &nbsp;")
                        html.append(f"<p>{formatted_line}</p>")
                # if not in_table and line == "":
                #     html.append("<br>")
            # html += "<br>"
            i += 1

        html.append("</body></html>")
        # print("".join(html))
        # #print(html)
        return "".join(html)

    def on_link_clicked(self, event):
        link = event.GetURL()
        if link.startswith("data:"):
            return
        # print(f"Link clicked: {link}")
        if link.startswith("internal:"):
            name = link[len("internal:") :]
            self.net.send_message(self.net.build_message("GETSUMMARYLINK", [name]))
            # print("Sent get summary message")
            cont = base64.b64decode(
                self.net.get_message_params(self.net.recv_message())[0]
            ).decode()
            # print("THE CONTENT: ", cont)
            assert self.editor is not None
            self.editor.SetValue(cont)
            self.prev_content = cont
            self.update_html_view()

        # if link.startswith("internal:"):
        #     target = link[9:]  # Remove 'internal:' prefix
        #     wx.MessageBox(
        #         f"Navigating to internal section: {target}",
        #         "Link Clicked",
        #         wx.OK | wx.ICON_INFORMATION,
        #     )
        #     event.Veto()  # Prevent navigation if needed
        # else:
        #     # Open external links in the default browser
        #     wx.LaunchDefaultBrowser(link)

    def on_summarize(self, _):
        assert self.editor is not None
        selected = self.editor.GetStringSelection()
        # print("Currently selecting : ", selected)
        self.net.send_message(self.net.build_message("SUMMARIZE", [selected]))

    def show_export_menu(self, _):
        # print("Showing export menu")
        menu = wx.Menu()
        for label, handler in [
            ("Markdown", self.export_as_markdown),
            ("PDF", self.export_as_pdf),
            ("HTML", self.export_as_html),
            ("TXT", self.export_as_txt),
        ]:
            item = wx.MenuItem(menu, wx.ID_ANY, label)
            menu.Bind(wx.EVT_MENU, handler, id=item.GetId())
            menu.Append(item)
        self.PopupMenu(menu)

    def show_import_menu(self, _):
        # print("Showing import menu")
        menu = wx.Menu()
        for label, handler in [
            ("Markdown", self.import_from_markdown),
            # ("PDF", self.import_from_pdf),
            ("HTML", self.import_from_html),
            ("TXT", self.import_from_txt),
            ("Scan A File", self.import_from_file),
        ]:
            item = wx.MenuItem(menu, wx.ID_ANY, label)
            menu.Bind(wx.EVT_MENU, handler, id=item.GetId())
            menu.Append(item)
        self.PopupMenu(menu)

    def import_from_file(self, _):
        # Open a file dialog to select a File
        dialog = wx.FileDialog(
            self,
            message="Choose a file to import",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dialog.ShowModal() == wx.ID_CANCEL:
            return
        path = dialog.GetPath()
        self.net.send_file(path)
        self.net.send_message(
            self.net.build_message("GETFILECONTENT", [os.path.basename(path)])
        )

    def on_view_events(self, _):
        self.net.send_message(self.net.build_message("GETEVENTS", []))

    def on_add_event(self, _):
        dialog = wx.Dialog(self, title="Add New Event", size=(400, 300))
        panel = wx.Panel(dialog)

        # Vertical layout for the dialog
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title input
        title_label = wx.StaticText(panel, label="Event Title:")
        title_input = wx.TextCtrl(panel)
        vbox.Add(title_label, flag=wx.ALL, border=5)
        vbox.Add(title_input, flag=wx.EXPAND | wx.ALL, border=5)

        # Date input
        date_label = wx.StaticText(panel, label="Event Date:")
        date_picker = wx.adv.DatePickerCtrl(
            panel, style=wx.adv.DP_DEFAULT | wx.adv.DP_SHOWCENTURY
        )
        vbox.Add(date_label, flag=wx.ALL, border=5)
        vbox.Add(date_picker, flag=wx.EXPAND | wx.ALL, border=5)

        # Time input
        time_label = wx.StaticText(panel, label="Event Time:")
        time_picker = wx.adv.TimePickerCtrl(panel, style=wx.adv.TP_DEFAULT)
        vbox.Add(time_label, flag=wx.ALL, border=5)
        vbox.Add(time_picker, flag=wx.EXPAND | wx.ALL, border=5)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)

        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        vbox.Add(button_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(vbox)

        # Show the dialog and handle result
        if dialog.ShowModal() == wx.ID_OK:
            self.event_title = title_input.GetValue()
            self.event_date = date_picker.GetValue()
            self.event_time = time_picker.GetValue()

            # Validate inputs
            if not self.event_title:
                wx.MessageBox(
                    "Please enter an event title.", "Error", wx.OK | wx.ICON_ERROR
                )
                dialog.Destroy()
                return

            # Convert wx date and time to Python date and time
            self.formatted_date = self.event_date.FormatISODate()
            self.formatted_time = self.event_time.Format("%H:%M:%S")
            self.datetime_str = f"{self.formatted_date} {self.formatted_time}"

            self.net.send_message(
                self.net.build_message(
                    "ADDEVENT", [self.event_title, self.datetime_str]
                )
            )
            self.dialog = dialog
            # might be better to create the handler dynamically here, rather than have all state in the class

    def export_as_markdown(self, _):
        # print("Exporting as Markdown")
        self.export_file("md")

    def export_as_pdf(self, _):
        # print("Exporting as PDF")
        self.export_file("pdf")

    def export_as_html(self, _):
        # print("Exporting as HTML")
        # For HTML, we could directly use our HTML content
        self.export_file("html", use_html=True)

    def export_as_txt(self, _):
        # print("Exporting as TXT")
        self.export_file("txt")

    def export_file(self, ext, use_html=False):
        """Export file with improved error handling"""
        dialog = wx.FileDialog(
            self,
            message="Save file as ...",
            defaultDir=os.getcwd(),
            defaultFile=f"summary.{ext}",
            wildcard=f"{ext.upper()} files (*.{ext})|*.{ext}",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dialog.ShowModal() == wx.ID_CANCEL:
            dialog.Destroy()
            return

        path = dialog.GetPath()
        dialog.Destroy()

        try:
            if ext.lower() == "pdf":
                self._export_as_pdf(path)
                return
            formatted_content = self._format_content_for_export(ext)

            with open(path, "w", encoding="utf-8") as f:
                f.write(formatted_content)

            self.show_success_message(f"Summary saved to {path}", "Export Successful")
            return
        except Exception as e:
            print(f"Error exporting file: {e}")
            self.show_error_message(f"Error saving file: {str(e)}")
            return

    def _export_as_pdf(self, path):
        """Export content as PDF"""
        try:
            return pdfkit.from_string(self.html_content, path)
        except Exception as e:
            self.show_error_message(f"Error creating PDF: {str(e)}")
            return ""

    def _format_content_for_export(self, ext):
        """Format content based on export type"""
        if ext.lower() in ["html", "pdf"]:
            self.on_refresh_html(None)
            return self.html_content

        assert self.editor is not None
        return self.editor.GetValue()

    def import_from_markdown(self, _):
        # print("Importing from Markdown")
        file_text_content = self.get_file_content("md")
        if not file_text_content:
            return
        assert self.editor is not None
        self.editor.SetValue(file_text_content)
        self.update_html_view()

    def import_from_pdf(self, _):
        print("Importing from PDF")
        # Implementation would go here

    def import_from_html(self, _):
        # print("Importing from HTML")
        # Implementation would go here
        file_text_content = self.get_file_content("html")
        if not file_text_content:
            return
        # preform the reverse of convert_text_to_html
        assert self.editor is not None
        self.editor.SetValue(self.html_to_text(file_text_content))
        self.update_html_view()
        return

    def import_from_txt(self, _):
        # print("Importing from TXT")
        # Implementation would go here
        file_text_content = self.get_file_content("txt")
        if not file_text_content:
            return
        assert self.editor is not None
        self.editor.SetValue(file_text_content)
        self.update_html_view()

    def get_file_content(self, _):
        # Open a file dialog to select a File
        # return its text content for txt and md
        # returns its html for pdf and html
        dialog = wx.FileDialog(
            self,
            message="Choose a file to import",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dialog.ShowModal() == wx.ID_CANCEL:
            dialog.Destory()
            return b""

        path = dialog.GetPath()
        # if path.endswith(".pdf"):
        #     return self.get_pdf_content(path)
        dialog.Destroy()
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # def get_pdf_content(self, path):
    #     # convert pdf to html using pdfkit
    #     return pdfkit.
    def on_browse_data(self, _):
        wx.MessageBox(
            f"Browsing data for user: {self.username}",
            "Info",
            wx.OK | wx.ICON_INFORMATION,
        )
        self.net.send_message(self.net.build_message("GETSUMMARIES", []))
        msg = self.net.recv_message()
        code, params = self.net.get_message_code(msg), self.net.get_message_params(msg)
        if code.strip() == "ERROR":
            wx.MessageBox(f"Error: {params[0]}", "Error", wx.OK | wx.ICON_ERROR)
            return
        #
        summaries = []
        for summary in params:
            summ = pickle.loads(base64.b64decode(summary))
            summaries.append(summ)

        if not summaries:
            wx.MessageBox("No summaries found.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        # Show carousel
        carousel = SummaryCarousel(summaries, self.net, self)
        carousel.ShowModal()
        carousel.Destroy()

    def on_save(self, _):
        # print("Saving")

        # Prompt the user for a title
        dialog = wx.TextEntryDialog(
            None, "Enter a title for the summary:", "Save Summary"
        )
        if dialog.ShowModal() == wx.ID_OK:
            title = dialog.GetValue()
        else:
            # print("Save canceled by user.")
            dialog.Destroy()
            return  # Exit if the user cancels the input

        dialog.Destroy()

        # Build and send the save message with font information
        font_info = {
            "name": self.current_font["name"],
            "url": self.current_font["url"] if self.current_font["from_url"] else "",
        }

        # Convert font info to string
        font_info_str = f"{font_info['name']}|{font_info['url']}"

        # Build and send the save message
        assert self.editor is not None
        self.net.send_message(
            self.net.build_message(
                "SAVE", [title, self.editor.GetValue(), font_info_str]
            )
        )

    def handle_take_hist(self, _, *params, net):
        self.historic = True

        def process_summary():
            try:
                dic = pickle.loads(base64.b64decode(params[0]))
                cont = dic["data"].decode()
                dicty = {"font": dic["summ"].font}
                assert self.editor is not None
                self.editor.SetValue(cont)
                self.prev_content = cont
                dicty["font"] = dicty.get("font", "Arial")

                if dicty["font"] and dicty["font"].startswith("http"):
                    self.current_font = {
                        "name": dicty["font"],
                        "url": dicty["font"],
                        "from_url": True,
                    }
                else:
                    # Clean up the font name - remove any @ symbol or pipe characters
                    if dicty.get("font") is None:
                        clean_font_name = "Arial"

                    else:
                        clean_font_name = (
                            dicty.get("font", "Arial").replace("@", "").replace("|", "")
                        )
                    self.current_font = {
                        "name": clean_font_name if clean_font_name else "Arial",
                        "url": None,
                        "from_url": False,
                    }

                try:
                    font = wx.Font(
                        12,
                        wx.FONTFAMILY_DEFAULT,
                        wx.FONTSTYLE_NORMAL,
                        wx.FONTWEIGHT_NORMAL,
                        False,
                        self.current_font["name"],
                    )
                    self.editor.SetFont(font)
                except Exception as font_error:
                    print(f"Error setting font: {font_error}")
                    # Fallback to default font
                    default_font = wx.Font(
                        12,
                        wx.FONTFAMILY_DEFAULT,
                        wx.FONTSTYLE_NORMAL,
                        wx.FONTWEIGHT_NORMAL,
                        False,
                        "Arial",
                    )
                    self.editor.SetFont(default_font)

                print("Font info: ", self.current_font)
                self.update_timer.Stop()
                self.update_enable_timer.Stop()
                # if hasattr(self, "carousel") and self.carousel:
                #     self.carousel.Close()
                # self.update_timer.Start(3000)  # Check every 3 seconds
                # self.update_enable_timer.Start(3000)
            except Exception as _:
                # print("Error: ", e)
                traceback.print_exc()
                wx.MessageBox(
                    "Error: Could not retrieve summary content.",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
                self.Close()

        wx.CallAfter(process_summary)

    def handle_recived_summary(self, _, *params, net):
        self.historic = False

        def process_summary():
            assert self.editor is not None
            try:
                dic = pickle.loads(base64.b64decode(params[0]))
                cont = dic["data"].decode()
                dicty = {"font": dic["summ"].font}
                self.editor.SetValue(cont)
                self.prev_content = cont
                dicty["font"] = dicty.get("font", "Arial")

                if dicty["font"] and dicty["font"].startswith("http"):
                    self.current_font = {
                        "name": dicty["font"],
                        "url": dicty["font"],
                        "from_url": True,
                    }
                else:
                    # Clean up the font name - remove any @ symbol or pipe characters
                    if dicty.get("font") is None:
                        clean_font_name = "Arial"

                    else:
                        clean_font_name = (
                            dicty.get("font", "Arial").replace("@", "").replace("|", "")
                        )
                    self.current_font = {
                        "name": clean_font_name if clean_font_name else "Arial",
                        "url": None,
                        "from_url": False,
                    }

                try:
                    font = wx.Font(
                        12,
                        wx.FONTFAMILY_DEFAULT,
                        wx.FONTSTYLE_NORMAL,
                        wx.FONTWEIGHT_NORMAL,
                        False,
                        self.current_font["name"],
                    )
                    self.editor.SetFont(font)
                except Exception as font_error:
                    print(f"Error setting font: {font_error}")
                    # Fallback to default font
                    default_font = wx.Font(
                        12,
                        wx.FONTFAMILY_DEFAULT,
                        wx.FONTSTYLE_NORMAL,
                        wx.FONTWEIGHT_NORMAL,
                        False,
                        "Arial",
                    )
                    self.editor.SetFont(default_font)

                print("Font info: ", self.current_font)
                if hasattr(self, "carousel") and self.carousel:
                    self.carousel.Close()
                self.update_timer.Start(3000)  # Check every 3 seconds
                self.update_enable_timer.Start(3000)
            except Exception as _:
                # print("Error: ", e)
                traceback.print_exc()
                wx.MessageBox(
                    "Error: Could not retrieve summary content.",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
                self.Close()

        wx.CallAfter(process_summary)
