import datetime
import wx
import wx.adv  # Needed for DatePickerCtrl and TimePickerCtrl
import os
import pickle
import base64  # Needed for encoding/decoding event data for network
import threading  # Needed for GCal import
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Assume net object has methods:
# net.send_message(message)
# net.build_message(command, params)
# net.add_handler(command, handler_function)
# Assume parent object might be needed for context or accessing net if not passed directly
# For standalone testing, you might need dummy net/parent classes.
HEIGHT = 6


class EventsDialog(wx.Dialog):
    def __init__(self, events, parent, net, debug=False):  # Added debug flag
        super().__init__(
            None, title="Your Events Calendar", size=(800, 800)
        )  # Increased height for logs
        self.events = events
        self.parent = parent  # Keep reference if needed elsewhere
        self.net = net
        self.debug = debug  # Store debug flag
        self.log_messages = []  # Initialize log storage
        self.log_display = None  # <<<< MOVE THIS LINE UP

        # --- Now it's safe to log ---
        self.log_event("Initializing EventsDialog.")

        self.delete_buttons = []  # Store references to delete buttons
        self.credentials = None
        self.service = None

        # Calendar navigation variables
        now = datetime.datetime.now()
        self.current_month = now.month
        self.current_year = now.year
        self.selected_date = now.date()
        self.day_buttons = []  # Buttons/Panels representing days
        self.events_by_date = {}  # Cache events grouped by date

        # self.log_display = None # <<<< REMOVE FROM HERE (or comment out)

        # Register network handlers (comments remain the same)
        # ...
        self.organize_events_by_date()
        self.setup_ui()  # Initialize UI
        self.log_event(
            "UI Setup complete."
        )  # This call is fine as setup_ui might assign the TextCtrl
        self.update_events_for_selected_date()

    # def on_event_success(self,parent,*params,net):
    #     # add the event to list and re render
    #     self.log_event("Event successfully added.")
    #     self.events.append(params[0]) # Assuming params[0] is the new event
    #     self.organize_events_by_date() # Reorganize events by date
    #     self.update_events_for_selected_date() # Update the event list for the selected 2025-04-29
    #     self.update_calendar_grid(self.calendar_section) # Update the calendar grid
    #     self.update_log_display() # Update the log display if it exists
    #     self.log_event("Event successfully added and UI updated.")
    # #    self.net.add_handler("EVENT_SUCCESS", self.on_event_success) # Register the handler for event success
    #
    def log_event(self, message):
        """Adds a timestamped message to the log."""
        if not self.debug:
            return
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"{now} - {message}"
        self.log_messages.append(log_entry)
        # Keep log concise (e.g., last 100 entries)
        if len(self.log_messages) > 100:
            self.log_messages.pop(0)
        self.update_log_display()  # Update the GUI

    def update_log_display(self):
        """Updates the log display TextCtrl if it exists and debug is True."""
        if self.debug and self.log_display:
            # Use CallAfter for thread safety if logs can be generated from other threads
            wx.CallAfter(self.log_display.SetValue, "\n".join(self.log_messages))
            wx.CallAfter(
                self.log_display.ShowPosition, self.log_display.GetLastPosition()
            )

    def setup_ui(self):
        """Setup the UI components and refresh the dialog when called."""
        self.log_event("Setting up UI...")
        # Clear existing UI
        self.DestroyChildren()  # More robust than Clear() for complex layouts

        # Main panel and sizer
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Top Buttons Row ---
        top_button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Add New Event button
        add_event_button = wx.Button(panel, label="Add New Event")
        add_event_button.Bind(wx.EVT_BUTTON, self.on_add_event)

        # Google Calendar import button
        gcal_button = wx.Button(panel, label="Import from Google Calendar")
        gcal_button.Bind(wx.EVT_BUTTON, self.on_import_gcal)

        # Save to Server button
        # save_button = wx.Button(panel, label="Save Events to Server")
        # save_button.Bind(wx.EVT_BUTTON, self.on_save_to_server)
        #
        top_button_sizer.Add(add_event_button, flag=wx.RIGHT, border=10)
        top_button_sizer.Add(gcal_button, flag=wx.RIGHT, border=10)
        # top_button_sizer.Add(save_button)
        main_sizer.Add(top_button_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # --- Calendar Section ---
        calendar_section = wx.StaticBox(panel, label="Calendar View")
        self.calendar_section = calendar_section
        calendar_sizer = wx.StaticBoxSizer(calendar_section, wx.VERTICAL)
        self.calendar_sizer = calendar_sizer
        # Month navigation
        month_nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        prev_month_btn = wx.Button(panel, label="◀", size=(30, -1))
        next_month_btn = wx.Button(panel, label="▶", size=(30, -1))

        month_names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        self.month_year_label = wx.StaticText(
            panel, label=f"{month_names[self.current_month-1]} {self.current_year}"
        )
        self.month_year_label.SetFont(
            wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        )

        month_nav_sizer.Add(prev_month_btn, flag=wx.RIGHT, border=5)
        month_nav_sizer.Add(self.month_year_label, proportion=1, flag=wx.ALIGN_CENTER)
        month_nav_sizer.Add(next_month_btn, flag=wx.LEFT, border=5)
        calendar_sizer.Add(month_nav_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        prev_month_btn.Bind(wx.EVT_BUTTON, self.on_prev_month)
        next_month_btn.Bind(wx.EVT_BUTTON, self.on_next_month)

        # Day names row
        days_sizer = wx.GridSizer(rows=1, cols=7, hgap=1, vgap=1)  # Use rows=1
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day_name in day_names:
            day_label = wx.StaticText(panel, label=day_name, style=wx.ALIGN_CENTER)
            day_label.SetFont(
                wx.Font(
                    10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
                )
            )
            day_label.SetBackgroundColour(wx.Colour(220, 220, 220))
            days_sizer.Add(day_label, flag=wx.EXPAND | wx.ALL, border=1)
        calendar_sizer.Add(days_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        # Calendar grid
        self.calendar_grid = wx.GridSizer(rows=HEIGHT, cols=7, hgap=1, vgap=1)
        self.update_calendar_grid(panel)  # Pass panel for creating children
        calendar_sizer.Add(self.calendar_grid, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(
            calendar_sizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
        )  # Allow calendar to expand vertically

        # --- Events for Selected Date Section ---
        events_section = wx.StaticBox(
            panel, label=f"Events for {self.selected_date.strftime('%Y-%m-%d')}"
        )
        events_sizer = wx.StaticBoxSizer(events_section, wx.VERTICAL)
        self.events_static_box = events_section
        events_list_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.events_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES,
            size=(250 + 80 + 150 + 70 + 5 * 4, 300),
        )
        self.events_list.InsertColumn(0, "Title", width=250)
        self.events_list.InsertColumn(1, "Time", width=80)
        self.events_list.InsertColumn(2, "Created", width=150)
        self.events_list.InsertColumn(3, "Past Due", width=70)
        print("Size: ", self.events_list.GetSize())
        # Panel to hold delete buttons aligned with list items
        self.buttons_panel = wx.Panel(panel)
        self.buttons_sizer = wx.BoxSizer(wx.VERTICAL)
        self.buttons_panel.SetSizer(self.buttons_sizer)

        events_list_sizer.Add(
            self.events_list, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=5
        )
        events_list_sizer.Add(
            self.buttons_panel, flag=wx.ALIGN_TOP
        )  # Buttons align top
        events_sizer.Add(
            events_list_sizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
        )
        main_sizer.Add(
            events_sizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )  # Allow event list to expand

        # --- Log Display Section (Conditional) ---
        if self.debug:
            log_section = wx.StaticBox(panel, label="Event Log")
            log_sizer = wx.StaticBoxSizer(log_section, wx.VERTICAL)
            self.log_display = wx.TextCtrl(
                panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP
            )
            self.log_display.SetMinSize((-1, 100))  # Ensure minimum height for log
            log_sizer.Add(
                self.log_display, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
            )
            main_sizer.Add(
                log_sizer, proportion=0, flag=wx.EXPAND | wx.ALL, border=10
            )  # Log section doesn't expand by default

        # --- Close Button ---
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        close_button = wx.Button(panel, label="Close")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        bottom_sizer.AddStretchSpacer()
        bottom_sizer.Add(close_button, flag=wx.ALIGN_CENTER)
        bottom_sizer.AddStretchSpacer()
        main_sizer.Add(
            bottom_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10
        )

        panel.SetSizer(main_sizer)

        # Initial data population
        self.organize_events_by_date()
        self.update_events_for_selected_date()
        self.update_log_display()  # Show initial logs

        # Force layout calculation
        self.Layout()
        self.Fit()  # Adjust dialog size to fit content if needed
        self.Centre()  # Center the dialog on screen
        self.log_event("UI setup and layout complete.")
        self.update_calendar_grid(panel)

    def organize_events_by_date(self):
        """Group events by their date for easier access."""
        self.log_event("Organizing events by date.")
        self.events_by_date = {}
        if not self.events:  # Handle empty events list
            self.log_event("No events to organize.")
            return
        for event in self.events:
            # Ensure event_date is a datetime object
            if isinstance(event.get("event_date"), datetime.datetime):
                event_date = event["event_date"].date()
                if event_date not in self.events_by_date:
                    self.events_by_date[event_date] = []
                self.events_by_date[event_date].append(event)
            else:
                self.log_event(
                    f"Warning: Event '{event.get('event_title')}' has invalid date format: {event.get('event_date')}"
                )
        self.log_event(f"Organized events into {len(self.events_by_date)} date groups.")

    def update_calendar_grid(self, panel):
        """Update the calendar grid with days for the current month/year."""
        self.log_event(
            f"Updating calendar grid for {self.current_month}/{self.current_year}."
        )
        self.calendar_grid.Clear(delete_windows=True)
        self.day_buttons = []

        # --- Define Colors ---
        COLOR_SELECTED = wx.Colour(255, 215, 100)  # Gold
        COLOR_TODAY = wx.Colour(200, 230, 255)  # Light blue
        COLOR_PAST_EVENT = wx.Colour(255, 200, 200)  # Light red
        COLOR_FUTURE_EVENT = wx.Colour(200, 255, 200)  # Light green
        COLOR_DEFAULT_BG = wx.NullColour  # System default background
        COLOR_EMPTY_CELL = wx.Colour(240, 240, 240)  # Grey for empty cells
        COLOR_EVENT_INDICATOR = wx.Colour(0, 100, 0)  # Dark green for dot

        try:
            # Calculate first and last day of month safely
            first_day = datetime.date(self.current_year, self.current_month, 1)

            # Calculate last day more safely
            if self.current_month == 12:
                next_month = datetime.date(self.current_year + 1, 1, 1)
            else:
                next_month = datetime.date(self.current_year, self.current_month + 1, 1)

            last_day = next_month - datetime.timedelta(days=1)
            days_in_month = last_day.day

            self.log_event(
                f"Month has {days_in_month} days, starts on {first_day.strftime('%A')}"
            )
        except ValueError as e:
            # Handle potential invalid date combinations
            self.log_event(f"Error calculating dates: {e}. Resetting to current month.")
            self.current_month = datetime.datetime.now().month
            self.current_year = datetime.datetime.now().year

            # Recalculate after reset
            first_day = datetime.date(self.current_year, self.current_month, 1)
            if self.current_month == 12:
                next_month = datetime.date(self.current_year + 1, 1, 1)
            else:
                next_month = datetime.date(self.current_year, self.current_month + 1, 1)

            last_day = next_month - datetime.timedelta(days=1)
            days_in_month = last_day.day

        # Get the weekday of the first day (0=Monday, 6=Sunday)
        first_weekday = first_day.weekday()

        # Add empty cells before the 1st
        for _ in range(first_weekday):
            empty_cell = wx.Panel(panel)
            empty_cell.SetBackgroundColour(COLOR_EMPTY_CELL)
            self.calendar_grid.Add(empty_cell, flag=wx.EXPAND)
            self.day_buttons.append(None)

        # Get current date/time ONCE for comparison
        now_datetime = datetime.datetime.now()
        now_date = now_datetime.date()  # Today's date

        # Add day cells - this is the critical part for showing all days
        for day in range(1, days_in_month + 1):
            current_date = datetime.date(self.current_year, self.current_month, day)
            day_panel = wx.Panel(panel)
            day_sizer = wx.BoxSizer(wx.VERTICAL)

            # Create day label with adequate size
            day_label = wx.StaticText(day_panel, label=str(day), style=wx.ALIGN_LEFT)
            day_label.SetMinSize((20, 15))  # Ensure minimum size for visibility
            day_sizer.Add(day_label, flag=wx.ALL, border=2)

            # --- Determine Date Status & Styling ---
            is_today = current_date == now_date
            is_selected = current_date == self.selected_date
            date_events = self.events_by_date.get(current_date, [])
            has_events = bool(date_events)

            all_past = False
            any_future = False
            tooltip_lines = []

            if has_events:
                all_past = all(
                    e.get("event_date", now_datetime) < now_datetime
                    for e in date_events
                )
                any_future = any(
                    e.get(
                        "event_date", now_datetime - datetime.timedelta(days=1)
                    ).date()
                    >= now_date
                    for e in date_events
                )

                num_events = len(date_events)
                event_plural = "s" if num_events > 1 else ""

                # Create tooltip preview
                tooltip_lines.append(f"{current_date.strftime('%A, %B %d, %Y')}:")
                for event in sorted(date_events, key=lambda e: e.get("event_date")):
                    time_str = (
                        event.get("event_date", "N/A").strftime("%H:%M")
                        if isinstance(event.get("event_date"), datetime.datetime)
                        else "N/A"
                    )
                    tooltip_lines.append(
                        f"- {time_str} {event.get('event_title', 'No Title')}"
                    )
                    if len(tooltip_lines) > 5:  # Limit preview to a few events
                        tooltip_lines.append("...")
                        break

            # Apply initial background color
            bg_color = COLOR_DEFAULT_BG

            # Add event indicator dot BEFORE applying background colors
            if has_events:
                event_indicator = wx.StaticText(day_panel, label="•")  # Just a dot
                indicator_font = wx.Font(
                    12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
                )
                event_indicator.SetFont(indicator_font)
                event_indicator.SetForegroundColour(COLOR_EVENT_INDICATOR)
                day_sizer.Add(
                    event_indicator, flag=wx.ALIGN_LEFT | wx.LEFT | wx.RIGHT, border=2
                )

                # Color based on event status (show immediately without click)
                if all_past:
                    bg_color = COLOR_PAST_EVENT
                elif any_future:
                    bg_color = COLOR_FUTURE_EVENT

            # Override with Today's color if applicable
            if is_today:
                bg_color = COLOR_TODAY
                day_label.SetFont(
                    wx.Font(
                        10,
                        wx.FONTFAMILY_DEFAULT,
                        wx.FONTSTYLE_NORMAL,
                        wx.FONTWEIGHT_BOLD,
                    )
                )

            # Highest priority: Selected date color
            if is_selected:
                bg_color = COLOR_SELECTED

            # Apply the background color
            day_panel.SetBackgroundColour(bg_color)

            # Finish setting up the day cell
            day_panel.SetSizer(day_sizer)

            # Use lambda with explicit default parameter to avoid late binding issues
            day_panel.Bind(
                wx.EVT_LEFT_DOWN,
                lambda evt, date=current_date: self.on_date_selected(evt, date),
            )

            # Update Tooltip with event preview
            tooltip_text = (
                "\n".join(tooltip_lines)
                if tooltip_lines
                else current_date.strftime("%A, %B %d, %Y")
            )
            day_panel.SetToolTip(tooltip_text)

            self.calendar_grid.Add(day_panel, flag=wx.EXPAND)
            self.day_buttons.append(day_panel)

        # Add empty cells after the last day
        total_cells = HEIGHT * 7
        remaining_cells = total_cells - (first_weekday + days_in_month)
        for _ in range(remaining_cells):
            empty_cell = wx.Panel(panel)
            empty_cell.SetBackgroundColour(COLOR_EMPTY_CELL)
            self.calendar_grid.Add(empty_cell, flag=wx.EXPAND)
            self.day_buttons.append(None)

        # Ensure proper layout
        self.calendar_grid.Layout()
        self.log_event("Calendar grid updated with event highlighting.")

    def on_date_selected(self, event, date):
        """Handle date selection from the calendar with improved responsiveness."""
        self.log_event(f"Date selected: {date}")

        # Store old selection to update only what's needed
        old_date = self.selected_date
        self.selected_date = date

        # --- Update Visual Selection Efficiently ---
        # Only update the two affected dates instead of redrawing entire grid

        # Find old date button and restore its appropriate color
        if old_date:
            old_month = old_date.month
            old_year = old_date.year
            old_day = old_date.day

            # Only try to update if the date was in the current view
            if old_month == self.current_month and old_year == self.current_year:
                # Find the button index for the old date
                first_day = datetime.date(self.current_year, self.current_month, 1)
                first_day_idx = first_day.weekday()
                old_day_idx = first_day_idx + old_day - 1

                if (
                    0 <= old_day_idx < len(self.day_buttons)
                    and self.day_buttons[old_day_idx]
                ):
                    old_panel = self.day_buttons[old_day_idx]

                    # Determine appropriate color for old date
                    now_date = datetime.datetime.now().date()
                    is_today = old_date == now_date
                    date_events = self.events_by_date.get(old_date, [])
                    has_events = bool(date_events)

                    # Default background
                    bg_color = wx.NullColour

                    # Set color based on event status
                    if has_events:
                        now_datetime = datetime.datetime.now()
                        all_past = all(
                            e.get("event_date", now_datetime) < now_datetime
                            for e in date_events
                        )
                        any_future = any(
                            e.get(
                                "event_date", now_datetime - datetime.timedelta(days=1)
                            ).date()
                            >= now_date
                            for e in date_events
                        )

                        if all_past:
                            bg_color = wx.Colour(255, 200, 200)  # Light red
                        elif any_future:
                            bg_color = wx.Colour(200, 255, 200)  # Light green

                    # Override with today's color
                    if is_today:
                        bg_color = wx.Colour(200, 230, 255)  # Light blue

                    # Apply color immediately without full grid redraw
                    old_panel.SetBackgroundColour(bg_color)
                    old_panel.Refresh()

        # Find new date button and highlight it
        if date.month == self.current_month and date.year == self.current_year:
            # Find the button index for the new date
            first_day = datetime.date(self.current_year, self.current_month, 1)
            first_day_idx = first_day.weekday()
            new_day_idx = first_day_idx + date.day - 1

            if (
                0 <= new_day_idx < len(self.day_buttons)
                and self.day_buttons[new_day_idx]
            ):
                new_panel = self.day_buttons[new_day_idx]
                # Highlight selected date
                new_panel.SetBackgroundColour(wx.Colour(255, 215, 100))  # Gold
                new_panel.Refresh()

        # --- Update Events List ---
        # Update the label of the events section
        if hasattr(self, "events_static_box") and self.events_static_box:
            self.events_static_box.SetLabel(
                f"Events for {self.selected_date.strftime('%Y-%m-%d')}"
            )

        # Update the events list without redrawing everything
        self.update_events_for_selected_date()

        # Refresh only what's necessary
        self.events_static_box.Refresh()

    def update_events_for_selected_date(self):
        """Update the events list to show events for the selected date."""
        self.log_event(f"Updating event list for {self.selected_date}.")
        self.events_list.DeleteAllItems()

        # Clear old buttons correctly
        self.buttons_sizer.Clear(delete_windows=True)
        self.delete_buttons = []

        events_on_date = self.events_by_date.get(self.selected_date, [])
        self.log_event(f"Found {len(events_on_date)} events for this date.")

        if events_on_date:
            # Sort events by time
            events_on_date.sort(key=lambda e: e["event_date"])

            now_time = datetime.datetime.now()

            for i, event in enumerate(events_on_date):
                # Check required fields
                event_title = event.get("event_title", "Missing Title")
                event_datetime = event.get("event_date")
                event_createtime = event.get("createTime")
                event_id = event.get("id", None)  # Get ID for delete button

                if event_id is None:
                    self.log_event(f"Warning: Event '{event_title}' is missing an ID.")

                time_str = event_datetime.strftime("%H:%M") if event_datetime else "N/A"
                created_str = (
                    event_createtime.strftime("%Y-%m-%d %H:%M")
                    if event_createtime
                    else "N/A"
                )
                is_past_due = event_datetime < now_time if event_datetime else False

                index = self.events_list.InsertItem(i, event_title)
                self.events_list.SetItem(index, 1, time_str)
                self.events_list.SetItem(index, 2, created_str)
                self.events_list.SetItem(index, 3, str(is_past_due))

                # Highlight past due events
                if is_past_due:
                    item = self.events_list.GetItem(index)
                    item.SetTextColour(wx.RED)
                    self.events_list.SetItem(item)  # Apply the change

                # --- Add Delete Button with proper ID storage ---
                if event_id is not None:
                    # Create delete button with unique ID
                    btn_id = wx.NewId()
                    delete_btn = wx.Button(
                        self.buttons_panel, id=btn_id, label="Delete", size=(70, -1)
                    )

                    # Store event ID as user data
                    delete_btn.event_id = event_id  # Store as an attribute

                    # Bind with explicit reference to the button's event ID
                    delete_btn.Bind(
                        wx.EVT_BUTTON,
                        lambda evt, eid=event_id: self.on_delete_btn(evt, eid),
                    )

                    self.delete_buttons.append(delete_btn)
                    self.buttons_sizer.Add(delete_btn, 0, wx.BOTTOM | wx.EXPAND, 2)
                else:
                    # Add a spacer for consistency
                    self.buttons_sizer.AddSpacer(
                        wx.Button(self.buttons_panel).GetSize().height + 2
                    )

        # Crucial: Layout the panel containing the buttons AFTER adding them
        self.buttons_panel.Layout()

        # Also layout the parent sizer containing the list and button panel
        if self.events_list.GetContainingSizer():
            self.events_list.GetContainingSizer().Layout()
        else:
            print("NO get containing? ")
            self.log_event("ERRROR continaing size")
        self.log_event("Event list updated.")

    def on_prev_month(self, event):
        """Go to previous month."""
        self.log_event("Previous month requested.")
        if self.current_month > 1:
            self.current_month -= 1
        else:
            self.current_month = 12
            self.current_year -= 1
        self.update_month_display()

    def on_next_month(self, event):
        """Go to next month."""
        self.log_event("Next month requested.")
        if self.current_month < 12:
            self.current_month += 1
        else:
            self.current_month = 1
            self.current_year += 1
        self.update_month_display()

    def update_month_display(self):
        """Update the month/year label and refresh calendar grid with improved responsiveness."""
        self.log_event(
            f"Updating display for month: {self.current_month}/{self.current_year}"
        )

        # Cache old selection
        old_selected_date = self.selected_date

        month_names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        self.month_year_label.SetLabel(
            f"{month_names[self.current_month-1]} {self.current_year}"
        )

        # Find the parent panel for the calendar grid
        parent_panel = self.calendar_section

        if parent_panel:
            # Update the grid with the new month
            self.update_calendar_grid(parent_panel)

            # Check if selected date is still valid in the new month/year view
            try:
                # Try to create the same day in the new month
                new_date = datetime.date(
                    self.current_year, self.current_month, old_selected_date.day
                )
                self.selected_date = new_date
            except ValueError:
                # If day is invalid for new month (e.g. Feb 31), select the last day of month
                if self.current_month == 12:
                    last_day = datetime.date(
                        self.current_year + 1, 1, 1
                    ) - datetime.timedelta(days=1)
                else:
                    last_day = datetime.date(
                        self.current_year, self.current_month + 1, 1
                    ) - datetime.timedelta(days=1)

                self.log_event(
                    f"Selected day {old_selected_date.day} invalid for new month, selecting {last_day.day}."
                )
                self.selected_date = last_day

            # Highlight the selected date in the grid without full redraw
            for i, day_btn in enumerate(self.day_buttons):
                if day_btn is not None:
                    first_day = datetime.date(self.current_year, self.current_month, 1)
                    first_weekday = first_day.weekday()

                    if i >= first_weekday:
                        day_num = i - first_weekday + 1
                        if day_num <= 31:  # Safe upper bound
                            try:
                                btn_date = datetime.date(
                                    self.current_year, self.current_month, day_num
                                )
                                if btn_date == self.selected_date:
                                    day_btn.SetBackgroundColour(
                                        wx.Colour(255, 215, 100)
                                    )  # Gold
                                    day_btn.Refresh()
                            except ValueError:
                                pass  # Invalid date, skip

            # Update event list for the (potentially new) selected date
            self.update_events_for_selected_date()

            # Update the events section label
            if hasattr(self, "events_static_box") and self.events_static_box:
                self.events_static_box.SetLabel(
                    f"Events for {self.selected_date.strftime('%Y-%m-%d')}"
                )
                self.events_static_box.Refresh()

            # Only do Layout if we think dimensions changed
            self.Layout()
        else:
            self.log_event("Error: Could not find parent panel for month update.")

    # --- Event Add Functionality ---
    def on_add_event(self, event):
        """Opens a dialog to add a new event."""
        self.log_event("Add event button clicked.")

        dialog = wx.Dialog(self, title="Add New Event", size=(400, 300))
        panel = wx.Panel(dialog)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Title
        title_label = wx.StaticText(panel, label="Event Title:")
        title_input = wx.TextCtrl(panel)
        vbox.Add(title_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        vbox.Add(
            title_input, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10
        )

        # Date (pre-fill with currently selected date)
        date_label = wx.StaticText(panel, label="Event Date:")
        # Convert selected Python date to wx.DateTime
        wx_selected_date = wx.DateTime(
            self.selected_date.day,
            self.selected_date.month - 1,
            self.selected_date.year,
        )
        date_picker = wx.adv.DatePickerCtrl(
            panel, dt=wx_selected_date, style=wx.adv.DP_DEFAULT | wx.adv.DP_SHOWCENTURY
        )
        vbox.Add(date_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        vbox.Add(
            date_picker, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10
        )

        # Time
        time_label = wx.StaticText(panel, label="Event Time:")
        time_picker = wx.adv.TimePickerCtrl(panel, style=wx.adv.TP_DEFAULT)
        # Set a default time, e.g., next hour? Or 00:00?
        # time_picker.SetValue(wx.DateTime.Now()) # Set to current time
        vbox.Add(time_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        vbox.Add(
            time_picker, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10
        )

        # Buttons
        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        vbox.Add(button_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizer(vbox)
        panel.Fit()
        dialog.Fit()
        dialog.Centre()

        # --- Handler for successful add response ---
        # Defined here to capture 'self' and potentially dialog inputs if needed later
        def on_add_success(parent_dialog_self, _, *params, net):
            self_outer = parent_dialog_self  # Reference to EventsDialog instance
            self_outer.log_event(f"Received ADD_SUCCESS from server. Params: {params}")
            if not params:
                self_outer.log_event("Error: ADD_SUCCESS received no parameters.")
                wx.CallAfter(
                    wx.MessageBox,
                    "Server confirmed adding event, but sent no data back.",
                    "Warning",
                    wx.OK | wx.ICON_WARNING,
                    self_outer,
                )
                return

            try:
                # Assuming server sends back the *single* added event, pickled and base64 encoded
                pickled_event_b64 = params[0]
                pickled_event = base64.b64decode(pickled_event_b64)
                new_event = pickle.loads(pickled_event)  # Should be a single dict

                self_outer.log_event(
                    f"Successfully decoded new event: {new_event.get('event_title')} ID: {new_event.get('id')}"
                )

                # Add the new event to the main list
                self_outer.events.append(new_event)

                # Reorganize and refresh UI
                self_outer.organize_events_by_date()

                # Need to find the parent panel to update grid
                # This is awkward here. It's better if setup_ui is called, or update methods handle finding panel
                # Let's call setup_ui for simplicity, although it's less efficient
                wx.CallAfter(self_outer.setup_ui)  # Refresh the whole dialog UI

                # Optionally show a success message
                # wx.CallAfter(wx.MessageBox, f"Event '{new_event['event_title']}' added successfully.", "Event Added", wx.OK | wx.ICON_INFORMATION, self_outer)

            except Exception as e:
                self_outer.log_event(f"Error processing ADD_SUCCESS: {e}")
                wx.CallAfter(
                    wx.MessageBox,
                    f"Error processing server confirmation: {e}",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                    self_outer,
                )

        # --- Show Dialog and Handle Result ---
        if dialog.ShowModal() == wx.ID_OK:
            event_title = title_input.GetValue()
            event_wxdate = date_picker.GetValue()
            event_wxtime = (
                time_picker.GetValue()
            )  # wx.DateTime object containing H, M, S

            # Validate inputs
            if not event_title:
                self.log_event("Add event failed: No title entered.")
                wx.MessageBox(
                    "Please enter an event title.", "Error", wx.OK | wx.ICON_ERROR, self
                )
                dialog.Destroy()  # Destroy the dialog
                return

            # Convert wx date and time to Python datetime
            py_date = datetime.date(
                event_wxdate.GetYear(),
                event_wxdate.GetMonth() + 1,
                event_wxdate.GetDay(),
            )
            py_time = datetime.time(
                event_wxtime.GetHour(),
                event_wxtime.GetMinute(),
                event_wxtime.GetSecond(),
            )
            event_datetime = datetime.datetime.combine(py_date, py_time)

            self.log_event(
                f"Attempting to add event: '{event_title}' at {event_datetime}"
            )

            # Format for sending (server expects string?)
            datetime_str = event_datetime.strftime(
                "%Y-%m-%d %H:%M:%S"
            )  # ISO-like format

            # Add the handler *before* sending the message
            # Pass 'self' (the EventsDialog instance) to the handler
            self.net.add_handler(
                "EVENT_SUCCESS", lambda *p, net: on_add_success(self, *p, net=net)
            )
            print("added handler")
            # Send to server
            self.net.send_message(
                self.net.build_message("ADDEVENT", [event_title, datetime_str])
            )
            self.log_event("ADDEVENT message sent to server.")

            # We don't add to self.events here; we wait for ADD_SUCCESS confirmation
            # dialog.Destroy() should happen AFTER ShowModal returns
        else:
            self.log_event("Add event dialog cancelled by user.")

        dialog.Destroy()  # Ensure dialog is destroyed

    # --- Event Deletion ---
    def on_delete_btn(self, event, delete_id, *, net=None):
        """Handles delete event button click."""
        button_pressed = event.GetEventObject()
        # Retrieve the event ID stored in the button's help text instead of client data
        print("Deleteing helptext=", button_pressed.GetHelpText())
        event_id_to_delete = delete_id
        print("DELETING event_id_to_delete=", delete_id)
        if not event_id_to_delete:
            self.log_event("Error: Delete button pressed but no event ID found.")
            return

        self.log_event(f"Delete button clicked for event ID: {event_id_to_delete}")

        # Confirmation Dialog
        confirm_dialog = wx.MessageDialog(
            self,
            "Are you sure you want to delete this event?",  # Add event title later if needed
            "Confirm Deletion",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )

        if confirm_dialog.ShowModal() == wx.ID_YES:
            self.log_event(f"Deletion confirmed for event ID: {event_id_to_delete}")

            # --- Nested Handler for successful delete response ---
            # Defined here to capture 'self' and 'event_id_to_delete'
            def on_delete_success(parent_dialog_self, *params, net):
                # Use the captured self (parent_dialog_self) and event_id_to_delete
                self_outer = parent_dialog_self
                deleted_id_str = str(event_id_to_delete)  # Use the captured ID

                # Check if the success message matches the ID we tried to delete
                if params and str(params[1]) == deleted_id_str:
                    self_outer.log_event(
                        f"Received DELETE_SUCCESS confirmation for ID: {deleted_id_str}"
                    )

                    # Remove event from the local list
                    initial_count = len(self_outer.events)
                    self_outer.events = [
                        ev
                        for ev in self_outer.events
                        if str(ev.get("id")) != deleted_id_str
                    ]
                    final_count = len(self_outer.events)

                    if final_count < initial_count:
                        self_outer.log_event(
                            f"Event ID {deleted_id_str} removed locally."
                        )
                        # Reorganize and refresh UI
                        self_outer.organize_events_by_date()
                        # Refresh the whole UI to ensure consistency
                        wx.CallAfter(self_outer.setup_ui)
                    else:
                        self_outer.log_event(
                            f"Warning: DELETE_SUCCESS received for {deleted_id_str}, but event not found in local list."
                        )

                else:
                    self_outer.log_event(
                        f"Warning: Received DELETE_SUCCESS, but params {params[1]} didn't match expected ID {deleted_id_str}."
                    )
                    wx.CallAfter(
                        wx.MessageBox,
                        f"Server confirmed deletion, but for an unexpected ID ({params[1] if params else 'None'}). Please refresh.",
                        "Warning",
                        wx.OK | wx.ICON_WARNING,
                        self_outer,
                    )

            # Add the specific handler for this deletion request
            # It needs to check if the success message corresponds to *this* deletion
            self.net.add_handler(
                "DELETE_SUCCESS", lambda *p, net: on_delete_success(self, *p, net=net)
            )

            # Send delete request to server
            self.net.send_message(
                self.net.build_message("DELETEEVENT", [str(event_id_to_delete)])
            )
            self.log_event(f"DELETEEVENT message sent for ID: {event_id_to_delete}")
        else:
            self.log_event(f"Deletion cancelled for event ID: {event_id_to_delete}")

        confirm_dialog.Destroy()

    # --- Other Actions ---
    def on_close(self, event):
        self.log_event("Close button clicked.")
        self.Close()

    def authenticate_google(self):
        """Authenticate with Google Calendar API"""
        self.log_event("Attempting Google authentication.")
        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = None
        token_file = "token.pickle"
        creds_file = "credentials.json"  # Make sure this file exists

        if not os.path.exists(creds_file):
            self.log_event(f"Error: {creds_file} not found.")
            self.show_error(
                f"{creds_file} not found. Please download it from Google Cloud Console and place it in the application directory."
            )
            return False

        if os.path.exists(token_file):
            try:
                with open(token_file, "rb") as token:
                    creds = pickle.load(token)
                self.log_event("Loaded credentials from token.pickle.")
            except Exception as e:
                self.log_event(
                    f"Error loading token.pickle: {e}. Will re-authenticate."
                )
                creds = None  # Force re-authentication

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    self.log_event("Refreshing expired Google credentials.")
                    creds.refresh(Request())
                except Exception as e:
                    self.log_event(
                        f"Error refreshing token: {e}. Re-authentication required."
                    )
                    creds = None  # Force re-authentication
                    # Optionally delete the bad token file
                    if os.path.exists(token_file):
                        os.remove(token_file)

            else:
                try:
                    self.log_event("No valid credentials found. Starting OAuth flow.")
                    flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                    # Make run_local_server use a specific port if needed, 0 picks random available
                    creds = flow.run_local_server(port=0)
                    self.log_event("OAuth flow completed successfully.")
                except Exception as e:
                    self.log_event(f"Error during OAuth flow: {e}")
                    self.show_error(f"Failed to authenticate with Google: {e}")
                    return False

            # Save the credentials for the next run
            try:
                with open(token_file, "wb") as token:
                    pickle.dump(creds, token)
                self.log_event("Saved new credentials to token.pickle.")
            except Exception as e:
                self.log_event(f"Error saving token.pickle: {e}")

        try:
            self.service = build("calendar", "v3", credentials=creds)
            self.log_event("Google Calendar service built successfully.")
            return True
        except Exception as e:
            self.log_event(f"Error building Google Calendar service: {e}")
            self.show_error(f"Failed to build Google Calendar service: {e}")
            return False

    def fetch_google_events(self, days_to_fetch=365):
        """Fetch events from Google Calendar"""
        self.log_event(
            f"Fetching Google Calendar events for the next {days_to_fetch} days."
        )
        if not self.service:
            self.log_event("Google service not available. Attempting authentication.")
            if not self.authenticate_google():
                self.log_event("Authentication failed. Cannot fetch events.")
                return []

        now = datetime.datetime.utcnow()
        end_date = now + datetime.timedelta(days=days_to_fetch)
        now_str = now.isoformat() + "Z"
        end_str = end_date.isoformat() + "Z"

        try:
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
            gcal_events = events_result.get("items", [])
            self.log_event(f"Fetched {len(gcal_events)} events from Google Calendar.")
        except Exception as e:
            self.log_event(f"Error fetching Google Calendar events: {e}")
            self.show_error(f"Error fetching events from Google Calendar: {e}")
            return []

        formatted_events = []
        for event in gcal_events:
            summary = event.get("summary", "Untitled Event")
            start_info = event.get("start", {})
            start = start_info.get(
                "dateTime", start_info.get("date")
            )  # dateTime is preferred

            if not start:
                self.log_event(
                    f"Skipping event '{summary}' - no start date/time found."
                )
                continue

            try:
                # Handle date vs datetime
                if len(start) == 10:  # 'YYYY-MM-DD' format (all-day event)
                    event_dt = datetime.datetime.strptime(start, "%Y-%m-%d")
                    # Assign a default time (e.g., midnight) or handle as needed
                    event_dt = event_dt.replace(hour=0, minute=0, second=0)
                else:  # Assume ISO format 'YYYY-MM-DDTHH:MM:SS...'
                    # Make timezone aware if possible, otherwise naive UTC assumed by 'Z'
                    if "T" in start:
                        # Handle potential timezone offsets or 'Z'
                        if start.endswith("Z"):
                            start = start[:-1] + "+00:00"  # Replace Z with UTC offset
                        try:
                            event_dt = datetime.datetime.fromisoformat(start)
                            # Convert to local time if timezone aware
                            if event_dt.tzinfo:
                                event_dt = event_dt.astimezone(
                                    datetime.datetime.now().astimezone().tzinfo
                                )
                            event_dt = event_dt.replace(
                                tzinfo=None
                            )  # Make naive for internal use
                        except ValueError:
                            self.log_event(
                                f"Warning: Could not parse complex date '{start}' for event '{summary}'. Using now()."
                            )
                            event_dt = datetime.datetime.now()  # Fallback
                    else:
                        # Fallback if format is unexpected
                        self.log_event(
                            f"Warning: Unexpected date format '{start}' for event '{summary}'. Using now()."
                        )
                        event_dt = datetime.datetime.now()

                formatted_event = {
                    "id": -1,  # Indicate it's newly imported, needs saving
                    "event_title": summary,
                    "event_date": event_dt,  # Store as Python datetime
                    "createTime": datetime.datetime.now(),  # Set creation time to now
                }
                formatted_events.append(formatted_event)

            except ValueError as ve:
                self.log_event(
                    f"Error parsing date '{start}' for event '{summary}': {ve}"
                )
            except Exception as e:
                self.log_event(f"Unexpected error processing event '{summary}': {e}")

        self.log_event(f"Formatted {len(formatted_events)} Google events for import.")
        return formatted_events

    def on_import_gcal(self, event):
        """Handle Google Calendar import button click"""
        self.log_event("Import from Google Calendar button clicked.")
        
        # Create a progress dialog that doesn't block the UI
        progress_dialog = wx.ProgressDialog(
            "Google Calendar Import",
            "Connecting to Google Calendar and fetching events...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        
        # Update to show it's working (indeterminate progress)
        progress_dialog.Pulse()
        
        # Define the thread function
        def import_thread():
            try:
                new_events = self.fetch_google_events()
                # Use CallAfter to interact with UI from the worker thread
                wx.CallAfter(progress_dialog.Destroy)  # Properly close the dialog
                wx.CallAfter(self.show_imported_events, new_events)
            except Exception as e:
                wx.CallAfter(progress_dialog.Destroy)  # Ensure dialog is closed on error
                self.log_event(f"Error in import thread: {e}")
                # Show error message in the main thread
                wx.CallAfter(
                    self.show_error, f"Error importing Google events: {str(e)}"
                )
        
        # Start the thread
        thread = threading.Thread(target=import_thread)
        thread.daemon = True  # Allow program to exit even if thread is running
        thread.start()
        self.log_event("Google import thread started.")
        
        # Allow UI updates while waiting
        wx.Yield()
    
    def show_imported_events(self, imported_events):
        """Display imported events and ask for confirmation"""
        try:
            self.log_event(
                f"Showing {len(imported_events)} imported events for confirmation."
            )
            if not imported_events:
                wx.MessageBox(
                    "No new events found in your Google Calendar for the specified period.",
                    "No Events Found",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
                return

            dialog = wx.Dialog(
                self, title="Confirm Google Calendar Import", size=(500, 400)
            )
            panel = wx.Panel(dialog)
            vbox = wx.BoxSizer(wx.VERTICAL)

            vbox.Add(
                wx.StaticText(
                    panel, label="Add the following events from Google Calendar?"
                ),
                flag=wx.ALL,
                border=10,
            )

            event_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
            event_list.InsertColumn(0, "Title", width=250)
            event_list.InsertColumn(1, "Date & Time", width=180)

            for i, event in enumerate(imported_events):
                index = event_list.InsertItem(i, event["event_title"])
                event_list.SetItem(index, 1, event["event_date"].strftime("%Y-%m-%d %H:%M"))

            vbox.Add(event_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

            btn_sizer = wx.StdDialogButtonSizer()
            import_btn = wx.Button(panel, wx.ID_OK, label="Add These Events")
            cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
            btn_sizer.AddButton(import_btn)
            btn_sizer.AddButton(cancel_btn)
            btn_sizer.Realize()

            vbox.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=10)
            panel.SetSizer(vbox)
            panel.Fit()
            dialog.Fit()
            dialog.Centre()

            if dialog.ShowModal() == wx.ID_OK:
                self.log_event(f"User confirmed import of {len(imported_events)} events.")
                # Add events to our list - they already have id = -1
                self.events.extend(imported_events)
                self.organize_events_by_date()
                self.setup_ui()  # Refresh UI fully
                wx.MessageBox(
                    f"Added {len(imported_events)} events. Remember to 'Save Events to Server'.",
                    "Import Successful",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
            else:
                self.log_event("User cancelled Google event import.")

            dialog.Destroy()
        except Exception as e:
            import traceback
            traceback.print_exc()
    def show_error(self, message):
        """Show error message dialog."""
        self.log_event(f"Displaying error: {message}")
        wx.MessageBox(message, "Error", wx.OK | wx.ICON_ERROR, self)

    def on_save_to_server(self, event):
        """Handle saving newly added/imported events to server."""
        self.log_event("Save to Server button clicked.")

        # Filter events that haven't been saved yet (assume id == -1)
        events_to_save = [ev for ev in self.events if ev.get("id") == -1]

        if not events_to_save:
            self.log_event("No new events to save.")
            wx.MessageBox(
                "No new events to save to the server.",
                "Nothing to Save",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return

        self.log_event(f"Found {len(events_to_save)} new events to save.")
        # Print for debugging, remove later
        # print("Events to save to server:")
        # for ev in events_to_save: print(f"  Title: {ev['event_title']}, Date: {ev['event_date']}")

        try:
            # Serialize the list of events to save
            pickled_data = pickle.dumps(events_to_save)
            encoded_data = base64.b64encode(pickled_data).decode("utf-8")  # Use utf-8

            # Add handler for save success? Assume server sends back updated events?
            # For now, just send. Need server response spec.
            # self.net.add_handler("SAVE_SUCCESS", self.handle_save_success)

            # Send the encoded data
            self.net.send_message(self.net.build_message("SAVE_EVENTS", [encoded_data]))
            self.log_event("SAVE_EVENTS message sent to server.")

            # Optionally clear the id=-1 flag locally *after* successful confirmation
            # For now, we assume the server will send back updated event list on connect/refresh

            wx.MessageBox(
                f"Sent {len(events_to_save)} new event(s) to the server for saving.",
                "Save Request Sent",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )

        except Exception as e:
            self.log_event(f"Error pickling or sending events to save: {e}")
            self.show_error(f"Error preparing events for saving: {e}")


# Example usage (requires a dummy parent and net object for standalone running)
if __name__ == "__main__":

    # --- Dummy Network Class ---
    class DummyNetwork:
        def __init__(self):
            self.handlers = {}
            print("DummyNetwork Initialized")

        def add_handler(self, command, handler_func):
            print(f"DummyNetwork: Adding handler for {command}")
            self.handlers[command] = handler_func

        def build_message(self, command, params):
            print(f"DummyNetwork: Building message {command} with params {params}")
            return f"{command}~" + "~".join(map(str, params))  # Simple pipe delimiter

        def send_message(self, message):
            print(f"DummyNetwork: Sending message: {message}")
            # --- Simulate Server Responses ---
            parts = message.split("~", 1)
            command = parts[0]
            params = parts[1].split("~") if len(parts) > 1 else []

            if command == "DELETEEVENT":
                event_id = params[0]
                print(f"Simulating DELETE_SUCCESS for ID {event_id}")
                if "DELETE_SUCCESS" in self.handlers:
                    # Need to run handler slightly later to avoid UI recursion issues
                    wx.CallLater(
                        100, self.handlers["DELETE_SUCCESS"], event_id,net=self
                    )  # Pass back the ID

            elif command == "ADDEVENT":
                title, dt_str = params
                print(f"Simulating ADD_SUCCESS for title '{title}'")
                # Create a fake new event dict
                new_id = datetime.datetime.now().microsecond  # Fake unique ID
                new_event = {
                    "id": new_id,
                    "event_title": title + " (Added)",
                    "event_date": datetime.datetime.strptime(
                        dt_str, "%Y-%m-%d %H:%M:%S"
                    ),
                    "createTime": datetime.datetime.now(),
                }
                # Pickle and encode it
                pickled_event = pickle.dumps(new_event)
                encoded_event = base64.b64encode(pickled_event).decode()
                if "ADD_SUCCESS" in self.handlers:
                    wx.CallLater(100, self.handlers["ADD_SUCCESS"], encoded_event,net=self)

            elif command == "SAVE_EVENTS":
                print(
                    "Simulating server received SAVE_EVENTS. No specific reply defined yet."
                )
                # Potentially simulate a refresh or updated event list later

    # --- Dummy Parent Frame ---
    class DummyFrame(wx.Frame):
        def __init__(self):
            super().__init__(None, title="Main App")
            self.net = DummyNetwork()  # Frame owns the network connection
            # Add button to open dialog
            panel = wx.Panel(self)
            button = wx.Button(panel, label="Open Events Calendar")
            button.Bind(wx.EVT_BUTTON, self.show_events)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(button, 0, wx.ALL | wx.CENTER, 20)
            panel.SetSizer(sizer)
            self.Show()

        def show_events(self, event):
            # --- Sample Events Data ---
            now = datetime.datetime.now()
            sample_events = [
                {
                    "id": 1,
                    "event_title": "Team Meeting",
                    "event_date": now.replace(hour=10, minute=0, second=0),
                    "createTime": now - datetime.timedelta(days=1),
                },
                {
                    "id": 2,
                    "event_title": "Project Deadline",
                    "event_date": now + datetime.timedelta(days=2, hours=3),
                    "createTime": now - datetime.timedelta(days=5),
                },
                {
                    "id": 3,
                    "event_title": "Lunch with Client",
                    "event_date": now.replace(hour=12, minute=30, second=0),
                    "createTime": now - datetime.timedelta(hours=4),
                },
                {
                    "id": 4,
                    "event_title": "Past Event",
                    "event_date": now - datetime.timedelta(days=1, hours=2),
                    "createTime": now - datetime.timedelta(days=10),
                },
                # Event on a different day
                {
                    "id": 5,
                    "event_title": "Future Planning",
                    "event_date": now + datetime.timedelta(days=5, hours=14),
                    "createTime": now - datetime.timedelta(days=1),
                },
            ]
            # Ensure dates are datetime objects
            for ev in sample_events:
                if isinstance(ev["event_date"], str):
                    ev["event_date"] = datetime.datetime.fromisoformat(ev["event_date"])
                if isinstance(ev["createTime"], str):
                    ev["createTime"] = datetime.datetime.fromisoformat(ev["createTime"])

            # Pass events, self (as parent), and network object
            dlg = EventsDialog(sample_events, self, self.net, debug=True)
            dlg.ShowModal()
            dlg.Destroy()

    app = wx.App(False)
    frame = DummyFrame()
    app.MainLoop()
