"""Tkinter GUI of the Advanced QR Code Generator."""

import os
import subprocess
import sys
import tkinter as tk
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.metadata import version as package_version
from pathlib import Path
from tkinter import colorchooser, filedialog, font, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

from aqrgen import __version__, clipboard, core, payloads, presets
from aqrgen.insert_dialog import InsertDialog

TITLE = "Advanced QR Code Generator"
"""Window and message box title."""

PREVIEW_SIZE = 300
"""Smallest width and height of the preview in pixels."""

MAX_PREVIEW_SIZE = 2 * PREVIEW_SIZE
"""Largest preview size, reached when the window is enlarged."""

PREVIEW_DELAY_MS = 300
"""Delay after the last change before the preview is redrawn."""

POLL_MS = 50
"""Interval for checking whether background work has finished."""

STATUS_MS = 3000
"""How long short status messages stay visible."""

TOOLTIP_DELAY_MS = 500
"""Delay before a tooltip appears."""

PAD = 5
"""Basic padding between widgets in pixels."""

MIN_LONG_ENTRY_WIDTH = 20
"""Smallest width in characters of entries that fill their group."""

MIN_MESSAGE_LINES = 3
"""Height of the message box in lines when it is (nearly) empty."""

IMAGE_FILETYPES = (
    ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
    ("All files", "*.*"),
)
"""File type filter of the image file dialogs."""

PRESET_FIELDS = (
    "message",
    "save_dir",
    "file_name",
    "on_collision",
    "version",
    "error_correction",
    "extension",
    "embed_image",
    "embedded_image_path",
    "logo_size",
    "back_color",
    "back_opacity",
    "front_color",
    "box_size",
    "border",
    "box_style",
    "eye_style",
    "color_mask",
    "mask_image_path",
    "edge_color",
)
"""Names of the variables stored in presets."""

ERROR_CORRECTION_OPTIONS = (
    ("L · 7 %", "L"),
    ("M · 15 %", "M"),
    ("Q · 25 %", "Q"),
    ("H · 30 %", "H"),
)
BOX_STYLE_OPTIONS = (
    ("Square", "square"),
    ("Gapped square", "gapsquare"),
    ("Rounded", "rounded"),
    ("Circle", "circle"),
    ("Gapped circle", "gapcircle"),
    ("Vertical bars", "vbars"),
    ("Horizontal bars", "hbars"),
)
ERROR_CORRECTION_TIPS = {
    "L": "Low: still scans with about 7 % of the code damaged or covered. "
    "Gives the smallest code for the same message.",
    "M": "Medium: still scans with about 15 % damaged or covered. "
    "A good default.",
    "Q": "Quartile: still scans with about 25 % damaged or covered. "
    "For printed codes that may get dirty or worn.",
    "H": "High: still scans with about 30 % damaged or covered. "
    "The largest code; required when a logo is embedded.",
}
"""Tooltips of the error correction buttons."""

STYLE_LAYOUT = ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (0, 2), (1, 2))
"""Grid positions of the style buttons: squares, circles, bars."""
COLOR_MASK_OPTIONS = (
    ("Solid fill", "solid"),
    ("Radial gradient", "rgrad"),
    ("Square gradient", "sgrad"),
    ("Horizontal gradient", "hgrad"),
    ("Vertical gradient", "vgrad"),
    ("Image", "image"),
)


class Tooltip:
    """Small help text shown while the mouse rests on a widget.

    Parameters
    ----------
    widget : tkinter.Widget
        Widget the tooltip belongs to.
    text : str
        Help text.
    """

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        self._job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def _schedule(self, _event=None):
        """Show the tooltip after a short delay.

        Parameters
        ----------
        _event : tkinter.Event, optional
            The ``<Enter>`` event (unused).
        """
        self._cancel()
        self._job = self.widget.after(TOOLTIP_DELAY_MS, self.show)

    def _cancel(self):
        """Cancel a scheduled tooltip."""
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None

    def show(self):
        """Show the tooltip below the widget."""
        self._job = None
        if self.window is not None:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(
            f"+{self.widget.winfo_rootx() + 10}"
            f"+{self.widget.winfo_rooty() + self.widget.winfo_height() + 4}"
        )
        tk.Label(
            self.window,
            text=self.text,
            justify=tk.LEFT,
            wraplength=320,
            background="#ffffe0",
            foreground="black",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
        ).pack()

    def hide(self, _event=None):
        """Hide the tooltip, or cancel it if it isn't shown yet.

        Parameters
        ----------
        _event : tkinter.Event, optional
            The ``<Leave>`` or ``<ButtonPress>`` event (unused).
        """
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None


class QrCodeGeneratorApp:
    """Main window for interactive creation of QR codes.

    Parameters
    ----------
    root : tkinter.Tk
        Root window the app is built in.
    """

    def __init__(self, root):
        self.root = root
        self._executor = ThreadPoolExecutor(max_workers=2)
        # (user value, forced value) of constrained variables, see
        # _constrain; keyed by variable name
        self._saved = {}
        self._preview_job = None  # id of the scheduled preview update
        self._preview_running = False
        self._preview_outdated = False
        self._preview_photo = None  # reference keeps the image alive
        self._saving = False
        self._closed = False
        self._insert_values = {}  # last form values per message type
        self.insert_dialog = None

        self._create_variables()
        root.title(f"{TITLE} by Jan Klíma")
        root.report_callback_exception = self._report_exception
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-Return>", lambda _event: self.generate())
        root.bind(
            "<Control-Shift-Return>", lambda _event: self.copy_to_clipboard()
        )

        self._build_header(root)
        columns = ttk.Frame(root, padding=(PAD, 0, PAD, 2 * PAD))
        columns.grid(column=0, row=1, sticky=tk.NSEW)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        # only the right column (preview) takes extra space
        left, middle, right = (
            _column(columns, index, weight)
            for index, weight in enumerate((0, 0, 1))
        )
        columns.rowconfigure(0, weight=1)
        self._left_column = left
        self._build_content(left)
        self._build_colors(left)
        self._build_styles(middle)
        self._build_logo(middle)
        self._build_preview(right)
        self._build_save(right)

        self._update_states()
        for attr in PRESET_FIELDS:
            if attr not in ("save_dir", "file_name", "on_collision"):
                getattr(self, attr).trace_add(
                    "write", lambda *_: self._schedule_preview()
                )
        self._schedule_preview()
        self.message_entry.focus()
        root.update_idletasks()
        for column in (left, middle, right):
            _fit_groups_to_column(column)
        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())
        root.after_idle(self._import_legacy_presets)

    # --- construction ------------------------------------------------

    def _create_variables(self):
        """Create the tkinter variables holding all settings."""
        self.message = tk.StringVar()
        self.save_dir = tk.StringVar()
        self.file_name = tk.StringVar()
        self.on_collision = tk.StringVar(value="ask")
        self.version = tk.IntVar(value=1)
        self.error_correction = tk.StringVar(value="M")
        self.extension = tk.StringVar(value=".png")
        self.embed_image = tk.BooleanVar(value=False)
        self.embedded_image_path = tk.StringVar()
        self.logo_size = tk.IntVar(value=25)  # percent of the width
        self.back_color = tk.StringVar(value="(255, 255, 255)")
        self.back_opacity = tk.IntVar(value=100)  # percent
        self.front_color = tk.StringVar(value="(0, 0, 0)")
        self.box_size = tk.IntVar(value=10)
        self.border = tk.IntVar(value=4)
        self.box_style = tk.StringVar(value="square")
        self.eye_style = tk.StringVar(value="square")
        self.color_mask = tk.StringVar(value="solid")
        self.mask_image_path = tk.StringVar()
        self.edge_color = tk.StringVar(value="(0, 0, 255)")
        self.preset_name = tk.StringVar()
        self.status = tk.StringVar()

    def _build_header(self, root):
        """Build the title, the version line and the preset bar.

        Parameters
        ----------
        root : tkinter.Tk
            Root window.
        """
        frame = ttk.Frame(root, padding=(2 * PAD, PAD))
        frame.grid(column=0, row=0, sticky=tk.EW)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=TITLE, font=("Courier", 18, "bold")).grid(
            column=0, row=0, sticky=tk.W
        )
        ttk.Label(
            frame,
            text=f"by Jan Klíma · version {__version__} · qrcode "
            f"{package_version('qrcode')}",
            font=("Courier", 10),
        ).grid(column=0, row=1, sticky=tk.W)
        bar = ttk.Frame(frame)
        bar.grid(column=2, row=0, rowspan=2, sticky=tk.E)
        ttk.Label(bar, text="Preset:").grid(column=0, row=0)
        self.preset_combo = ttk.Combobox(
            bar,
            width=25,
            textvariable=self.preset_name,
            postcommand=self._reload_preset_list,
        )
        self.preset_combo.grid(column=1, row=0, padx=PAD)
        for column, text, command in (
            (2, "Load", self.load_preset),
            (3, "Save", self.save_preset),
            (4, "Delete", self.delete_preset),
            (5, "Open folder", self.open_presets_folder),
        ):
            ttk.Button(bar, text=text, command=command).grid(
                column=column, row=0, padx=(0, PAD)
            )
        self._reload_preset_list()

    def _build_content(self, column):
        """Build the message, size standard and error correction inputs.

        Parameters
        ----------
        column : tkinter.ttk.Frame
            Left column of the window.
        """
        frame = _group(column, "Content")
        self._build_message(frame)
        _spinbox_row(
            frame,
            "Size standard (1–40, 1 = 21×21 boxes):",
            self.version,
            (1, 40, 1),
        )
        _add(
            frame,
            ttk.Label(frame, text="Error correction (can recover):"),
            pady=(PAD, 0),
        )
        self._error_correction_buttons = _radio_group(
            frame, self.error_correction, ERROR_CORRECTION_OPTIONS, 4
        )
        for value, button in self._error_correction_buttons.items():
            button.tooltip = Tooltip(button, ERROR_CORRECTION_TIPS[value])

        frame = _group(column, "Dimensions")
        _spinbox_row(
            frame, "Box size (pixels per box):", self.box_size, (1, 100, 1)
        )
        _spinbox_row(
            frame, "Border (boxes, 4 recommended):", self.border, (0, 20, 1)
        )

    def _build_message(self, frame):
        """Build the multi-line message input and its Insert menu.

        Parameters
        ----------
        frame : tkinter.ttk.Frame
            Body of the Content group.
        """
        header = _add(frame, ttk.Frame(frame), sticky=tk.EW)
        header.columnconfigure(0, weight=1)
        _grid(ttk.Label(header, text="Message/URL to encode:"), 0, 0)
        button = ttk.Menubutton(header, text="Insert…")
        self.insert_menu = tk.Menu(button, tearoff=False)
        for payload_type in payloads.PAYLOAD_TYPES:
            self.insert_menu.add_command(
                label=payload_type.title + "…",
                command=lambda t=payload_type: self.open_insert_dialog(t),
            )
        button["menu"] = self.insert_menu
        button.grid(column=1, row=0, sticky=tk.E)
        button.tooltip = Tooltip(
            button,
            "Fill in the message from a form: Wi-Fi network, contact, "
            "e-mail, SMS, phone call, WhatsApp, location, calendar event "
            "or payment.",
        )
        line = _add(frame, ttk.Frame(frame), sticky=tk.EW)
        line.columnconfigure(0, weight=1)
        self.message_entry = tk.Text(
            line,
            width=MIN_LONG_ENTRY_WIDTH,
            height=MIN_MESSAGE_LINES,
            wrap="char",
            undo=True,
            font="TkDefaultFont",
        )
        self.message_entry.grid(column=0, row=0, sticky=tk.EW)
        self._message_scrollbar = ttk.Scrollbar(
            line, orient=tk.VERTICAL, command=self.message_entry.yview
        )
        self._message_scrollbar.grid(column=1, row=0, sticky=tk.NS)
        self._message_scrollbar.grid_remove()  # shown when needed
        self.message_entry.configure(yscrollcommand=self._message_scrollbar.set)
        _link_text(self.message_entry, self.message)
        # grow with the content, and use space the window gains
        self.message.trace_add(
            "write", lambda *_: self.root.after_idle(self._fit_message_height)
        )
        self._left_column.bind("<Configure>", self._fit_message_height)
        # keep the shortcuts and Tab working inside the text box
        for sequence, action in (
            ("<Control-Return>", self.generate),
            ("<Control-Shift-Return>", self.copy_to_clipboard),
            ("<Tab>", lambda: self.message_entry.tk_focusNext().focus_set()),
            (
                "<Shift-Tab>",
                lambda: self.message_entry.tk_focusPrev().focus_set(),
            ),
        ):
            self.message_entry.bind(sequence, _instead_of_default(action))

    def _fit_message_height(self, _event=None):
        """Fit the message box to its content, as far as there is room.

        The box grows by lines (wrapped lines included) until the left
        column is as tall as the space it has, i.e. the tallest column;
        beyond that a scrollbar appears.

        Parameters
        ----------
        _event : tkinter.Event, optional
            The ``<Configure>`` event of the left column (unused).
        """
        if self._closed:
            return
        text = self.message_entry
        lines = _display_lines(text)
        line_height = font.nametofont("TkDefaultFont").metrics("linespace")
        current = int(text.cget("height"))
        box_height = text.winfo_reqheight()
        frame_height = box_height - current * line_height  # borders
        room = self._left_column.winfo_height() - (
            self._left_column.winfo_reqheight() - box_height
        )
        most = max(MIN_MESSAGE_LINES, (room - frame_height) // line_height)
        height = max(MIN_MESSAGE_LINES, min(lines, most))
        if height != current:
            text.configure(height=height)
        if lines > height:
            self._message_scrollbar.grid()
        else:
            self._message_scrollbar.grid_remove()

    def open_insert_dialog(self, payload_type):
        """Open the form of a message type.

        Parameters
        ----------
        payload_type : type
            One of `aqrgen.payloads.PAYLOAD_TYPES`.
        """
        self.insert_dialog = InsertDialog(
            self.root,
            payload_type,
            lambda text, values: self._insert_message(
                payload_type, text, values
            ),
            self._insert_values.get(payload_type),
        )

    def _insert_message(self, payload_type, text, values):
        """Put a message built by the Insert form into the message box.

        Parameters
        ----------
        payload_type : type
            The message type that was filled in.
        text : str
            The built message.
        values : dict
            Form values, remembered for the next use of the form.
        """
        self._insert_values[payload_type] = values
        self.message.set(text)
        self.message_entry.focus_set()

    def _build_colors(self, column):
        """Build the background, opacity and face color inputs.

        Parameters
        ----------
        column : tkinter.ttk.Frame
            Left column of the window.
        """
        frame = _group(column, "Colors")
        self._color_input(
            frame,
            "Background, e.g. (255, 255, 255) or #ffffff:",
            self.back_color,
        )
        _spinbox_row(
            frame,
            "Background opacity (%, 0 = transparent):",
            self.back_opacity,
            (0, 100, 10),
        )
        self._face_widgets = self._color_input(
            frame, "Face, e.g. (0, 0, 0) or #000000:", self.front_color
        )

    def _build_styles(self, column):
        """Build the box style, eye style and color mask inputs.

        Parameters
        ----------
        column : tkinter.ttk.Frame
            Middle column of the window.
        """
        styles = _radio_group(
            _group(column, "Box style"),
            self.box_style,
            BOX_STYLE_OPTIONS,
            STYLE_LAYOUT,
            self._update_states,
        )
        eyes = _radio_group(
            _group(column, "Eye style (the 3 corner squares)"),
            self.eye_style,
            BOX_STYLE_OPTIONS,
            STYLE_LAYOUT,
            self._update_states,
        )
        frame = _group(column, "Color mask")
        masks = _radio_group(
            frame, self.color_mask, COLOR_MASK_OPTIONS, 3, self._update_states
        )
        edge = _add(frame, ttk.Frame(frame), pady=(PAD, 0))
        self._edge_widgets = [
            _grid(ttk.Label(edge, text="2nd color:"), 0, 0),
            _grid(
                ttk.Entry(edge, width=16, textvariable=self.edge_color),
                1,
                0,
                padx=PAD,
            ),
            _grid(
                ttk.Button(
                    edge,
                    text="Palette…",
                    command=lambda: self._pick_color(self.edge_color),
                ),
                2,
                0,
            ),
        ]
        self._mask_image_widgets = _labeled_entry(
            frame,
            "Image mask path:",
            self.mask_image_path,
            None,
            (
                "Browse…",
                lambda: self._browse_image(self.mask_image_path, "Image mask"),
            ),
        )
        self._style_buttons, self._eye_buttons = styles, eyes
        self._mask_buttons = masks
        self._png_only_widgets = [
            button
            for buttons, allowed in (
                (styles, core.SVG_DRAWERS),
                (eyes, core.SVG_DRAWERS),
                (masks, core.SVG_GRADIENTS),
            )
            for value, button in buttons.items()
            if value not in allowed
        ]

    def _build_logo(self, column):
        """Build the embedded image inputs.

        Parameters
        ----------
        column : tkinter.ttk.Frame
            Middle column of the window.
        """
        frame = _group(column, "Logo")
        _add(
            frame,
            ttk.Checkbutton(
                frame,
                text="Embed an image in the center (uses error correction H)",
                variable=self.embed_image,
                command=self._update_states,
            ),
        )
        self._embed_widgets = _labeled_entry(
            frame,
            "Image path:",
            self.embedded_image_path,
            None,
            (
                "Browse…",
                lambda: self._browse_image(
                    self.embedded_image_path, "Image to embed"
                ),
            ),
        ) + _spinbox_row(
            frame,
            "Logo size (% of width, 25 recommended):",
            self.logo_size,
            (5, 50, 5),
        )

    def _build_preview(self, column):
        """Build the preview area, which grows with the window.

        Parameters
        ----------
        column : tkinter.ttk.Frame
            Right column of the window.
        """
        frame = _group(column, "Preview")
        self._preview_column = column
        self._preview_size = PREVIEW_SIZE
        self._preview_box = ttk.Frame(
            frame,
            width=PREVIEW_SIZE + 4,
            height=PREVIEW_SIZE + 4,
            relief="sunken",
            borderwidth=2,
        )
        _add(frame, self._preview_box)
        self._preview_box.grid_propagate(False)
        self._preview_box.columnconfigure(0, weight=1)
        self._preview_box.rowconfigure(0, weight=1)
        self.preview_label = ttk.Label(
            self._preview_box,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            wraplength=PREVIEW_SIZE,
        )
        self.preview_label.grid(column=0, row=0)
        column.bind("<Configure>", self._on_preview_area_resized)

    def _build_save(self, column):
        """Build the format, folder and name inputs and Generate.

        Parameters
        ----------
        column : tkinter.ttk.Frame
            Right column of the window.
        """
        frame = _group(column, "Save")
        _add(frame, ttk.Label(frame, text="Format:"))
        _radio_group(
            frame,
            self.extension,
            (("PNG", ".png"), ("SVG (fewer styles and color masks)", ".svg")),
            2,
            self._update_states,
        )
        self._save_dir_widgets = _labeled_entry(
            frame,
            "Folder:",
            self.save_dir,
            None,
            ("Browse…", self._browse_save_dir),
        )
        name = _add(frame, ttk.Frame(frame), pady=(PAD, 0))
        _grid(ttk.Label(name, text="Name:"), 0, 0)
        _grid(
            ttk.Entry(name, width=18, textvariable=self.file_name),
            1,
            0,
            padx=PAD,
        )
        _grid(ttk.Label(name, text="If it exists:"), 2, 0)
        collision = ttk.Combobox(
            name,
            textvariable=self.on_collision,
            width=12,
            values=("ask", "overwrite", "warn & abort"),
        )
        collision.state(["readonly"])
        _grid(collision, 3, 0, padx=(PAD, 0))
        actions = _add(frame, ttk.Frame(frame), sticky="", pady=(2 * PAD, 0))
        self.generate_button = ttk.Button(
            actions, text="Generate QR code", command=self.generate
        )
        self.copy_button = ttk.Button(
            actions,
            text="Copy PNG to clipboard",
            command=self.copy_to_clipboard,
        )
        self.copy_button.tooltip = Tooltip(
            self.copy_button,
            "Copies the QR code as a PNG image (also when SVG is "
            "selected), e.g. to paste it into a document or a chat.",
        )
        for index, (button, keys) in enumerate(
            (
                (self.generate_button, "Ctrl+Enter"),
                (self.copy_button, "Ctrl+Shift+Enter"),
            )
        ):
            button.grid(column=index, row=0, padx=PAD, ipadx=10, ipady=5)
            ttk.Label(actions, text=keys, foreground="gray").grid(
                column=index, row=1
            )
        _add(frame, ttk.Label(frame, textvariable=self.status), sticky="")
        # extra height goes below the Save group
        filler = ttk.Frame(column)
        filler.grid(column=0, row=_next_row(column))
        column.rowconfigure(filler.grid_info()["row"], weight=1)

    def _color_input(self, frame, text, var):
        """Build a labeled color entry with a palette button.

        Parameters
        ----------
        frame : tkinter.ttk.Frame
            Frame to build the widgets in.
        text : str
            Label text.
        var : tkinter.StringVar
            Variable holding the color.

        Returns
        -------
        list of tkinter.ttk.Widget
            The label, the entry and the button.
        """
        return _labeled_entry(
            frame, text, var, 28, ("Palette…", lambda: self._pick_color(var))
        )

    # --- widget states -----------------------------------------------

    def _update_states(self):
        """Enable, disable and constrain widgets according to settings.

        For SVG, box and eye styles and color masks that SVG doesn't
        support are replaced by square and solid fill; an embedded
        image forces error correction H. The user's values come back
        when the constraint goes away, see `_constrain`.
        """
        svg = self.extension.get() == ".svg"
        embed = self.embed_image.get()
        self._constrain(
            self.box_style, core.SVG_DRAWERS if svg else None, "square"
        )
        self._constrain(
            self.eye_style, core.SVG_DRAWERS if svg else None, "square"
        )
        self._constrain(
            self.color_mask, core.SVG_GRADIENTS if svg else None, "solid"
        )
        self._constrain(self.error_correction, "H" if embed else None, "H")
        mask = self.color_mask.get()
        _set_enabled(self._png_only_widgets, not svg)
        _set_enabled(self._embed_widgets, embed)
        _set_enabled(self._mask_image_widgets, mask == "image")
        _set_enabled(self._face_widgets, mask != "image")
        _set_enabled(self._edge_widgets, mask not in ("solid", "image"))
        _set_enabled(
            [b for v, b in self._error_correction_buttons.items() if v != "H"],
            not embed,
        )

    def _constrain(self, var, allowed, fallback):
        """Keep a variable within allowed values, remembering its value.

        If the value is not allowed, it is replaced by the fallback.
        Once the original value is allowed again it comes back, unless
        the user picked another value in the meantime.

        Parameters
        ----------
        var : tkinter.Variable
            Variable to constrain.
        allowed : collection or None
            Allowed values, or None to allow every value.
        fallback : object
            Value used while the original value is not allowed.
        """
        key = str(var)
        if key in self._saved:
            original, forced = self._saved.pop(key)
            if var.get() == forced:  # untouched since it was forced
                if allowed is None or original in allowed:
                    var.set(original)
                else:
                    self._saved[key] = (original, forced)
                return
        if allowed is not None and var.get() not in allowed:
            self._saved[key] = (var.get(), fallback)
            var.set(fallback)

    def _unconstrained_value(self, var):
        """Return the value a variable would have without constraints.

        Parameters
        ----------
        var : tkinter.Variable
            Variable to read.

        Returns
        -------
        object
            The user's value from before a constraint, else the
            current value.
        """
        original, forced = self._saved.get(str(var), (None, None))
        current = var.get()
        return (
            original
            if str(var) in self._saved and current == forced
            else current
        )

    # --- settings ----------------------------------------------------

    def collect_settings(self):
        """Read all inputs into a settings object.

        Returns
        -------
        aqrgen.core.QrSettings
            The current settings. Colors the selected format and mask
            do not use are left at their defaults.

        Raises
        ------
        ValueError
            With a user-readable message if an input is invalid.
        """
        mask = self.color_mask.get()
        embed = self.embed_image.get()
        colors = {
            "back_color": _read_color(self.back_color, "Background"),
            "back_opacity": _read_int(self.back_opacity, "Background opacity")
            / 100,
        }
        if mask != "image":
            colors["front_color"] = _read_color(self.front_color, "Face")
        if mask not in ("solid", "image"):
            colors["edge_color"] = _read_color(self.edge_color, "2nd")
        logo = {}
        if embed:
            logo = {
                "embedded_image_path": self.embedded_image_path.get(),
                "logo_ratio": _read_int(self.logo_size, "Logo size") / 100,
            }
        return core.QrSettings(
            data=self.message.get(),
            version=_read_int(self.version, "Size standard"),
            error_correction=self.error_correction.get(),
            extension=self.extension.get(),
            box_size=_read_int(self.box_size, "Box size"),
            border=_read_int(self.border, "Border size"),
            box_style=self.box_style.get(),
            eye_style=self.eye_style.get(),
            color_mask=mask,
            mask_image_path=self.mask_image_path.get() or None,
            **colors,
            **logo,
        )

    # --- generating and saving ---------------------------------------

    def is_busy(self):
        """Tell whether a preview, save or copy is pending or running.

        Returns
        -------
        bool
            True while background work is pending or running.
        """
        return (
            self._saving
            or self._preview_running
            or self._preview_job is not None
        )

    def generate(self):
        """Generate the QR code and save it in the background."""
        if self._saving:
            return
        try:
            settings = self.collect_settings()
        except ValueError as err:
            self._warn(str(err))
            return
        target = self._choose_target()
        if target is None:
            return
        self._set_saving(True)
        future = self._executor.submit(_render_and_save, settings, target)
        self._when_done(future, self._finish_generate)

    def _choose_target(self):
        """Ask for missing information and resolve file name clashes.

        Returns
        -------
        pathlib.Path or None
            Path to save the QR code to, or None to cancel.
        """
        if not self.save_dir.get():
            if not messagebox.askyesno(
                f"Overwrite save directory - {TITLE}",
                "You did not specify the saving directory. Do you want to "
                "use current directory?",
            ):
                self._warn("No saving path entered! Image not saved.")
                return None
            self.save_dir.set(os.getcwd())
        if not Path(self.save_dir.get()).is_dir():
            self._warn(f"Directory {self.save_dir.get()!r} does not exist.")
            return None
        if not self.file_name.get():
            self._warn("Please enter a QR code name.")
            return None
        target = core.output_path(
            self.save_dir.get(), self.file_name.get(), self.extension.get()
        )
        if not target.exists() or self.on_collision.get() == "overwrite":
            return target
        if self.on_collision.get() == "ask":
            overwrite = messagebox.askyesno(
                f"Overwrite - {TITLE}",
                "Image with this name already exists within the specified "
                "location. Do you want to overwrite it?",
            )
            return target if overwrite else None
        self._warn(
            "Image with this name already exists within the specified "
            "location! QR code generation aborted."
        )
        return None

    def _finish_generate(self, future):
        """Report the result of a background save.

        Parameters
        ----------
        future : concurrent.futures.Future
            Finished future returned by `_render_and_save`.
        """
        self._set_saving(False)
        try:
            path = future.result()
        except ValueError as err:
            self._warn(str(err))
        except OSError as err:
            self._warn(f"Saving failed: {err}")
        else:
            messagebox.showinfo(f"Info - {TITLE}", f"QR code saved to\n{path}")

    def _set_saving(self, saving, message="Generating…"):
        """Switch the window between the idle and the working state.

        Parameters
        ----------
        saving : bool
            Whether a save or copy is running.
        message : str, default "Generating…"
            Status shown while working.
        """
        self._saving = saving
        for button in (self.generate_button, self.copy_button):
            button.state(["disabled" if saving else "!disabled"])
        self.status.set(message if saving else "")

    def copy_to_clipboard(self):
        """Render the QR code as PNG and copy it to the clipboard."""
        if self._saving:
            return
        try:
            settings = self.collect_settings()
        except ValueError as err:
            self._warn(str(err))
            return
        self._set_saving(True, "Copying…")
        future = self._executor.submit(_render_png, settings)
        self._when_done(future, self._finish_copy)

    def _finish_copy(self, future):
        """Put a rendered QR code on the clipboard.

        Parameters
        ----------
        future : concurrent.futures.Future
            Finished future returned by `_render_png`.
        """
        self._set_saving(False)
        try:
            clipboard.copy_image(future.result())
        except ValueError as err:
            self._warn(str(err))
        except clipboard.ClipboardError as err:
            self._warn(f"Copying to the clipboard failed: {err}")
        else:
            self._flash_status("QR code copied to the clipboard as PNG.")

    def _flash_status(self, message):
        """Show a status message for a few seconds.

        Parameters
        ----------
        message : str
            Text to show.
        """
        self.status.set(message)
        self.root.after(STATUS_MS, self._clear_status, message)

    def _clear_status(self, message):
        """Clear the status line if it still shows a message.

        Parameters
        ----------
        message : str
            The message to clear; newer messages are kept.
        """
        if self.status.get() == message:
            self.status.set("")

    # --- preview -----------------------------------------------------

    def _on_preview_area_resized(self, event):
        """Fit the preview into its column, from 1 to 2 times its size.

        Parameters
        ----------
        event : tkinter.Event
            The ``<Configure>`` event of the right column.
        """
        # height of everything in the column except the preview itself
        others = self._preview_column.winfo_reqheight() - (
            self._preview_size + 4
        )
        available = min(event.width, event.height - others) - 4
        size = max(PREVIEW_SIZE, min(MAX_PREVIEW_SIZE, available))
        if abs(size - self._preview_size) >= 8:
            self._preview_size = size
            self._preview_box.configure(width=size + 4, height=size + 4)
            self.preview_label.configure(wraplength=size)
            self._schedule_preview()

    def _schedule_preview(self):
        """Redraw the preview shortly after the last change."""
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
        self._preview_job = self.root.after(
            PREVIEW_DELAY_MS, self._start_preview
        )

    def _start_preview(self):
        """Start rendering the preview in the background."""
        self._preview_job = None
        if self._preview_running:
            self._preview_outdated = True
            return
        if not self.message.get():
            self._show_preview(text="Enter a message to see a preview.")
            return
        try:
            settings = self.collect_settings()
        except ValueError as err:
            self._show_preview(text=str(err))
            return
        self._preview_running = True
        future = self._executor.submit(
            core.make_preview, settings, self._preview_size
        )
        self._when_done(future, self._finish_preview)

    def _finish_preview(self, future):
        """Show a rendered preview, then render again if outdated.

        Parameters
        ----------
        future : concurrent.futures.Future
            Finished future returned by `aqrgen.core.make_preview`.
        """
        self._preview_running = False
        try:
            image = future.result()
        except ValueError as err:
            self._show_preview(text=str(err))
        except Exception as err:  # never let the preview crash
            self._show_preview(text=f"Preview failed:\n{err}")
        else:
            self._show_preview(image=image)
        if self._preview_outdated:
            self._preview_outdated = False
            self._start_preview()

    def _show_preview(self, image=None, text=""):
        """Show an image or a message in the preview area.

        Parameters
        ----------
        image : PIL.Image.Image, optional
            Preview image.
        text : str, optional
            Message shown instead of an image.
        """
        if image is not None and image.mode == "RGBA":
            # show transparency on a checkerboard
            image = Image.alpha_composite(_checkerboard(image.size), image)
        self._preview_photo = ImageTk.PhotoImage(image) if image else None
        self.preview_label.configure(image=self._preview_photo or "", text=text)

    def _when_done(self, future, callback):
        """Call a function in the GUI thread once a future is done.

        The callback always runs from the Tk event loop, so errors in
        it reach `_report_exception`.

        Parameters
        ----------
        future : concurrent.futures.Future
            Future of the background work.
        callback : callable
            Called with the future as its only argument.
        """

        def check():
            """Run the callback if the future is done, else wait."""
            if self._closed:
                return
            if future.done():
                callback(future)
            else:
                self.root.after(POLL_MS, check)

        self.root.after(POLL_MS, check)

    # --- dialogs -----------------------------------------------------

    def _pick_color(self, var):
        """Let the user choose a color in a dialog.

        Parameters
        ----------
        var : tkinter.StringVar
            Variable receiving the color as an RGB triplet. It is left
            unchanged if the dialog is cancelled.
        """
        try:
            initial = core.parse_color(var.get())
        except ValueError:
            initial = None
        rgb, _ = colorchooser.askcolor(initialcolor=initial)
        if rgb is not None:
            var.set(str(tuple(int(c) for c in rgb)))

    def _browse_save_dir(self):
        """Let the user choose the save directory in a dialog."""
        path = filedialog.askdirectory(
            title="Location to save the QR code at",
            initialdir=self.save_dir.get() or os.getcwd(),
        )
        if path:
            self.save_dir.set(path)

    def _browse_image(self, var, title):
        """Let the user choose an image file in a dialog.

        Parameters
        ----------
        var : tkinter.StringVar
            Variable receiving the path. It is left unchanged if the
            dialog is cancelled.
        title : str
            Dialog title.
        """
        path = filedialog.askopenfilename(
            title=title,
            filetypes=IMAGE_FILETYPES,
            initialdir=Path(var.get()).parent if var.get() else os.getcwd(),
        )
        if path:
            var.set(path)

    def _warn(self, message):
        """Show a warning message box.

        Parameters
        ----------
        message : str
            Text of the warning.
        """
        messagebox.showwarning(f"Warning - {TITLE}", message)

    def _report_exception(self, exc_type, exc, tb):
        """Show unexpected errors in a dialog instead of the console.

        Parameters
        ----------
        exc_type : type
            Exception class.
        exc : BaseException
            The exception.
        tb : types.TracebackType
            Its traceback.
        """
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        messagebox.showerror(
            f"Error - {TITLE}", f"Unexpected error:\n\n{details}"
        )

    # --- presets -----------------------------------------------------

    def load_preset(self):
        """Load the preset named in the preset dropdown."""
        name = self.preset_name.get()
        try:
            values = presets.read_preset(name)
        except FileNotFoundError:
            self._warn(f"There is no preset named {name!r}.")
            return
        except ValueError as err:
            self._warn(str(err))
            return
        self._saved.clear()
        invalid = []
        for attr in PRESET_FIELDS:
            if attr not in values:
                continue
            var = getattr(self, attr)
            try:
                var.set(_check_preset_value(var, values[attr]))
            except ValueError:
                invalid.append(f"{attr}: {values[attr]!r}")
        self._update_states()
        if invalid:
            self._warn(
                "These values could not be loaded, check them in the "
                "preset file:\n" + "\n".join(invalid)
            )
        else:
            messagebox.showinfo(
                f"Info - {TITLE}", f"Preset {name!r} loaded successfully!"
            )

    def save_preset(self):
        """Save the current settings under the name in the dropdown.

        Locked values are saved as they were before the lock.
        """
        name = self.preset_name.get()
        try:
            exists = presets.preset_path(name).exists()
        except ValueError as err:
            self._warn(str(err))
            return
        if exists and not messagebox.askyesno(
            f"Overwrite - {TITLE}",
            f"Preset {name!r} already exists. Do you want to overwrite it?",
        ):
            return
        values = {}
        for attr in PRESET_FIELDS:
            var = getattr(self, attr)
            try:
                values[attr] = self._unconstrained_value(var)
            except tk.TclError:  # e.g. text in a number entry
                values[attr] = str(self.root.getvar(str(var)))
        presets.write_preset(name, values)
        self._reload_preset_list()
        messagebox.showinfo(
            f"Info - {TITLE}", f"Preset {name!r} saved successfully!"
        )

    def delete_preset(self):
        """Delete the preset named in the preset dropdown."""
        name = self.preset_name.get()
        title = f"Delete preset - {TITLE}"
        try:
            exists = presets.preset_path(name).exists()
        except ValueError as err:
            self._warn(str(err))
            return
        if not exists:
            messagebox.showinfo(title, f"There is no preset named {name!r}.")
            return
        if messagebox.askyesno(
            title, f"Do you REALLY want to delete preset {name!r}?"
        ):
            presets.delete_preset(name)
            self.preset_name.set("")
            self._reload_preset_list()
            messagebox.showinfo(title, f"Preset {name!r} deleted.")

    def open_presets_folder(self):
        """Open the presets folder in the system's file manager."""
        _open_in_file_manager(presets.ensure_presets_dir())

    def _reload_preset_list(self):
        """Fill the preset dropdown with the names of all presets."""
        self.preset_combo["values"] = presets.list_presets()

    def _import_legacy_presets(self):
        """Import old ``.txt`` presets and tell the user about it."""
        try:
            imported = presets.import_legacy_presets()
        except OSError as err:
            self._warn(f"Old presets could not be imported: {err}")
            return
        if imported:
            self._reload_preset_list()
            messagebox.showinfo(
                f"Presets imported - {TITLE}",
                f"Imported {len(imported)} preset(s) from the old "
                f"'presets' folder:\n{', '.join(imported)}\n\nThey are "
                f"now stored in:\n{presets.PRESETS_DIR}\n\nThe old files "
                "were left untouched.",
            )

    # --- shutdown ----------------------------------------------------

    def close(self):
        """Stop background work and close the window."""
        self._closed = True
        if self._preview_job is not None:
            self.root.after_cancel(self._preview_job)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def _column(parent, index, weight):
    """Create one of the three main columns.

    Parameters
    ----------
    parent : tkinter.ttk.Frame
        Frame holding the columns.
    index : int
        Grid column.
    weight : int
        Share of extra width the column takes when the window grows.

    Returns
    -------
    tkinter.ttk.Frame
        The column frame.
    """
    frame = ttk.Frame(parent)
    frame.grid(column=index, row=0, sticky=tk.NSEW, padx=PAD)
    frame.columnconfigure(0, weight=1)
    parent.columnconfigure(index, weight=weight)
    return frame


def _link_text(text, var):
    """Keep a multi-line Text widget and a StringVar in sync.

    Parameters
    ----------
    text : tkinter.Text
        The text widget.
    var : tkinter.StringVar
        Variable holding the same text.
    """

    def from_var(*_args):
        """Show the variable's value in the widget if it differs.

        Parameters
        ----------
        *_args
            Trace callback arguments (unused).
        """
        if text.get("1.0", "end-1c") != var.get():
            text.delete("1.0", "end")
            text.insert("1.0", var.get())
        text.edit_modified(False)

    def from_text(_event):
        """Store the widget's text in the variable after an edit.

        Parameters
        ----------
        _event : tkinter.Event
            The ``<<Modified>>`` event (unused).
        """
        if text.edit_modified():
            value = text.get("1.0", "end-1c")
            if value != var.get():
                var.set(value)
            text.edit_modified(False)

    var.trace_add("write", from_var)
    text.bind("<<Modified>>", from_text)
    from_var()


def _display_lines(text):
    """Count the lines a Text widget shows, wrapped lines included.

    Parameters
    ----------
    text : tkinter.Text
        The text widget.

    Returns
    -------
    int
        Number of display lines, at least 1.
    """
    try:
        result = text.count("1.0", "end-1c", "update", "displaylines")
    except tk.TclError:
        result = None
    if isinstance(result, tuple):  # Python < 3.13 returns a tuple
        result = result[0]
    if result is None:  # widget not laid out yet: count text lines
        return int(text.index("end-1c").split(".")[0])
    return result + 1


def _instead_of_default(action):
    """Wrap an action as an event handler that stops default handling.

    Parameters
    ----------
    action : callable
        Called without arguments.

    Returns
    -------
    callable
        Event handler returning ``"break"``.
    """

    def handler(_event):
        """Run the action and skip the widget's own handling.

        Parameters
        ----------
        _event : tkinter.Event
            The key event (unused).

        Returns
        -------
        str
            ``"break"``, which stops further handling of the event.
        """
        action()
        return "break"

    return handler


def _next_row(frame):
    """Return the first empty grid row of a frame.

    Parameters
    ----------
    frame : tkinter.Widget
        Frame using the grid geometry manager.

    Returns
    -------
    int
        Index of the first row below all placed widgets.
    """
    return frame.grid_size()[1]


def _add(frame, widget, **options):
    """Place a widget in the next free row of a one-column frame.

    Parameters
    ----------
    frame : tkinter.Widget
        Parent frame.
    widget : tkinter.Widget
        Widget to place.
    **options
        Further options of ``widget.grid``, e.g. ``sticky`` (default
        left-aligned) or ``pady``.

    Returns
    -------
    tkinter.Widget
        The widget, for chaining.
    """
    options.setdefault("sticky", tk.W)
    widget.grid(column=0, row=_next_row(frame), **options)
    return widget


def _group(column, title):
    """Create a titled group of inputs: a bold heading and a line.

    Parameters
    ----------
    column : tkinter.ttk.Frame
        Column frame the group is stacked into.
    title : str
        Heading text.

    Returns
    -------
    tkinter.ttk.Frame
        Body frame for the group's inputs, see `_fit_groups_to_column`.
    """
    row = _next_row(column)
    frame = ttk.Frame(column, padding=(0, PAD, 0, 0))
    # space between groups, but not above the first one
    frame.grid(
        column=0, row=row, sticky=tk.NSEW, pady=(2 * PAD if row else 0, 0)
    )
    frame.columnconfigure(0, weight=1)  # the separator fills the column
    bold = font.nametofont("TkDefaultFont").copy()
    bold.configure(weight="bold")
    heading = _add(frame, ttk.Label(frame, text=title, font=bold))
    heading.bold_font = bold  # keep a reference, fonts are not owned
    _add(frame, ttk.Separator(frame), sticky=tk.EW, pady=(0, PAD))
    frame.body = _add(frame, ttk.Frame(frame))
    frame.body.columnconfigure(0, weight=1)
    return frame.body


def _fit_groups_to_column(column):
    """Make every group body as wide as the column's default width.

    Long entries stretch to the body's width, so they use all of the
    column's default width but don't grow with the window.

    Parameters
    ----------
    column : tkinter.ttk.Frame
        Column frame, after its widgets have been laid out once.
    """
    width = column.winfo_reqwidth()
    for group in column.grid_slaves():
        body = getattr(group, "body", None)
        if body is not None:
            ttk.Frame(body, width=width, height=1).grid(
                column=0, row=_next_row(body)
            )


def _grid(widget, column, row, **options):
    """Place a widget in the grid, aligned to the left.

    Parameters
    ----------
    widget : tkinter.Widget
        Widget to place.
    column, row : int
        Grid position.
    **options
        Further options of ``widget.grid``.

    Returns
    -------
    tkinter.Widget
        The widget, for chaining.
    """
    widget.grid(column=column, row=row, sticky=tk.W, **options)
    return widget


def _labeled_entry(frame, text, var, width, button=None):
    """Add a label with an entry (and a button) in the row below.

    Parameters
    ----------
    frame : tkinter.ttk.Frame
        Frame to build the widgets in.
    text : str
        Label text.
    var : tkinter.StringVar
        Variable of the entry.
    width : int or None
        Width of the entry in characters, or None for an entry that
        fills the group's width (for long text like URLs and paths).
    button : tuple of (str, callable), optional
        Text and command of a button next to the entry.

    Returns
    -------
    list of tkinter.ttk.Widget
        The label, the entry and the button, if any.
    """
    label = _add(frame, ttk.Label(frame, text=text))
    if width is None:
        line = _add(frame, ttk.Frame(frame), sticky=tk.EW)
        line.columnconfigure(0, weight=1)
        entry = ttk.Entry(line, width=MIN_LONG_ENTRY_WIDTH, textvariable=var)
        entry.grid(column=0, row=0, sticky=tk.EW)
    else:
        line = _add(frame, ttk.Frame(frame))
        entry = _grid(ttk.Entry(line, width=width, textvariable=var), 0, 0)
    widgets = [label, entry]
    if button is not None:
        text, command = button
        widgets.append(
            _grid(
                ttk.Button(line, text=text, command=command),
                1,
                0,
                padx=(PAD, 0),
            )
        )
    return widgets


def _spinbox_row(frame, text, var, limits):
    """Add a label with a number spinbox next to it.

    Parameters
    ----------
    frame : tkinter.ttk.Frame
        Frame to build the widgets in.
    text : str
        Label text.
    var : tkinter.IntVar
        Variable of the spinbox.
    limits : tuple of int
        ``(lowest, highest, step)`` of the spinbox arrows. Typed
        values are checked when the settings are read.

    Returns
    -------
    list of tkinter.ttk.Widget
        The label and the spinbox.
    """
    low, high, step = limits
    line = _add(frame, ttk.Frame(frame), pady=1)
    return [
        _grid(ttk.Label(line, text=text), 0, 0),
        _grid(
            ttk.Spinbox(
                line,
                from_=low,
                to=high,
                increment=step,
                width=6,
                textvariable=var,
            ),
            1,
            0,
            padx=PAD,
        ),
    ]


def _radio_group(frame, var, options, layout, command=None):
    """Add radio buttons laid out in a grid.

    Parameters
    ----------
    frame : tkinter.ttk.Frame
        Frame to build the buttons in.
    var : tkinter.Variable
        Variable shared by the buttons.
    options : sequence of tuple of str
        ``(text, value)`` pairs, one per button.
    layout : int or sequence of tuple of int
        Number of buttons per row, or the ``(column, row)`` of each
        button.
    command : callable, optional
        Called when a button is clicked.

    Returns
    -------
    dict
        Buttons keyed by their value.
    """
    if isinstance(layout, int):
        layout = [(i % layout, i // layout) for i in range(len(options))]
    group = _add(frame, ttk.Frame(frame))
    buttons = {}
    for (text, value), (column, line) in zip(options, layout, strict=True):
        buttons[value] = _grid(
            ttk.Radiobutton(
                group, text=text, variable=var, value=value, command=command
            ),
            column,
            line,
            padx=(0, 2 * PAD),
        )
    return buttons


def _set_enabled(widgets, enabled):
    """Enable or disable ttk widgets.

    Parameters
    ----------
    widgets : iterable of tkinter.ttk.Widget
        Widgets to change.
    enabled : bool
        Whether the widgets should be enabled.
    """
    for widget in widgets:
        widget.state(["!disabled" if enabled else "disabled"])


def _read_int(var, label):
    """Read a whole number from an integer variable.

    Parameters
    ----------
    var : tkinter.IntVar
        Variable to read.
    label : str
        Name of the input, used in the error message.

    Returns
    -------
    int
        The number.

    Raises
    ------
    ValueError
        If the input is not a whole number.
    """
    try:
        return var.get()
    except tk.TclError:
        raise ValueError(f"{label} must be a whole number.") from None


def _read_color(var, label):
    """Read a color from a string variable.

    Parameters
    ----------
    var : tkinter.StringVar
        Variable to read.
    label : str
        Name of the color, used in the error message.

    Returns
    -------
    tuple of int
        The color as an ``(r, g, b)`` tuple.

    Raises
    ------
    ValueError
        If the input is not a valid color.
    """
    try:
        return core.parse_color(var.get())
    except ValueError as err:
        raise ValueError(f"{label} color: {err}") from None


def _check_preset_value(var, value):
    """Check that a value from a preset fits the variable's type.

    Parameters
    ----------
    var : tkinter.Variable
        Variable the value is meant for.
    value : object
        Value as read from the preset file.

    Returns
    -------
    bool or int or str
        The value, if it has the right type.

    Raises
    ------
    ValueError
        If the value has the wrong type for the variable.
    """
    if isinstance(var, tk.BooleanVar):
        expected = bool
    elif isinstance(var, tk.IntVar):
        expected = int
    else:
        expected = str
    # bool is a subclass of int, so rule it out for numbers explicitly
    if not isinstance(value, expected) or (
        expected is int and isinstance(value, bool)
    ):
        raise ValueError(f"expected {expected.__name__}")
    return value


def _open_in_file_manager(path):
    """Open a folder in the system's file manager.

    Parameters
    ----------
    path : pathlib.Path
        Folder to open.
    """
    if sys.platform == "win32":
        os.startfile(path)  # only exists on Windows
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, str(path)])


def _checkerboard(size, square=10):
    """Create a light gray checkerboard to show transparency on.

    Parameters
    ----------
    size : tuple of int
        Width and height in pixels.
    square : int, default 10
        Side of one checkerboard square in pixels.

    Returns
    -------
    PIL.Image.Image
        RGBA image of the checkerboard.
    """
    board = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], square):
        for x in range(y // square % 2 * square, size[0], 2 * square):
            draw.rectangle(
                (x, y, x + square - 1, y + square - 1), fill=(204, 204, 204)
            )
    return board


def _render_png(settings):
    """Render a QR code as a PIL image; runs in a worker thread.

    Parameters
    ----------
    settings : aqrgen.core.QrSettings
        Options of the QR code. SVG settings are rendered as PNG.

    Returns
    -------
    PIL.Image.Image
        The rendered QR code.
    """
    png = replace(settings, extension=".png")
    return core.make_qr_image(png).get_image()


def _render_and_save(settings, target):
    """Generate a QR code and save it; runs in a worker thread.

    Parameters
    ----------
    settings : aqrgen.core.QrSettings
        Options of the QR code.
    target : pathlib.Path
        File to save the QR code to.

    Returns
    -------
    pathlib.Path
        The saved file.
    """
    image = core.make_qr_image(settings)
    return core.save_qr_image(image, target.parent, target.stem, target.suffix)


def main():
    """Start the GUI and run its main loop."""
    root = tk.Tk()
    QrCodeGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
