import datetime
import wx
from wx import adv
from networkManager import NetworkManager
import base64
import pickle
import os


class SummaryCarousel(wx.Dialog):
    def __init__(self, summaries, net, parent):
        super().__init__(None, title="Summaries Carousel", size=(600, 400))
        self.summaries = summaries
        self.parent = parent
        # Main layout
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Listbox to display summaries
        self.summary_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        for summ in self.summaries:
            display_text = f"{summ.shareLink} - By User {summ.ownerId} - Created on {summ.createTime.strftime('%Y-%m-%d %H:%M:%S')}"
            self.summary_list.Append(display_text)

        vbox.Add(self.summary_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Buttons
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        open_button = wx.Button(panel, label="Open")
        close_button = wx.Button(panel, label="Close")
        hbox.Add(open_button, flag=wx.ALL, border=5)
        hbox.Add(close_button, flag=wx.ALL, border=5)

        vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        panel.SetSizer(vbox)

        # Bind events
        open_button.Bind(wx.EVT_BUTTON, self.on_open_summary)
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        self.net = net

    def on_open_summary(self, event):
        selection = self.summary_list.GetSelection()
        if selection == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a summary to open.",
                "No Selection",
                wx.OK | wx.ICON_WARNING,
            )
            return

        selected_summary = self.summaries[selection]
        print(selected_summary)
        wx.MessageBox(
            f"Opening summary:\n\n"
            f"Name: {selected_summary.shareLink}\n"
            f"Path: {selected_summary.path_to_summary}",
            "Open Summary",
            wx.OK | wx.ICON_INFORMATION,
        )
        self.net.send_message(
            self.net.build_message("GETSUMMARY", [str(selected_summary.id)])
        )
        print("Sent get summary message")
        self.net.sock.settimeout(5)
        try:
            cont = base64.b64decode(
                self.net.get_message_params(self.net.recv_message())[0]
            ).decode()
        except Exception as e:
            print("Error: ", e)
            wx.MessageBox(
                "Error: Could not retrieve summary content.",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
            self.Close()
            return

        print("THE CONTENT: ", cont)
        self.parent.summary_box.SetValue(cont)
        self.Close()

    def on_close(self, event):
        self.Close()


class MainFrame(wx.Frame):
    def __init__(self, net: NetworkManager, username):
        super().__init__(None, title="App Dashboard", size=(800, 600))
        self.net = net
        self.username = username

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
        save_button = wx.Button(panel, label="Save")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)

        hbox_top.Add(
            self.username_label,
            proportion=1,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=5,
        )
        hbox_top.Add(share_button, flag=wx.ALL, border=5)
        hbox_top.Add(see_linked_button, flag=wx.ALL, border=5)
        hbox_top.Add(browse_data_button, flag=wx.ALL, border=5)
        add_event_button = wx.Button(panel, label="Add Event")
        add_event_button.Bind(wx.EVT_BUTTON, self.on_add_event)
        hbox_top.Add(add_event_button, flag=wx.ALL, border=5)
        view_events_button = wx.Button(panel, label="View Events")
        view_events_button.Bind(wx.EVT_BUTTON, self.on_view_events)
        hbox_top.Add(view_events_button, flag=wx.ALL, border=5)
        vbox.Add(hbox_top, flag=wx.EXPAND | wx.ALL, border=10)

        # Big text box for summary
        self.summary_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        vbox.Add(self.summary_box, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Bottom controls (Export, Import, Summarize)
        hbox_bottom = wx.BoxSizer(wx.HORIZONTAL)

        # Export button with dropdown
        export_button = wx.Button(panel, label="Export")
        export_button.Bind(wx.EVT_BUTTON, self.show_export_menu)
        hbox_bottom.Add(export_button, flag=wx.ALL, border=5)

        # Import button with dropdown
        import_button = wx.Button(panel, label="Import")
        import_button.Bind(wx.EVT_BUTTON, self.show_import_menu)
        hbox_bottom.Add(import_button, flag=wx.ALL, border=5)
        # In the hbox_top sizer, add:

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

    def on_summarize(self, event):
        selected = self.summary_box.GetStringSelection()
        print("Currently selecting : ", selected)
        self.net.send_message(self.net.build_message("SUMMARIZE", [selected]))
        summ = self.net.get_message_params(self.net.recv_message())[0]
        print("THE SUMM: ", summ)
        # only update the selcted
        # self.summary_box.SetStringSelection(summ)
        start, end = self.summary_box.GetSelection()

        self.summary_box.Replace(start, end, summ)

    def show_export_menu(self, event):
        print("Showing export menu \n\n\n\n\n\n\n")
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
        print("Showing import menu\n\n\n\n\n\n")
        menu = wx.Menu()
        for label, handler in [
            ("Markdown", self.import_from_markdown),
            ("PDF", self.import_from_pdf),
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
        # self.net.recv_handle()
        self.net.send_message(
            self.net.build_message("GETFILECONTENT", [os.path.basename(path)])
        )
        content = self.net.get_message_params(self.net.recv_message())
        print("THE CONTENT: ", content)
        self.summary_box.AppendText(content[0])

    def on_view_events(self, event):
        self.net.send_message(self.net.build_message("GETEVENTS", []))
        msg = self.net.recv_message()
        code, params = self.net.get_message_code(msg), self.net.get_message_params(msg)

        if code.strip() == "ERROR":
            wx.MessageBox(f"Error: {params[0]}", "Error", wx.OK | wx.ICON_ERROR)
            return

        events = []
        for event_data in params:
            event = pickle.loads(base64.b64decode(event_data))
            events.append(event)

        if not events:
            wx.MessageBox("No events found.", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        # Show events dialog
        events_dialog = EventsDialog(events, self, self.net)
        events_dialog.ShowModal()
        events_dialog.Destroy()

    #

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
            event_title = title_input.GetValue()
            event_date = date_picker.GetValue()
            event_time = time_picker.GetValue()

            # Validate inputs
            if not event_title:
                wx.MessageBox(
                    "Please enter an event title.", "Error", wx.OK | wx.ICON_ERROR
                )
                dialog.Destroy()
                return

            # Convert wx date and time to Python date and time
            formatted_date = event_date.FormatISODate()
            formatted_time = event_time.Format("%H:%M:%S")
            datetime_str = f"{formatted_date} {formatted_time}"

            self.net.send_message(
                self.net.build_message("ADDEVENT", [event_title, datetime_str])
            )
            msg = self.net.recv_message()
            code, params = (
                self.net.get_message_code(msg),
                self.net.get_message_params(msg),
            )
            if code.strip() == "ERROR":
                wx.MessageBox(f"Error: {params[0]}", "Error", wx.OK | wx.ICON_ERROR)
                return

            wx.MessageBox(
                f"Event '{event_title}' on {formatted_date} at {formatted_time} added.",
                "Success",
                wx.OK | wx.ICON_INFORMATION,
            )

            dialog.Destroy()

    def export_as_markdown(self, event):
        print("Exporting as Markdown")
        self.export_file("md")

    def export_as_pdf(self, event):
        print("Exporting as PDF")
        self.export_file("pdf")

    def export_as_html(self, event):
        print("Exporting as HTML")
        self.export_file("html")

    def export_as_txt(self, event):
        print("Exporting as TXT")
        self.export_file("txt")

    def export_file(self, ext):
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
        self.net.send_message(
            self.net.build_message("EXPORT", [self.summary_box.GetValue(), ext])
        )
        inner_content = self.net.get_message_params(self.net.recv_message())[0]

        with open(path, "wb") as f:
            f.write(base64.b64decode(inner_content))
        wx.MessageBox(
            f"Summary saved to {path}", "Export Successful", wx.OK | wx.ICON_INFORMATION
        )

    def import_from_markdown(self, event):
        print("Importing from Markdown")

    def import_from_pdf(self, event):
        print("Importing from PDF")

    def import_from_html(self, event):
        print("Importing from HTML")

    def import_from_txt(self, event):
        print("Importing from TXT")

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
        print("Saving")

        # Prompt the user for a title
        dialog = wx.TextEntryDialog(
            None, "Enter a title for the summary:", "Save Summary"
        )
        if dialog.ShowModal() == wx.ID_OK:
            title = dialog.GetValue()
        else:
            print("Save canceled by user.")
            dialog.Destroy()
            return  # Exit if the user cancels the input

        dialog.Destroy()

        # Build and send the save message
        self.net.send_message(
            self.net.build_message("SAVE", [title, self.summary_box.GetValue()])
        )
        msg = self.net.recv_message()
        code, params = self.net.get_message_code(msg), self.net.get_message_params(msg)
        print("CODE RESPONSE :", code)
        print("PARAMS RESPONSE: ", params)


class EventsDialog(wx.Dialog):
    def __init__(self, events, parent, net):
        super().__init__(None, title="Your Events", size=(600, 400))
        self.events = events
        self.parent = parent
        self.net = net
        self.delete_buttons = []  # Store references to delete buttons

        self.setup_ui()  # Initialize UI

    def setup_ui(self):
        """Setup the UI components and refresh the dialog when called."""
        # Clear existing UI
        self.DestroyChildren()

        # Main layout
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Events list (using a ListCtrl for columns)
        self.events_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.events_list.InsertColumn(0, "Title", width=200)
        self.events_list.InsertColumn(1, "Date", width=120)
        self.events_list.InsertColumn(2, "Created", width=180)
        self.events_list.InsertColumn(3, "Past Due", width=80)

        # Populate the list and color rows that are past due
        for i, event in enumerate(self.events):
            is_past_due = event["event_date"] < datetime.datetime.now()
            index = self.events_list.InsertItem(i, event["event_title"])
            self.events_list.SetItem(
                index, 1, event["event_date"].strftime("%Y-%m-%d %H:%M")
            )
            self.events_list.SetItem(
                index, 2, event["createTime"].strftime("%Y-%m-%d %H:%M")
            )
            self.events_list.SetItem(index, 3, str(is_past_due))

            # Color the row red if past due
            if is_past_due:
                for col in range(4):
                    self.events_list.SetItemTextColour(index, wx.RED)

        # Create delete buttons
        buttons_panel = wx.Panel(panel)
        buttons_sizer = wx.BoxSizer(wx.VERTICAL)
        buttons_sizer.Add((0, 23))  # Spacer for header

        self.delete_buttons = []  # Reset button list

        for i, event in enumerate(self.events):
            delete_btn = wx.Button(
                buttons_panel, id=event["id"], label="Delete", size=(70, -1)
            )
            delete_btn.Bind(wx.EVT_BUTTON, self.on_delete)
            self.delete_buttons.append(delete_btn)
            buttons_sizer.Add(delete_btn, flag=wx.BOTTOM, border=1)

        buttons_panel.SetSizer(buttons_sizer)
        self.btn_panel = buttons_panel

        # Layout adjustments
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_sizer.Add(self.events_list, proportion=1, flag=wx.EXPAND)
        h_sizer.Add(buttons_panel, flag=wx.ALIGN_TOP | wx.LEFT, border=5)
        vbox.Add(h_sizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Close button
        close_button = wx.Button(panel, label="Close")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        vbox.Add(close_button, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(vbox)
        self.Layout()

    def on_delete(self, event):
        """Handles delete event and refreshes UI."""
        btn_id = event.GetId()
        self.net.send_message(self.net.build_message("DELETEEVENT", [str(btn_id)]))
        msg = self.net.recv_message()
        code, params = self.net.get_message_code(msg), self.net.get_message_params(msg)

        if code.strip() == "ERROR":
            wx.MessageBox(f"Error: {params[0]}", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Remove event from list
        self.events = [event for event in self.events if event["id"] != btn_id]

        # Refresh UI
        self.setup_ui()

    def on_close(self, event):
        self.Close()
