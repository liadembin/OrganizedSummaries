import os
import tempfile
import urllib.request

import wx


class FontSelectorDialog(wx.Dialog):
    def __init__(self, parent, net):
        super().__init__(parent, title="Font Selector", size=(600, 550))
        self.parent = parent
        self.net = net
        self.custom_font_path = None
        self.selected_font = None
        self.from_url = False

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(panel)
        self.system_panel = wx.Panel(notebook)
        self.url_panel = wx.Panel(notebook)

        # System Fonts Tab
        system_sizer = wx.BoxSizer(wx.VERTICAL)
        system_fonts_label = wx.StaticText(
            self.system_panel, label="Available System Fonts:"
        )
        system_sizer.Add(system_fonts_label, flag=wx.LEFT | wx.TOP, border=10)

        font_enumerator = wx.FontEnumerator()
        font_enumerator.EnumerateFacenames()
        system_fonts = sorted(font_enumerator.GetFacenames())
        self.system_fonts_list = wx.ListBox(self.system_panel, choices=system_fonts)
        system_sizer.Add(
            self.system_fonts_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )
        self.system_panel.SetSizer(system_sizer)

        # URL Fonts Tab
        url_sizer = wx.BoxSizer(wx.VERTICAL)
        url_label = wx.StaticText(
            self.url_panel, label="Download font from URL (.ttf or .otf):"
        )
        url_sizer.Add(url_label, flag=wx.LEFT | wx.TOP, border=10)

        self.url_input = wx.TextCtrl(self.url_panel)
        url_sizer.Add(
            self.url_input, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10
        )

        download_button = wx.Button(self.url_panel, label="Download & Add to List")
        url_sizer.Add(download_button, flag=wx.ALL, border=10)

        self.url_fonts_list = wx.ListBox(self.url_panel)
        url_sizer.Add(
            self.url_fonts_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )
        self.url_panel.SetSizer(url_sizer)

        notebook.AddPage(self.system_panel, "System Fonts")
        notebook.AddPage(self.url_panel, "From URL")
        main_sizer.Add(notebook, proportion=2, flag=wx.EXPAND | wx.ALL, border=10)

        # Preview
        preview_label = wx.StaticText(panel, label="Preview:")
        main_sizer.Add(preview_label, flag=wx.LEFT | wx.TOP, border=10)

        self.preview_text = wx.TextCtrl(
            panel,
            value="The quick brown fox jumps over the lazy dog",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        self.preview_text.SetMinSize((580, 60))
        main_sizer.Add(self.preview_text, flag=wx.EXPAND | wx.ALL, border=10)

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(panel, wx.ID_OK)
        self.ok_button.Enable(False)
        self.ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)

        button_sizer.AddButton(self.ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        main_sizer.Add(button_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(main_sizer)

        # Bind Events
        self.system_fonts_list.Bind(wx.EVT_LISTBOX, self.on_system_font_selected)
        self.url_fonts_list.Bind(wx.EVT_LISTBOX, self.on_url_font_selected)
        download_button.Bind(wx.EVT_BUTTON, self.on_download_font)

    def on_system_font_selected(self, event):
        font_name = self.system_fonts_list.GetStringSelection()
        if font_name:
            self.selected_font = font_name
            self.from_url = False
            self.ok_button.Enable(True)
            self.set_preview_font(font_name)

    def on_url_font_selected(self, event):
        font_name = self.url_fonts_list.GetStringSelection()
        if font_name:
            self.selected_font = font_name
            self.from_url = True
            self.ok_button.Enable(True)
            self.set_preview_font(font_name)

    def set_preview_font(self, font_name):
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
        if not (url.lower().endswith(".ttf") or url.lower().endswith(".otf")):
            wx.MessageBox(
                "URL must point to a .ttf or .otf file", "Error", wx.OK | wx.ICON_ERROR
            )
            return

        try:
            progress_dialog = wx.ProgressDialog(
                "Downloading Font",
                "Downloading...",
                maximum=100,
                parent=self,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE,
            )

            temp_dir = tempfile.gettempdir()
            font_filename = os.path.basename(url)
            self.custom_font_path = os.path.join(temp_dir, font_filename)

            def reporthook(blocknum, blocksize, totalsize):
                if totalsize > 0:
                    percent = min(int(blocknum * blocksize * 100 / totalsize), 100)
                    progress_dialog.Update(percent)

            urllib.request.urlretrieve(url, self.custom_font_path, reporthook)
            progress_dialog.Destroy()

            if wx.Font.AddPrivateFont(self.custom_font_path):
                font_name = os.path.splitext(font_filename)[0]
                self.selected_font = font_name
                self.from_url = True

                # Add to list if not already there
                if font_name not in self.url_fonts_list.GetItems():
                    self.url_fonts_list.Append(font_name)

                self.url_fonts_list.SetStringSelection(font_name)
                self.set_preview_font(font_name)
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


# Basic test under __main__
if __name__ == "__main__":

    class DummyNet:
        pass

    app = wx.App(False)
    dlg = FontSelectorDialog(None, DummyNet())
    dlg.ShowModal()
    dlg.Destroy()
    app.MainLoop()
