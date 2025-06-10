import collections
import math

import wx


class GraphDialog(wx.Dialog):
    def __init__(self, parent, root_nodes, network_manager):
        super().__init__(parent, title="Summary Graph View", size=(800, 600))
        self.net = network_manager

        # Store root nodes directly - no flattening
        self.root_nodes = root_nodes

        # Build a mapping of all node IDs to nodes
        self.node_map = {}
        self._build_node_map(root_nodes)

        # --- UI Setup ---
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        instructions = wx.StaticText(
            panel,
            label="Click a node to select it; double-click or use the 'View' button to open its summary.",
        )
        sizer.Add(instructions, 0, wx.ALL, 10)

        self.canvas = wx.Panel(panel, style=wx.BORDER_SUNKEN)
        self.canvas.SetBackgroundColour(wx.WHITE)
        self.canvas.Bind(wx.EVT_PAINT, self._on_paint)
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self._on_click)
        self.canvas.Bind(wx.EVT_LEFT_DCLICK, self._on_double_click)
        sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 10)

        self.info_label = wx.StaticText(panel, label="No node selected")
        sizer.Add(self.info_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.view_btn = wx.Button(panel, label="View Selected Summary")
        self.view_btn.Bind(wx.EVT_BUTTON, self._on_view)
        self.view_btn.Disable()
        close_btn = wx.Button(panel, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        btn_sizer.Add(self.view_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(close_btn)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(sizer)
        self.SetMinSize((600, 500))

        self.selected_id = None
        self.node_positions = {}
        self.node_sizes = {}

        # Delay layout until shown
        self.Bind(wx.EVT_SHOW, self._on_show)

    def _build_node_map(self, nodes):
        """Build a map of node IDs to nodes, handling duplicates"""
        for node in nodes:
            self.node_map[node.id] = node

            # We don't recursively add children here, as they might be
            # node IDs rather than actual nodes

    def _on_show(self, event):
        if event.IsShown():
            wx.CallAfter(self._layout)

    def _layout(self):
        self._compute_positions()
        self.canvas.Refresh()

    def _compute_positions(self):
        w, h = self.canvas.GetClientSize()
        w, h = max(w, 600), max(h, 400)

        # First, compute the position of all root nodes
        self.node_positions = {}
        self.node_sizes = {}

        # Position root nodes in a row at the top
        y = 50
        padding = 100
        available_width = w - (2 * padding)

        if len(self.root_nodes) == 1:
            x_positions = [w / 2]
        else:
            step = available_width / max(1, len(self.root_nodes) - 1)
            x_positions = [padding + i * step for i in range(len(self.root_nodes))]

        # Assign positions to root nodes
        for i, node in enumerate(self.root_nodes):
            self.node_positions[node.id] = (x_positions[i], y)
            # Size based on number of connections
            deg = len(node.children)
            self.node_sizes[node.id] = 30 + min(deg * 5, 30)

        # Now compute positions for children recursively
        self._position_children(self.root_nodes, y, w, h)

        # Display stats for debugging
        print(f"Positioned {len(self.node_positions)} nodes")

    def _position_children(self, parent_nodes, parent_y, width, height):
        """Position all children of the given parent nodes"""
        if not parent_nodes:
            return

        # Collect all unique child IDs, accounting for shared children
        all_children = {}  # Map from child ID to node if available

        for parent in parent_nodes:
            for child_id in parent.children:
                # Try to get actual node if available
                child_node = self.node_map.get(child_id)
                if child_node:
                    all_children[child_id] = child_node
                else:
                    # Just store the ID if the node isn't available
                    all_children[child_id] = child_id

        if not all_children:
            return

        # Calculate y position for this level
        y = parent_y + 100  # Fixed vertical spacing

        # Position children horizontally
        padding = 100
        available_width = width - (2 * padding)
        child_ids = list(all_children.keys())

        if len(child_ids) == 1:
            x_positions = [width / 2]
        else:
            step = available_width / max(1, len(child_ids) - 1)
            x_positions = [padding + i * step for i in range(len(child_ids))]

        # Assign positions to children
        actual_child_nodes = []
        for i, child_id in enumerate(child_ids):
            self.node_positions[child_id] = (x_positions[i], y)

            # If we have the actual node, size it and add to list for next level
            child = all_children[child_id]
            if isinstance(child, str):
                # Just an ID, use default size
                self.node_sizes[child_id] = 30
            else:
                # Actual node object
                deg = len(child.children)
                self.node_sizes[child_id] = 30 + min(deg * 5, 30)
                actual_child_nodes.append(child)

        # Recursively position the next level of children
        self._position_children(actual_child_nodes, y, width, height)

    def _on_paint(self, event):
        dc = wx.PaintDC(self.canvas)
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return

        # First draw all connections
        pen = wx.Pen(wx.Colour(100, 100, 200), 1)
        gc.SetPen(pen)

        # Process all nodes in our node map
        for node_id, node in self.node_map.items():
            if node_id not in self.node_positions:
                continue

            sx, sy = self.node_positions[node_id]

            # Draw connections to all children
            for child_id in node.children:
                if child_id not in self.node_positions:
                    continue

                tx, ty = self.node_positions[child_id]
                gc.StrokeLine(sx, sy, tx, ty)
                self._draw_arrow(gc, sx, sy, tx, ty)

        # Then draw all nodes we have positions for
        for node_id, (x, y) in self.node_positions.items():
            r = self.node_sizes.get(node_id, 30) / 2

            # Get node if available - properly retrieve the node for THIS node_id
            node = self.node_map.get(node_id)

            # Determine color
            if self.selected_id == node_id:
                gc.SetPen(wx.Pen(wx.BLACK, 2))
                gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(255, 200, 0))))
            elif node and hasattr(node, "type"):
                clr = (
                    wx.Colour(100, 200, 100)
                    if node.type == "summary"
                    else wx.Colour(100, 150, 255)
                )
                gc.SetPen(wx.Pen(wx.BLACK, 1))
                gc.SetBrush(gc.CreateBrush(wx.Brush(clr)))
            else:
                # Default color for nodes without type information
                gc.SetPen(wx.Pen(wx.BLACK, 1))
                gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(180, 180, 180))))

            gc.DrawEllipse(x - r, y - r, 2 * r, 2 * r)

            # Draw label - fixed to properly look up node by its ID
            print("Looking up: ", node_id)
            current_node = node_id
            if type(node_id) is int:
                current_node = self.node_map.get(node_id)

            name = (
                current_node.name
                if current_node and hasattr(current_node, "name")
                else str(node_id)
            )
            if len(name) > 15:
                name = name[:12] + "..."

            font = wx.Font(
                8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
            )
            gc.SetFont(gc.CreateFont(font, wx.BLACK))
            tw, th = gc.GetTextExtent(name)
            gc.DrawText(name, x - tw / 2, y + r + 5)

    def _draw_arrow(self, gc, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist < 10:
            return

        ux, uy = dx / dist, dy / dist  # Unit vector in direction of arrow
        px, py = -uy, ux  # Perpendicular vector

        # Calculate node radius at destination
        r = 0
        dest_id = self._find_node_at(x2, y2)
        if dest_id and dest_id in self.node_sizes:
            r = self.node_sizes[dest_id] / 2

        # Calculate where to place arrow head
        back = min(r + 5, dist - 10) if r else dist - 10
        ax, ay = x2 - ux * back, y2 - uy * back

        # Draw arrow head
        size = 6
        p1 = (ax + px * size, ay + py * size)
        p2 = (ax - px * size, ay - py * size)
        path = gc.CreatePath()
        path.MoveToPoint(x2 - ux * r, y2 - uy * r)
        path.AddLineToPoint(*p1)
        path.AddLineToPoint(*p2)
        path.CloseSubpath()
        gc.FillPath(path)

    def _find_node_at(self, x, y):
        for nid, (nx, ny) in self.node_positions.items():
            r = self.node_sizes.get(nid, 30) / 2
            if (x - nx) ** 2 + (y - ny) ** 2 <= r * r:
                return nid
        return None

    def _on_click(self, evt):
        x, y = evt.GetPosition()
        nid = self._find_node_at(x, y)
        if nid is not None:
            self.selected_id = nid
            self.view_btn.Enable()
            self._update_info()
        else:
            self.selected_id = None
            self.view_btn.Disable()
            self.info_label.SetLabel("No node selected")
        self.canvas.Refresh()

    def _on_double_click(self, evt):
        self._on_click(evt)
        if self.selected_id is not None:
            self._on_view(evt)

    def _update_info(self):
        # Get node if available
        node = self.node_map.get(self.selected_id)

        if node:
            # Count parents (nodes that have this node as child)
            parents = []
            for parent_id, parent in self.node_map.items():
                if self.selected_id in parent.children:
                    parents.append(parent_id)

            pcount = len(parents)
            ccount = len(node.children)

            node_type = node.type if hasattr(node, "type") else "unknown"
            self.info_label.SetLabel(
                f"Selected: {node.name} (Type: {node_type})\n"
                f"Connections: {pcount} parent(s), {ccount} child(ren)"
            )
        else:
            # Just ID information if we don't have the node object
            self.info_label.SetLabel(f"Selected: Node ID {self.selected_id}")

    def _on_view(self, evt):
        print("Looking up summary for node:", self.selected_id)
        if self.selected_id is None:
            return

        #  node = self.node_map.get(self.selected_id)
        # if not node:
        #     print("Not a node?")
        #     return

        msg = self.net.build_message(
            "GETSUMMARY",
            [
                str(
                    self.selected_id.id
                    if hasattr(self.selected_id, "id")
                    else self.selected_id
                )
            ],
        )
        self.net.send_message(msg)
        self.EndModal(wx.ID_OK)
