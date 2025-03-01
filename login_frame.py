import wx
from wx import adv
from main_frame import MainFrame
import networkManager
import pickle
import base64
from typing import List, Any, Tuple


class LoginFrame(wx.Frame):
    def __init__(self, net: networkManager.NetworkManager):
        super().__init__(None, title="Login", size=(400, 300))
        self.net = net
        # Main panel
        panel = wx.Panel(self)

        # Layout
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Login to Your Account")
        title_font = wx.Font(
            14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        title.SetFont(title_font)
        vbox.Add(title, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        # Username input
        hbox_username = wx.BoxSizer(wx.HORIZONTAL)
        username_label = wx.StaticText(panel, label="Username:")
        self.username_input = wx.TextCtrl(panel)
        hbox_username.Add(
            username_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5
        )
        hbox_username.Add(self.username_input, proportion=1)
        vbox.Add(hbox_username, flag=wx.EXPAND | wx.ALL, border=10)

        # Password input
        hbox_password = wx.BoxSizer(wx.HORIZONTAL)
        password_label = wx.StaticText(panel, label="Password:")
        self.password_input = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        hbox_password.Add(
            password_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5
        )
        hbox_password.Add(self.password_input, proportion=1)
        vbox.Add(hbox_password, flag=wx.EXPAND | wx.ALL, border=10)

        # Buttons (Login and Register)
        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)

        login_button = wx.Button(panel, label="Login")
        login_button.Bind(wx.EVT_BUTTON, self.on_login)
        hbox_buttons.Add(login_button, flag=wx.ALL, border=10)

        register_button = wx.Button(panel, label="Register")
        register_button.Bind(wx.EVT_BUTTON, self.on_register)
        hbox_buttons.Add(register_button, flag=wx.ALL, border=10)

        vbox.Add(hbox_buttons, flag=wx.ALIGN_CENTER)

        # Set the main layout
        panel.SetSizer(vbox)

    def show_upcoming_events(self, events):
        # Sort events by proximity to current date
        sorted_events = sorted(
            events,
            key=lambda x: abs(
                (
                    datetime.strptime(x["event_date"], "%Y-%m-%d").date()
                    - datetime.now().date()
                ).days
            ),
        )

        # Create dialog
        dialog = wx.Dialog(self, title="Upcoming Events", size=(500, 400))
        panel = wx.Panel(dialog)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Events list
        events_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        events_list.InsertColumn(0, "Title", width=200)
        events_list.InsertColumn(1, "Date", width=150)
        events_list.InsertColumn(2, "Days Away", width=100)

        for event in sorted_events:
            event_date = datetime.strptime(event["event_date"], "%Y-%m-%d").date()
            days_away = (event_date - datetime.now().date()).days

            index = events_list.InsertItem(0, event["event_title"])
            events_list.SetItem(index, 1, event["event_date"])
            events_list.SetItem(index, 2, str(days_away))

        vbox.Add(events_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Continue button
        continue_button = wx.Button(panel, label="Continue")
        continue_button.Bind(wx.EVT_BUTTON, lambda event: dialog.EndModal(wx.ID_OK))
        vbox.Add(continue_button, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(vbox)

        return dialog.ShowModal()

    def on_login(self, event):
        username = self.username_input.GetValue()
        password = self.password_input.GetValue()

        success, events = self.authenticate(username, password)
        if success:
            wx.MessageBox("Login successful!", "Info", wx.OK | wx.ICON_INFORMATION)
            self.open_main_frame(username, events)
        else:
            wx.MessageBox(
                "Login failed! Please check your credentials.",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def authenticate(self, username, password) -> Tuple[bool, List[Any]]:
        self.net.send_message(self.net.build_message("LOGIN", [username, password]))
        msg = self.net.recv_message()
        code, params = self.net.get_message_code(msg), self.net.get_message_params(msg)
        print(f"PARAMS({len(params)}): ", params)
        if "LOGIN_SUCCESS" in code:
            # [pickle.loads(base64.b64decode(x)) for x in params]
            return (
                True,
                (
                    [pickle.loads(base64.b64decode(x)) for x in params]
                    if len(params) > 1
                    else []
                ),
            )
        return False, []

    def open_main_frame(self, username, events):
        self.Hide()
        main_frame = MainFrame(
            self.net, username
        )  # Assuming MainFrame uses NetworkManager

        print("EVENTS: ", events)

        if events:
            main_frame.show_upcoming_events(events)

        main_frame.Show()

    def on_register(self, event):
        # Open a registration dialog
        dialog = RegisterDialog(self.net)
        dialog.ShowModal()
        dialog.Destroy()


class RegisterDialog(wx.Dialog):
    def __init__(self, net: networkManager.NetworkManager):
        super().__init__(None, title="Register", size=(400, 300))
        self.net = net

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Create a New Account")
        title_font = wx.Font(
            14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        title.SetFont(title_font)
        vbox.Add(title, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        # Username input
        hbox_username = wx.BoxSizer(wx.HORIZONTAL)
        username_label = wx.StaticText(panel, label="Username:")
        self.username_input = wx.TextCtrl(panel)
        hbox_username.Add(
            username_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5
        )
        hbox_username.Add(self.username_input, proportion=1)
        vbox.Add(hbox_username, flag=wx.EXPAND | wx.ALL, border=10)

        # Password input
        hbox_password = wx.BoxSizer(wx.HORIZONTAL)
        password_label = wx.StaticText(panel, label="Password:")
        self.password_input = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        hbox_password.Add(
            password_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5
        )
        hbox_password.Add(self.password_input, proportion=1)
        vbox.Add(hbox_password, flag=wx.EXPAND | wx.ALL, border=10)

        # Confirm password input
        hbox_confirm = wx.BoxSizer(wx.HORIZONTAL)
        confirm_label = wx.StaticText(panel, label="Confirm Password:")
        self.confirm_password_input = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        hbox_confirm.Add(
            confirm_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5
        )
        hbox_confirm.Add(self.confirm_password_input, proportion=1)
        vbox.Add(hbox_confirm, flag=wx.EXPAND | wx.ALL, border=10)

        # Register button
        register_button = wx.Button(panel, label="Register")
        register_button.Bind(wx.EVT_BUTTON, self.on_register)
        vbox.Add(register_button, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(vbox)

    def on_register(self, event):
        username = self.username_input.GetValue()
        password = self.password_input.GetValue()
        confirm_password = self.confirm_password_input.GetValue()

        if password != confirm_password:
            wx.MessageBox("Passwords do not match!", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.net.send_message(self.net.build_message("REGISTER", [username, password]))
        msg = self.net.recv_message()
        code, params = self.net.get_message_code(msg), self.net.get_message_params(msg)
        if "REGISTER_SUCCESS" in code:
            wx.MessageBox(
                "Registration successful! You can now log in.",
                "Info",
                wx.OK | wx.ICON_INFORMATION,
            )
            self.Close()
        else:
            wx.MessageBox(
                f"Registration failed! Please try again. {params}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
