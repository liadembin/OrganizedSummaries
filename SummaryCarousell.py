import wx


class SummaryCarousel(wx.Dialog):
    def __init__(self, summaries, net, parent):
        super().__init__(None, title="Summaries Carousel", size=(800, 600))
        self.summaries = summaries
        self.parent = parent
        self.net = net
        self.current_index = 0 if summaries else -1

        # Main layout
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Summary Carousel")
        title.SetFont(
            wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )
        main_sizer.Add(title, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)

        # Carousel container
        carousel_panel = wx.Panel(panel)
        carousel_panel.SetBackgroundColour(wx.Colour(245, 245, 245))
        carousel_sizer = wx.BoxSizer(wx.VERTICAL)

        # Navigation and counter
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.prev_btn = wx.Button(carousel_panel, label="←", size=(40, 30))
        self.counter_text = wx.StaticText(carousel_panel, label="")
        self.next_btn = wx.Button(carousel_panel, label="→", size=(40, 30))

        nav_sizer.Add(self.prev_btn, flag=wx.ALL, border=5)
        nav_sizer.Add(
            self.counter_text,
            proportion=1,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        nav_sizer.Add(self.next_btn, flag=wx.ALL, border=5)

        carousel_sizer.Add(nav_sizer, flag=wx.EXPAND | wx.ALL, border=5)

        # Summary details
        self.summary_panel = wx.Panel(carousel_panel)
        summary_sizer = wx.BoxSizer(wx.VERTICAL)

        # Info section
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left column - Summary metadata
        meta_sizer = wx.BoxSizer(wx.VERTICAL)
        self.share_link = wx.StaticText(
            self.summary_panel, label="", style=wx.ST_ELLIPSIZE_END
        )
        self.share_link.SetFont(
            wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )
        self.owner_id = wx.StaticText(self.summary_panel, label="")
        self.create_time = wx.StaticText(self.summary_panel, label="")

        meta_sizer.Add(self.share_link, flag=wx.EXPAND | wx.BOTTOM, border=5)
        meta_sizer.Add(self.owner_id, flag=wx.EXPAND | wx.BOTTOM, border=3)
        meta_sizer.Add(self.create_time, flag=wx.EXPAND | wx.BOTTOM, border=3)

        info_sizer.Add(meta_sizer, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)

        # Add info section to summary sizer
        summary_sizer.Add(info_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Content preview section
        preview_label = wx.StaticText(self.summary_panel, label="Content Preview:")
        preview_label.SetFont(
            wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )
        summary_sizer.Add(preview_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        self.content_preview = wx.TextCtrl(
            self.summary_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_AUTO_URL,
            size=(-1, 150),
        )
        summary_sizer.Add(
            self.content_preview, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )

        self.summary_panel.SetSizer(summary_sizer)
        carousel_sizer.Add(
            self.summary_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
        )

        carousel_panel.SetSizer(carousel_sizer)
        main_sizer.Add(carousel_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Bottom buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        open_button = wx.Button(panel, label="Open Selected Summary")
        close_button = wx.Button(panel, label="Close")

        btn_sizer.Add(open_button, flag=wx.ALL, border=5)
        btn_sizer.Add(close_button, flag=wx.ALL, border=5)

        main_sizer.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=10)

        panel.SetSizer(main_sizer)

        # Bind events
        self.prev_btn.Bind(wx.EVT_BUTTON, self.on_prev)
        self.next_btn.Bind(wx.EVT_BUTTON, self.on_next)
        open_button.Bind(wx.EVT_BUTTON, self.on_open_summary)
        close_button.Bind(wx.EVT_BUTTON, self.on_close)

        # Initialize the carousel display
        self.update_display()

    def update_display(self):
        if not self.summaries:
            self.summary_panel.Hide()
            self.prev_btn.Disable()
            self.next_btn.Disable()
            self.counter_text.SetLabel("No summaries available")
            return

        self.summary_panel.Show()

        # Update counter
        self.counter_text.SetLabel(f"{self.current_index + 1} of {len(self.summaries)}")

        # Enable/disable navigation buttons
        self.prev_btn.Enable(self.current_index > 0)
        self.next_btn.Enable(self.current_index < len(self.summaries) - 1)

        # Update summary details
        current_summary = self.summaries[self.current_index]
        self.share_link.SetLabel(f"{current_summary.shareLink}")
        self.owner_id.SetLabel(f"By User: {current_summary.ownerId}")
        self.create_time.SetLabel(
            f"Created on: {current_summary.createTime.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Update content preview - trying to access content if available
        try:
            # Get a preview of the content (first 300 chars)
            content_text = (
                str(current_summary.content)[:300]
                if hasattr(current_summary, "content")
                else "Content preview not available"
            )
            if len(content_text) == 300:
                content_text += "..."
            self.content_preview.SetValue(content_text)
        except (AttributeError, TypeError):
            self.content_preview.SetValue("Content preview not available")

        # Force layout update
        self.Layout()

    def on_prev(self, event):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_display()

    def on_next(self, event):
        if self.current_index < len(self.summaries) - 1:
            self.current_index += 1
            self.update_display()

    def on_open_summary(self, event):
        if not self.summaries:
            wx.MessageBox(
                "No summaries available to open.",
                "No Summaries",
                wx.OK | wx.ICON_WARNING,
            )
            return

        selected_summary = self.summaries[self.current_index]

        wx.MessageBox(
            f"Opening summary:\n\n"
            f"Name: {selected_summary.shareLink}\n"
            f"Path: {selected_summary.path_to_summary if hasattr(selected_summary, 'path_to_summary') else 'N/A'}",
            "Open Summary",
            wx.OK | wx.ICON_INFORMATION,
        )

        # Send the network message to get the summary
        self.net.send_message(
            self.net.build_message("GETSUMMARY", [str(selected_summary.id)])
        )

    def on_close(self, event):
        self.Close()
