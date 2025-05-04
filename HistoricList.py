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


# Test function to handle the callback
def handle_timestamp_pick(selected_time):
    print(f"Selected timestamp: {selected_time}")
    print(f"Type: {type(selected_time)}")


if __name__ == "__main__":
    app = wx.App()
    
    # Create sample datetime objects
    current_time = datetime.datetime.now()
    sample_dates = [
        current_time - datetime.timedelta(days=10, hours=5),
        current_time - datetime.timedelta(days=7, hours=3),
        current_time - datetime.timedelta(days=5, hours=8),
        current_time - datetime.timedelta(days=3, hours=2),
        current_time - datetime.timedelta(days=1, hours=6),
        current_time
    ]
    
    # Create the frame with sample data
    frame = HistoricListFrame(
        None, 
        "Historic Timestamps", 
        sample_dates,
        on_pick_callback=handle_timestamp_pick
    )
    
    print("HistoricListFrame opened with sample data")
    print("Available timestamps:")
    for dt in sample_dates:
        print(f"  - {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nSelect a timestamp and click 'Pick Timestamp' to see the callback in action")
    
    app.MainLoop()
