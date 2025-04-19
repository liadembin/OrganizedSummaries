import datetime
import wx
from networkManager import NetworkManager
import base64
import pickle
import os
import wx.html2
import wx.adv
import pdfkit
import time
import json
import difflib
import threading
import unicodedata
from GraphDial import GraphDialog
from EventDiag import EventsDialog
from FontDiag import FontSelectorDialog
from SummaryCarousell import SummaryCarousel
import traceback

class MainFrame(wx.Frame):
    def __init__(self, net: NetworkManager, username):
        super().__init__(None, title="App Dashboard", size=(800, 600))
        self.sock_lock = threading.Lock()
        self.listening_thread = threading.Thread(
            target=self.listen_for_changes, args=(self,), daemon=True
        )
        self.update_lock = threading.Lock()
        self.is_proccesing = threading.Event()
        # self.made_changes = []
        # Set up a timer to check for document changes
        self.update_timer = wx.Timer(self)
        self.update_enable_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_doc, self.update_timer)
        self.Bind(wx.EVT_TIMER, self.enable_listen, self.update_enable_timer)
        net.set_lock(self.sock_lock)
        self.net = net
        self.username = username
        self.listening_thread.start()
        self.html_content = ""  # To store HTML content
        self.awaiting_update = False
        # Main panel
        panel = wx.Panel(self)

        # Layout
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Top controls (username, share button, see linked button, browse data button)
        hbox_top = wx.BoxSizer(wx.HORIZONTAL)
        self.username_label = wx.StaticText(panel, label=f"Username: {username}")
        share_button = wx.Button(panel, label="Share")
        see_linked_button = wx.Button(panel, label="See Linked")
        browse_data_button = wx.Button(panel, label="Browse Summaries")
        font_button = wx.Button(panel, label="Font Options")
        font_button.Bind(wx.EVT_BUTTON, self.on_font_selector)
        save_button = wx.Button(panel, label="Save")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        graph_button = wx.Button(panel, label="See graph")
        hbox_top.Add(
            self.username_label,
            proportion=1,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=5,
        )
        hbox_top.Add(share_button, flag=wx.ALL, border=5)
        hbox_top.Add(see_linked_button, flag=wx.ALL, border=5)
        hbox_top.Add(browse_data_button, flag=wx.ALL, border=5)
        hbox_top.Add(font_button, flag=wx.ALL, border=5)
        hbox_top.Add(graph_button, flag=wx.ALL, border=5)
        graph_button.Bind(wx.EVT_BUTTON, self.on_graph)
        add_event_button = wx.Button(panel, label="Add Event")
        add_event_button.Bind(wx.EVT_BUTTON, self.on_add_event)
        hbox_top.Add(add_event_button, flag=wx.ALL, border=5)
        view_events_button = wx.Button(panel, label="View Events")
        view_events_button.Bind(wx.EVT_BUTTON, self.on_view_events)
        hbox_top.Add(view_events_button, flag=wx.ALL, border=5)
        vbox.Add(hbox_top, flag=wx.EXPAND | wx.ALL, border=10)

        # Split panel for editor and HTML view
        self.splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)

        # Text editor for input
        self.editor_panel = wx.Panel(self.splitter)
        editor_sizer = wx.BoxSizer(wx.VERTICAL)
        self.editor = wx.TextCtrl(self.editor_panel, style=wx.TE_MULTILINE)
        self.editor.Bind(wx.EVT_TEXT, self.on_text_input)
        refresh_button = wx.Button(self.editor_panel, label="Refresh HTML View")
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_html)
        editor_sizer.Add(self.editor, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        editor_sizer.Add(refresh_button, flag=wx.ALL, border=5)
        self.editor_panel.SetSizer(editor_sizer)

        # HTML display panel
        self.html_panel = wx.Panel(self.splitter)
        html_sizer = wx.BoxSizer(wx.VERTICAL)
        self.html_window = wx.html2.WebView.New(self.html_panel)
        self.html_window.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self.on_link_clicked)
        html_sizer.Add(
            self.html_window, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
        )
        self.html_panel.SetSizer(html_sizer)

        # Set up splitter
        self.splitter.SplitVertically(self.editor_panel, self.html_panel)
        self.splitter.SetSashPosition(400)

        vbox.Add(self.splitter, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Bottom controls (Export, Import, Summarize)
        hbox_bottom = wx.BoxSizer(wx.HORIZONTAL)
        share_button.Bind(wx.EVT_BUTTON, self.share_summary)
        # Export button with dropdown
        export_button = wx.Button(panel, label="Export")
        export_button.Bind(wx.EVT_BUTTON, self.show_export_menu)
        hbox_bottom.Add(export_button, flag=wx.ALL, border=5)

        # Import button with dropdown
        import_button = wx.Button(panel, label="Import")
        import_button.Bind(wx.EVT_BUTTON, self.show_import_menu)
        hbox_bottom.Add(import_button, flag=wx.ALL, border=5)

        # Summarize button
        summarize_button = wx.Button(panel, label="Summarize with LLM")
        summarize_button.Bind(wx.EVT_BUTTON, self.on_summarize)
        hbox_bottom.Add(summarize_button, flag=wx.ALL, border=5)

        hbox_bottom.Add(save_button, flag=wx.ALL, border=5)
        vbox.Add(hbox_bottom, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10)

        # Set the main layout
        panel.SetSizer(vbox)

        # Bind browse data button
        browse_data_button.Bind(wx.EVT_BUTTON, self.on_browse_data)

        # Set default font info
        self.current_font = {"name": "Blackadder ITC", "url": None, "from_url": False}
        font = wx.Font(
            12,
            wx.FONTFAMILY_DEFAULT,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL,
            False,
            self.current_font["name"],
        )
        self.editor.SetFont(font)
        # Initialize HTML view
        self.prev_content = ""
        self.last_update_time = 0
        self.UPDATE_THROTTLE_INTERVAL = 2.0
        self.update_html_view()
        self.carousel = None
        self.events_dialog = None

    def on_graph(self, event):
        #print("Getting graph")
        self.net.send_message(self.net.build_message("GETGRAPH", []))

    def enable_listen(self, event):
        # self.awaiting_update = True
        pass

    def handle_error(self, _, explaination, net):
        # wx.MessageBox(f"Error: {explaination}", "Error", wx.OK | wx.ICON_ERROR)
        wx.CallAfter(
            wx.MessageBox, f"Error: {explaination}", "Error", wx.OK | wx.ICON_ERROR
        )
        return

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
            #print("Removed caroussle")

        wx.CallAfter(show_summaries)

    def handle_take_events(self, *params, net):
        events = []
        for event_data in params:
            event = pickle.loads(base64.b64decode(event_data))
            events.append(event)

        def show_events():
            if not events:
                wx.MessageBox("No events found.", "Info", wx.OK | wx.ICON_INFORMATION)
                return

            # Show events dialog
            self.events_dialog = EventsDialog(events, self, self.net)
            self.events_dialog.ShowModal()
            self.events_dialog.Destroy()

        wx.CallAfter(show_events)

    def handle_event_success(self, *params, net):
        wx.CallAfter(
            wx.MessageBox,
            f"Event '{self.event_title}' on {self.formatted_date} at {self.formatted_time} added.",
            "Success",
            wx.OK | wx.ICON_INFORMATION,
        )
        wx.CallAfter(self.dialog.Destroy)

    def save_handlers(self, *params, net):
        print("Save, response: ", params)

    def on_file_content(self, *params, net):
        def update_editor():
            self.editor.AppendText(params[1])
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

    def on_summary_recived(self, *params, net):
        def update_summary():
            summ = params[0]
            start, end = self.editor.GetSelection()
            self.editor.Replace(start, end, summ)
            self.update_html_view()

        wx.CallAfter(update_summary)

    def listen_for_changes(self, *_):
        """Optimized listening thread with better error handling"""
        self.handlers = {
            "ERROR": self.handle_error,
            "TAKESUMMARIES": self.handle_take_summaries,
            "SAVE_SUCCESS": self.save_handlers,
            "EVENT_SUCCESS": self.handle_event_success,
            "FILECONTENT": self.on_file_content,
            "SUMMARY": self.on_summary_recived,
            "TAKEEVENTS": self.handle_take_events,
            "INFO": self.handle_info,
            "TAKEUPDATE": self.take_update,
            "SHARE_SUCCESS": lambda a, *params, net: wx.CallAfter(
                wx.MessageBox,
                f"Summary shared with {params[0]}",
                "Success",
                wx.OK | wx.ICON_INFORMATION,
            ),
            "TAKESUMMARY": self.handle_recived_summary,
            "TAKEGRAPH": self.handle_graph,
            "TAKESUMMARYLINK": self.handle_take_link,
        }

        self.net.add_handlers(self.handlers)
        self.net.sock.settimeout(0.5)
        while True:
            try:
                # Non-blocking receive with better error management
                found_any = self.net.recv_handle_args(self)

                if not found_any:
                    time.sleep(0.1)  # Reduced sleep time

            except Exception as _:
                #print(f"Listening Thread Error: {e}")

                traceback.print_exc()
                time.sleep(1)  # Prevent tight error loop

    def share_summary(self, event):
        #print("Sharing summary")
        dialog = wx.TextEntryDialog(
            None, "Enter the username to share with:", "Share Summary"
        )
        if dialog.ShowModal() == wx.ID_OK:
            username = dialog.GetValue()
            #print("Sharing with: ", username)
            self.net.send_message(self.net.build_message("SHARESUMMARY", [username]))

        else:
            #print("Share canceled by user.")
            dialog.Destroy()
            return

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
            for col in range(3):
                events_list.SetItemTextColour(index, color)

        vbox.Add(events_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Continue button
        continue_button = wx.Button(panel, label="Continue")
        continue_button.Bind(wx.EVT_BUTTON, lambda event: dialog.EndModal(wx.ID_OK))
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

    def normalize(self, text):
        text = unicodedata.normalize("NFC", text)  # Normalize unicode
        text = text.replace("\r\n", "\n").replace("\r", "").rstrip()
        return text

    def update_doc(self, event):
        # if self.awaiting_update:
        #     return #print("Awaiting update, not sending another")
        if self.is_proccesing.is_set():
            return #print("Is proccesing, not sending another")
        if self.is_update_throttled():
            return
        with self.update_lock:
            # old_text = self.prev_content
            # new_text = self.editor.GetValue()
            old_text = self.normalize(
                self.prev_content
            )  # self.prev_content.replace("\r\n", "\n").rstrip()
            new_text = self.normalize(
                self.editor.GetValue()
            )  # self.editor.GetValue().replace("\r\n", "\n").rstrip()
            #print(f"Old Text: {repr(old_text[:50])}")
            #print(f"New Text: {repr(new_text[:50])}")

            # Detect if content has actually changed
            if old_text == new_text:
                #print("No Changes")
                return  self.send_changes([],False)

            # Use advanced diff algorithm
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
                if content == "" and tag != "delete":
                    #print("Not a real change.")
                    continue
                changes.append({"cord": [i1, i2], "type": change_type, "cont": content})

            # Only send update if there are meaningful changes
            # if changes:
            self.send_changes(changes,new_text)
    def send_changes(   self, changes, new_text):
        #print("Found these changes: ", changes)
        payload = json.dumps({"changes": changes})
        try:
            self.net.send_message(
                self.net.build_message("UPDATEDOC", [payload])
            )
            if new_text:
                self.prev_content = new_text
            self.awaiting_update = True
        except Exception as _:
            #print(f"Error sending update: {e}")
            traceback.print_exc()
    def handle_info(self, *params, net):
        #print("Recived info: ", params)
        wx.CallAfter(
            wx.MessageBox,
                f"Info: {params[0]}",
                "Info",
                wx.OK | wx.ICON_INFORMATION,
        )

    def handle_take_link(self, _, link, net):
        #print("Requesting link with sid: ", link)
        self.net.send_message(self.net.build_message("GETSUMMARY", [link]))

    def take_update(self, _, *params, net):
        """Enhanced server update handler with input freezing"""
        try:
            # Indicate server update is in progress
            self.is_proccesing.set()

            # Decode update
            jsoned = json.loads(base64.b64decode(params[0]).decode())

            def update_ui():
                try:
                    # Disable editor during update
                    self.editor.Disable()

                    # Update content
                    new_content = jsoned["doc_content"]
                    self.editor.SetValue(new_content)
                    self.prev_content = new_content
                    self.update_html_view()

                    # Re-enable editor after short delay
                    wx.CallLater(500, self.editor.Enable)

                    # Clear update flags
                    self.awaiting_update = False
                    self.is_proccesing.clear()

                except Exception as _:
                    #print(f"UI Update Error: {e}")
                    self.editor.Enable()
                    self.is_proccesing.clear()

            # Ensure UI update happens on main thread
            wx.CallAfter(update_ui)

        except Exception as _:
            #print(f"Update Processing Error: {e}")
            traceback.print_exc()
            self.is_proccesing.clear()

    def on_font_selector(self, event):
        dialog = FontSelectorDialog(self, self.net)
        if dialog.ShowModal() == wx.ID_OK:
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
            #print(self.current_font)
            # Apply the font to the editor
            font = wx.Font(
                12,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                False,
                font_name,
            )
            self.editor.SetFont(font)

            # If it's a custom font, upload it to the server
            if from_url and font_path:
                # self.upload_font_to_server(font_path, font_name, font_url)
                print("Uploading font to server")
            # Update the HTML view with the new font
            # self.send_update()
            self.update_html_view()

        dialog.Destroy()

    def on_text_input(self, event):
        # Store current position and content
        current_pos = self.editor.GetInsertionPoint()
        current_content = self.editor.GetValue()
        # Continue with existing functionality

        text_pos = current_pos - 1
        if text_pos < 2:
            return self.update_html_view()
        cont = current_content

        # Adjust for newlines
        text_pos -= 1 * cont.count("\n", 0, text_pos)
        if cont[text_pos] != "\n":
            self.update_html_view()
            return
        prev_back_n = cont.rfind("\n", 0, text_pos - 1)
        if prev_back_n == -1:
            prev_back_n = 0
        # line = cont[prev_back_n:text_pos].strip()


        # if line.startswith("###"):
            #print("Found special line: ", line)
            #print("That's the special!!!!!!!!!!!")
        self.update_html_view()

    def on_refresh_html(self, event):
        self.update_html_view()

    def update_html_view(self):
        """Convert text content to HTML and update the HTML window"""
        content = self.editor.GetValue()
        html = self.convert_text_to_html(content)
        self.html_content = html
        # self.html_window.RunScript(f"document.innerHTML = '{html}'")
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
            font_name = font_name.replace('|', '')
            
            html.append("@font-face {{")
            html.append(f"  font-family: '{font_name}';")
            html.append(f"  src: url('{font_url}');")
            html.append("}}")
            html.append(f"body {{ font-family: '{font_name}', sans-serif; margin: 20px; }}")
        else:
            # For system fonts, just set the font-family
            font_name = self.current_font["name"].replace('|', '')# .replace("@","")
            html.append(f"body {{ font-family: '{font_name}', sans-serif; margin: 20px; }}")
        
        html.append("</style></head><body>")
        print("Styling info: ", html)
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
        print("".join(html))
        # #print(html)
        return "".join(html)

    def on_link_clicked(self, event):
        link = event.GetURL()
        if link.startswith("data:"):
            return
        #print(f"Link clicked: {link}")
        if link.startswith("internal:"):
            name = link[len("internal:") :]
            self.net.send_message(self.net.build_message("GETSUMMARYLINK", [name]))
            #print("Sent get summary message")
            cont = base64.b64decode(
                self.net.get_message_params(self.net.recv_message())[0]
            ).decode()
            #print("THE CONTENT: ", cont)
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

    def on_summarize(self, event):
        selected = self.editor.GetStringSelection()
        #print("Currently selecting : ", selected)
        self.net.send_message(self.net.build_message("SUMMARIZE", [selected]))

    def show_export_menu(self, event):
        #print("Showing export menu")
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

    def show_import_menu(self, event):
        #print("Showing import menu")
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

    def import_from_file(self, event):
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

    def on_view_events(self, event):
        self.net.send_message(self.net.build_message("GETEVENTS", []))

    def on_add_event(self, event):
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

    def export_as_markdown(self, event):
        #print("Exporting as Markdown")
        self.export_file("md")

    def export_as_pdf(self, event):
        #print("Exporting as PDF")
        self.export_file("pdf")

    def export_as_html(self, event):
        #print("Exporting as HTML")
        # For HTML, we could directly use our HTML content
        self.export_file("html", use_html=True)

    def export_as_txt(self, event):
        #print("Exporting as TXT")
        self.export_file("txt")

    def export_file(self, ext, use_html=False):
        dialog = wx.FileDialog(
            self,
            message="Save file as ...",
            defaultDir=os.getcwd(),
            defaultFile=f"summary.{ext}",
            wildcard=f"{ext.upper()} files (*.{ext})|*.{ext}",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        if dialog.ShowModal() == wx.ID_CANCEL:
            return
        path = dialog.GetPath()
        dialog.Destroy()

        # # For HTML export, we can use our already formatted HTML content
        # content = (
        #     self.html_content if use_html and ext == "html" else self.editor.GetValue()
        # )
        #
        # self.net.send_message(self.net.build_message("EXPORT", [content, ext]))
        # inner_content = self.net.get_message_params(self.net.recv_message())[0]
        if ext.lower() == "pdf":
            # gross ill rewrite with all the rest

            return pdfkit.from_string(self.html_content, path)
        formated_content = self.format_content(self.editor.GetValue(), ext)
        #print("Writing: ", formated_content)
        with open(path, "w") as f:
            f.write(formated_content)
        # with open(path, "wb") as f:
        #     f.write(base64.b64decode(inner_content))
        wx.MessageBox(
            f"Summary saved to {path}", "Export Successful", wx.OK | wx.ICON_INFORMATION
        )

    def format_content(self, content, ext):
        if ext.lower() == "html":
            #print("HTML")
            #print(self.html_content)
            return self.html_content
        # elif ext == "md" or ext == "txt":
        #     return content
        elif ext.lower() == "pdf":
            return self.html_content
        return content

    def import_from_markdown(self, event):
        #print("Importing from Markdown")
        file_text_content = self.get_file_content("md")
        if not file_text_content:
            return
        self.editor.SetValue(file_text_content)
        self.update_html_view()

    def import_from_pdf(self, event):
        print("Importing from PDF")
        # Implementation would go here

    def import_from_html(self, event):
        #print("Importing from HTML")
        # Implementation would go here
        file_text_content = self.get_file_content("html")
        if not file_text_content:
            return
        # preform the reverse of convert_text_to_html
        self.editor.SetValue(self.html_to_text(file_text_content))
        self.update_html_view()
        return

    def import_from_txt(self, event):
        #print("Importing from TXT")
        # Implementation would go here
        file_text_content = self.get_file_content("txt")
        if not file_text_content:
            return
        self.editor.SetValue(file_text_content)
        self.update_html_view()

    def get_file_content(self, ext):
        # Open a file dialog to select a File
        # return its text content for txt and md
        # returns its html for pdf and html
        dialog = wx.FileDialog(
            self,
            message="Choose a file to import",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dialog.ShowModal() == wx.ID_CANCEL:
            return
        path = dialog.GetPath()
        # if path.endswith(".pdf"):
        #     return self.get_pdf_content(path)
        dialog.Destroy()
        with open(path, "r") as f:
            return f.read()

    # def get_pdf_content(self, path):
    #     # convert pdf to html using pdfkit
    #     return pdfkit.
    def on_browse_data(self, event):
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

    def on_save(self, event):
        #print("Saving")

        # Prompt the user for a title
        dialog = wx.TextEntryDialog(
            None, "Enter a title for the summary:", "Save Summary"
        )
        if dialog.ShowModal() == wx.ID_OK:
            title = dialog.GetValue()
        else:
            #print("Save canceled by user.")
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
        self.net.send_message(
            self.net.build_message(
                "SAVE", [title, self.editor.GetValue(), font_info_str]
            )
        )

    def handle_recived_summary(self, _, *params, net):
        def process_summary():
            try:
                dic = pickle.loads(base64.b64decode(params[0]))
                cont = dic["data"].decode()
                dicty = {"font": dic["summ"].font}
                self.editor.SetValue(cont)
                self.prev_content = cont
                dicty["font"] = dicty.get("font", "Arial")
                
                if dicty['font'] and dicty["font"].startswith("http"):
                    self.current_font = {
                        "name": dicty["font"],
                        "url": dicty["font"],
                        "from_url": True,
                    }
                else:
                    # Clean up the font name - remove any @ symbol or pipe characters
                    clean_font_name = dicty.get("font", "Arial").replace('@', '').replace('|', '')
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
                        "Arial"
                    )
                    self.editor.SetFont(default_font)
                    
                print("Font info: ", self.current_font)
                if hasattr(self, "carousel") and self.carousel:
                    self.carousel.Close()
                # else:
                    #print("No carousel to close")
                # self.update_doc(None)
                # #print("Sleeping 5 secs")
                # time.sleep(5)
                self.update_timer.Start(1000)  # Check every 3 seconds
                self.update_enable_timer.Start(3000)
            except Exception as _:
                #print("Error: ", e)
                traceback.print_exc()
                wx.MessageBox(
                    "Error: Could not retrieve summary content.",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
                self.Close()
        wx.CallAfter(process_summary)
