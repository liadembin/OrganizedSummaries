import wx
import pickle
import base64
from typing import List, Any, Tuple
import networkManager


def is_valid_password(password: str) -> bool:
    """At least 8 chars, at least one letter and one digit."""
    if len(password) < 8:
        return False
    if not any(c.isalpha() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    return True


class LoginFrame(wx.Frame):
    def __init__(self, net: networkManager.NetworkManager):
        super().__init__(None, title="Login", size=(400, 300))
        self.net = net

        # -- Main panel & style --
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(245, 245, 245))
        self.Centre()

        # -- Layout --
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Login to Your Account")
        title_font = wx.Font(14, wx.FONTFAMILY_SWISS, 
                              wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, flag=wx.ALIGN_CENTER | wx.TOP, border=20)

        # Username
        vbox.AddStretchSpacer(1)
        vbox.Add(self._make_labeled_ctrl(panel, "Username:", wx.TextCtrl),
                 flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=40)
        vbox.AddStretchSpacer(1)

        # Password
        vbox.Add(self._make_labeled_ctrl(panel, "Password:", wx.TextCtrl, style=wx.TE_PASSWORD),
                 flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=40)
        vbox.AddStretchSpacer(1)

        # Buttons
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        login_btn = wx.Button(panel, label="Login")
        register_btn = wx.Button(panel, label="Register")
        login_btn.Bind(wx.EVT_BUTTON, self.on_login)
        register_btn.Bind(wx.EVT_BUTTON, self.on_register)
        hbox.Add(login_btn, proportion=1, flag=wx.RIGHT, border=10)
        hbox.Add(register_btn, proportion=1)
        vbox.Add(hbox, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=40)
        vbox.AddStretchSpacer(2)

        panel.SetSizer(vbox)

    def _make_labeled_ctrl(self, parent, label, ctrl_cls, style=0):
        """Helper: returns a horizontal sizer with a label + control."""
        h = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(parent, label=label)
        ctrl = ctrl_cls(parent, style=style)
        setattr(self, label.lower().rstrip(":" ) + "_input", ctrl)
        h.Add(lbl, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        h.Add(ctrl, proportion=1)
        return h

    def on_login(self, event):
        username = self.username_input.GetValue()
        password = self.password_input.GetValue()

        # if not is_valid_password(password):
        #     wx.MessageBox(
        #         "Password must be at least 8 characters long\n"
        #         "and include both letters and digits.",
        #         "Invalid Password",
        #         wx.OK | wx.ICON_WARNING,
        #     )
        #     return

        success, events = self.authenticate(username, password)
        if success:
            wx.MessageBox("Login successful!", "Info",
                          wx.OK | wx.ICON_INFORMATION)
            self.open_main_frame(username, events)
        else:
            wx.MessageBox(
                "Login failed! Please check your credentials.",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def authenticate(self, username, password) -> Tuple[bool, List[Any]]:
        self.net.send_message(
            self.net.build_message("LOGIN", [username, password])
        )
        msg = self.net.recv_message()
        code = self.net.get_message_code(msg)
        params = self.net.get_message_params(msg)

        if "LOGIN_SUCCESS" in code:
            events = (
                [pickle.loads(base64.b64decode(x)) for x in params]
                if len(params) > 1 else []
            )
            return True, events
        return False, []

    def open_main_frame(self, username, events):
        self.Hide()
        from main_frame import MainFrame  # delay import
        main_frame = MainFrame(self.net, username)
        if events:
            main_frame.show_upcoming_events(events)
        main_frame.Show()

    def on_register(self, event):
        dlg = RegisterDialog(self.net)
        dlg.ShowModal()
        dlg.Destroy()


class RegisterDialog(wx.Dialog):
    def __init__(self, net: networkManager.NetworkManager):
        super().__init__(None, title="Register", size=(400, 350))
        self.net = net

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(245, 245, 245))
        self.Centre()

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Create a New Account")
        title_font = wx.Font(14, wx.FONTFAMILY_SWISS, 
                              wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        vbox.Add(title, flag=wx.ALIGN_CENTER | wx.TOP, border=20)

        vbox.AddStretchSpacer(1)

        # Username / Password / Confirm
        vbox.Add(self._make_labeled_ctrl(panel, "Username:", wx.TextCtrl),
                 flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=40)
        vbox.AddStretchSpacer(1)
        vbox.Add(self._make_labeled_ctrl(panel, "Password:", wx.TextCtrl, style=wx.TE_PASSWORD),
                 flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=40)
        vbox.AddStretchSpacer(1)
        vbox.Add(self._make_labeled_ctrl(panel, "Confirm Password:", wx.TextCtrl, style=wx.TE_PASSWORD),
                 flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=40)

        vbox.AddStretchSpacer(2)

        # Register button
        reg_btn = wx.Button(panel, label="Register")
        reg_btn.Bind(wx.EVT_BUTTON, self.on_register)
        vbox.Add(reg_btn, flag=wx.ALIGN_CENTER | wx.ALL, border=20)

        panel.SetSizer(vbox)

    def _make_labeled_ctrl(self, parent, label, ctrl_cls, style=0):
        h = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(parent, label=label)
        ctrl = ctrl_cls(parent, style=style)
        attr = label.lower().rstrip(":" ).replace(" ", "_") + "_input"
        setattr(self, attr, ctrl)
        h.Add(lbl, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        h.Add(ctrl, proportion=1)
        return h

    def on_register(self, event):
        username = self.username_input.GetValue()
        password = self.password_input.GetValue()
        confirm = self.confirm_password_input.GetValue()

        if password != confirm:
            wx.MessageBox(
                "Passwords do not match!", "Error", wx.OK | wx.ICON_ERROR
            )
            return
        if not is_valid_password(password):
            wx.MessageBox(
                "Password must be at least 8 characters long\n"
                "and include both letters and digits.",
                "Invalid Password",
                wx.OK | wx.ICON_WARNING,
            )
            return

        self.net.send_message(
            self.net.build_message("REGISTER", [username, password])
        )
        msg = self.net.recv_message()
        code = self.net.get_message_code(msg)
        params = self.net.get_message_params(msg)

        if "REGISTER_SUCCESS" in code:
            wx.MessageBox(
                "Registration successful! You can now log in.",
                "Info", wx.OK | wx.ICON_INFORMATION
            )
            self.Close()
        else:
            wx.MessageBox(
                f"Registration failed: {params}",
                "Error", wx.OK | wx.ICON_ERROR
            )


if __name__ == "__main__":
    app = wx.App(False)
    net = networkManager.NetworkManager(None,None,None)
    login = LoginFrame(net)
    login.Show()
    app.MainLoop()

