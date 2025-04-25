import wx
import pickle
import base64
import datetime


class HistoricListFrame(wx.Frame):
    def __init__(self, parent, title, parsed, on_pick_callback=None):
        super().__init__(parent, title=title, size=(300, 400))
        panel = wx.Panel(self)
        self.on_pick_callback = on_pick_callback
        self.selected_datetime = None

        self.sorted_list = sorted(parsed)

        # Display strings
        display_list = [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in self.sorted_list]

        # UI Elements
        self.list_box = wx.ListBox(panel, choices=display_list, style=wx.LB_SINGLE)
        pick_button = wx.Button(panel, label="Pick Timestamp")
        pick_button.Bind(wx.EVT_BUTTON, self.on_pick)

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.list_box, 1, wx.EXPAND | wx.ALL, 10)
        sizer.Add(pick_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        self.Centre()
        self.Show()

    def on_pick(self, event):
        index = self.list_box.GetSelection()
        if index != wx.NOT_FOUND:
            self.selected_datetime = self.sorted_list[index]
            if self.on_pick_callback:
                self.on_pick_callback(self.selected_datetime)
            self.Close()
