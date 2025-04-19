import wx


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

        # self.net.add_handler("GETSUMMARY", handle_summary)
        self.net.send_message(
            self.net.build_message("GETSUMMARY", [str(selected_summary.id)])
        )

    def on_close(self, event):
        self.Close()
