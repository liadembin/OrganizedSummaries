import datetime
import wx
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


class EventsDialog(wx.Dialog):
    def __init__(self, events, parent, net):
        super().__init__(None, title="Your Events", size=(600, 400))
        self.events = events
        self.parent = parent
        self.net = net
        self.delete_buttons = []  # Store references to delete buttons
        self.credentials = None
        self.service = None
        self.setup_ui()  # Initialize UI

    def setup_ui(self):
        """Setup the UI components and refresh the dialog when called."""
        # Clear existing UI
        self.DestroyChildren()
        # Main layout
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Add Google Calendar import button
        gcal_button = wx.Button(panel, label="Import from Google Calendar")
        gcal_button.Bind(wx.EVT_BUTTON, self.on_import_gcal)
        vbox.Add(gcal_button, flag=wx.ALIGN_LEFT | wx.ALL, border=10)

        # Add "Save to Server" button
        save_button = wx.Button(panel, label="Save Events to Server")
        save_button.Bind(wx.EVT_BUTTON, self.on_save_to_server)
        vbox.Add(save_button, flag=wx.ALIGN_LEFT | wx.ALL, border=10)

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
            delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_btn)
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
        print("Setup the Dialog")
        self.Layout()

    def on_delete_btn(self, event):
        """Handles delete event and refreshes UI."""
        btn_id = event.GetId()
        self.net.send_message(self.net.build_message("DELETEEVENT", [str(btn_id)]))

        def on_delete_success(parent, *params, net):
            selfrl = parent.events_dialog
            # Remove event from list
            selfrl.events = [event for event in selfrl.events if event["id"] != btn_id]
            print("Events then: ", selfrl.events)
            print(selfrl)
            # Refresh UI
            # selfrl.setup_ui()
            wx.CallAfter(selfrl.setup_ui)

        self.parent.net.add_handler("DELETE_SUCCESS", on_delete_success)

    def on_close(self, event):
        self.Close()

    def authenticate_google(self):
        """Authenticate with Google Calendar API"""

        # If modifying these scopes, delete the file token.pickle.
        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = None

        # The file token.pickle stores the user's access and refresh tokens
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open("token.pickle", "wb") as token:
                pickle.dump(creds, token)

        self.service = build("calendar", "v3", credentials=creds)
        return True

    def fetch_google_events(self, days_to_fetch=365):
        """Fetch events from Google Calendar for the next X days"""
        import datetime

        if not self.service:
            if not self.authenticate_google():
                return []

        # Get today's date and calculate end date
        now = datetime.datetime.utcnow()
        end_date = now + datetime.timedelta(days=days_to_fetch)

        # Format dates for API
        now_str = now.isoformat() + "Z"  # 'Z' indicates UTC time
        end_str = end_date.isoformat() + "Z"

        # Call the Calendar API
        events_result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=now_str,
                timeMax=end_str,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        # Convert to our format
        formatted_events = []
        for event in events:
            # Parse event date
            start = event["start"].get("dateTime", event["start"].get("date"))
            # If date is in 'YYYY-MM-DD' format, convert to datetime
            if len(start) == 10:  # Check if it's just a date 'YYYY-MM-DD'
                event_date = datetime.datetime.strptime(start, "%Y-%m-%d")
            else:
                # Try to parse datetime with timezone
                try:
                    # Parse ISO format with timezone
                    event_date = datetime.datetime.fromisoformat(
                        start.replace("Z", "+00:00")
                    )
                except ValueError:
                    # Fallback if parsing fails
                    event_date = datetime.datetime.now()

            # Format for our system
            formatted_event = {
                "id": -1,  # Temporary ID, will be assigned by the server
                "event_title": event.get("summary", "Untitled Event"),
                "event_date": event_date,
                "createTime": datetime.datetime.now(),
            }
            formatted_events.append(formatted_event)

        return formatted_events

    def on_import_gcal(self, event):
        """Handle Google Calendar import button click"""
        import threading

        # Show a wait dialog
        wait_dialog = wx.MessageDialog(
            self,
            "Connecting to Google Calendar...",
            "Please Wait",
            wx.OK | wx.ICON_INFORMATION,
        )
        wait_dialog.Show()

        # Define the thread function
        def import_thread():
            try:
                # Fetch events from Google Calendar
                new_events = self.fetch_google_events()

                # Close the wait dialog and update UI from the main thread
                wx.CallAfter(wait_dialog.Destroy)
                wx.CallAfter(self.show_imported_events, new_events)
            except Exception as e:
                wx.CallAfter(wait_dialog.Destroy)
                wx.CallAfter(self.show_error, f"Error importing events: {str(e)}")

        # Start the thread
        thread = threading.Thread(target=import_thread)
        thread.daemon = True
        thread.start()

    def show_imported_events(self, imported_events):
        """Display imported events and ask for confirmation"""
        if not imported_events:
            wx.MessageBox(
                "No events found in your Google Calendar for the next 30 days.",
                "No Events Found",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Create a dialog to show the events
        dialog = wx.Dialog(self, title="Imported Events", size=(500, 400))
        panel = wx.Panel(dialog)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Instructions
        vbox.Add(
            wx.StaticText(
                panel, label="The following events were found in your Google Calendar:"
            ),
            flag=wx.ALL,
            border=10,
        )

        # Create a list of events
        event_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        event_list.InsertColumn(0, "Title", width=250)
        event_list.InsertColumn(1, "Date", width=150)

        # Add events to the list
        for i, event in enumerate(imported_events):
            index = event_list.InsertItem(i, event["event_title"])
            event_list.SetItem(index, 1, event["event_date"].strftime("%Y-%m-%d %H:%M"))

        vbox.Add(event_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Add buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        import_btn = wx.Button(panel, wx.ID_OK, label="Add These Events")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")

        btn_sizer.Add(import_btn, flag=wx.RIGHT, border=5)
        btn_sizer.Add(cancel_btn)

        vbox.Add(btn_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        panel.SetSizer(vbox)

        # Show dialog and get result
        if dialog.ShowModal() == wx.ID_OK:
            # Add events to our list
            # self.events.extend(imported_events)
            # add a flag to each imported and non imported event to distinguish them
            for event in imported_events:
                event["id"] = -1
            self.events.extend(imported_events)
            # Refresh the UI
            self.setup_ui()
            wx.MessageBox(
                f"Added {len(imported_events)} events.",
                "Success",
                wx.OK | wx.ICON_INFORMATION,
            )

        dialog.Destroy()

    def show_error(self, message):
        """Show error message"""
        wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR)

    def on_save_to_server(self, event):
        """Handle saving events to server button click"""
        # For now, just print the events
        print("Events to save to server:")
        for event in self.events:
            print(
                f"Title: {event['event_title']}, Date: {event['event_date']} Id: {event['id']}"
            )
        import base64

        # You would normally send these to the server here
        # wx.MessageBox(f"Printed {len(self.events)} events to console.\nCheck your terminal for details.",
        #              "Events Printed", wx.OK | wx.ICON_INFORMATION)
        filtered_event = [event for event in self.events if event["id"] == -1]
        pickled = base64.b64encode(pickle.dumps(filtered_event)).decode()
        self.net.send_message(self.net.build_message("SAVE_EVENTS", [pickled]))
