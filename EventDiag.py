import wx
import datetime


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

        def on_delete_success(parent, *params, net):
            selfrl = parent.events_dialog
            # msg = self.net.recv_message()
            # code, params = self.net.get_message_code(
            #     msg), self.net.get_message_params(msg)

            # Remove event from list
            selfrl.events = [event for event in self.events if event["id"] != btn_id]

            # Refresh UI
            selfrl.setup_ui()

        self.parent.net.add_handler("DELETE_SUCCESS", on_delete_success)

    def on_close(self, event):
        self.Close()
        exit()
