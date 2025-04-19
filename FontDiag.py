import wx
import os
import tempfile
import urllib.request
import urllib


class FontSelectorDialog(wx.Dialog):
    def __init__(self, parent, net):
        super().__init__(parent, title="Font Selector", size=(600, 500))
        self.parent = parent
        self.net = net
        self.custom_font_path = None
        self.selected_font = None
        self.from_url = False

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # System fonts section
        system_fonts_label = wx.StaticText(panel, label="System Fonts")
        main_sizer.Add(system_fonts_label, flag=wx.ALL, border=5)

        # Get all system fonts
        font_enumerator = wx.FontEnumerator()
        font_enumerator.EnumerateFacenames()
        system_fonts = sorted(font_enumerator.GetFacenames())

        # Create list for system fonts
        self.system_fonts_list = wx.ListBox(panel, size=(-1, 200), choices=system_fonts)
        main_sizer.Add(
            self.system_fonts_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
        )

        # Font preview
        preview_label = wx.StaticText(panel, label="Preview:")
        main_sizer.Add(preview_label, flag=wx.ALL, border=5)

        self.preview_text = wx.TextCtrl(
            panel,
            value="The quick brown fox jumps over the lazy dog",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        self.preview_text.SetMinSize((580, 60))
        main_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=5)

        # URL input for custom fonts
        url_label = wx.StaticText(panel, label="Or download font from URL:")
        main_sizer.Add(url_label, flag=wx.ALL, border=5)

        self.url_input = wx.TextCtrl(panel)
        main_sizer.Add(self.url_input, flag=wx.EXPAND | wx.ALL, border=5)

        # Download button
        download_button = wx.Button(panel, label="Download & Preview")
        main_sizer.Add(download_button, flag=wx.ALL, border=5)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(panel, wx.ID_OK)
        self.ok_button.SetDefault()
        # Initially disabled until a font is selected
        self.ok_button.Enable(False)
        cancel_button = wx.Button(panel, wx.ID_CANCEL)

        button_sizer.AddButton(self.ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()

        main_sizer.Add(button_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(main_sizer)

        # Bind events
        self.system_fonts_list.Bind(wx.EVT_LISTBOX, self.on_font_selected)
        download_button.Bind(wx.EVT_BUTTON, self.on_download_font)

    def on_font_selected(self, event):
        font_name = self.system_fonts_list.GetStringSelection()
        if font_name:
            self.selected_font = font_name
            self.from_url = False
            self.ok_button.Enable(True)

            # Update preview
            font = wx.Font(
                12,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                False,
                font_name,
            )
            self.preview_text.SetFont(font)

    def on_download_font(self, event):
        url = self.url_input.GetValue().strip()
        if not url:
            wx.MessageBox("Please enter a URL", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Check if URL is valid and points to a font file
        if not (url.lower().endswith(".ttf") or url.lower().endswith(".otf")):
            wx.MessageBox(
                "URL must point to a .ttf or .otf font file",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
            return

        try:
            # Create a progress dialog
            progress_dialog = wx.ProgressDialog(
                "Downloading Font",
                "Downloading font file...",
                maximum=100,
                parent=self,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE,
            )

            # Download the file to a temporary location
            temp_dir = tempfile.gettempdir()
            font_filename = os.path.basename(url)
            self.custom_font_path = os.path.join(temp_dir, font_filename)

            def reporthook(blocknum, blocksize, totalsize):
                if totalsize > 0:
                    percent = min(int(blocknum * blocksize * 100 / totalsize), 100)
                    progress_dialog.Update(percent)

            urllib.request.urlretrieve(url, self.custom_font_path, reporthook)
            progress_dialog.Destroy()

            # Try to load the font
            if wx.Font.AddPrivateFont(self.custom_font_path):
                # Extract font name
                # This is a simplified approach - in a real app, you might need a more robust way to get the font name
                font_name = os.path.splitext(font_filename)[0]
                self.selected_font = font_name
                self.from_url = True

                # Update preview with the new font
                font = wx.Font(
                    12,
                    wx.FONTFAMILY_DEFAULT,
                    wx.FONTSTYLE_NORMAL,
                    wx.FONTWEIGHT_NORMAL,
                    False,
                    font_name,
                )
                self.preview_text.SetFont(font)

                self.ok_button.Enable(True)
                wx.MessageBox(
                    f"Font '{font_name}' downloaded successfully",
                    "Success",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "Failed to load the downloaded font", "Error", wx.OK | wx.ICON_ERROR
                )
                self.custom_font_path = None

        except Exception as e:
            wx.MessageBox(
                f"Error downloading font: {str(e)}", "Error", wx.OK | wx.ICON_ERROR
            )
            self.custom_font_path = None
