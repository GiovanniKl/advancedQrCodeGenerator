"""Tkinter GUI of the Advanced QR Code Generator."""

import os
import subprocess
import sys
import tkinter as tk
import traceback
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version as package_version
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import ImageTk

from aqrgen import __version__, core, presets

TITLE = "Advanced QR Code Generator"
"""Window and message box title."""

PREVIEW_SIZE = 300
"""Width and height of the preview in pixels."""

PREVIEW_DELAY_MS = 300
"""Delay after the last change before the preview is redrawn."""

POLL_MS = 50
"""Interval for checking whether background work has finished."""

PAD = 5
"""Padding around each section."""

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
    ("L/low/7%", "L"),
    ("M/medium/15%", "M"),
    ("Q/quite-high/25%", "Q"),
    ("H/high/30%", "H"),
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
COLOR_MASK_OPTIONS = (
    ("Solid fill", "solid"),
    ("Radial gradient", "rgrad"),
    ("Square gradient", "sgrad"),
    ("Horizontal gradient", "hgrad"),
    ("Vertical gradient", "vgrad"),
    ("Image", "image"),
)


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

        self._create_variables()
        root.title(f"{TITLE} by Jan Klíma")
        root.report_callback_exception = self._report_exception
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-Return>", lambda _event: self.generate())

        main = ttk.Frame(root, padding="5 5 5 10")
        main.grid(column=0, row=0)
        self._build_heading(main)
        self._build_output_section(main)
        self._build_code_section(main)
        self._build_color_section(main)
        self._build_style_section(main)
        self._build_generate_section(main)
        self._build_presets_section(main)
        self._build_preview(main)

        self._update_states()
        for attr in PRESET_FIELDS:
            if attr not in ("save_dir", "file_name", "on_collision"):
                getattr(self, attr).trace_add(
                    "write", lambda *_: self._schedule_preview()
                )
        self._schedule_preview()
        self.message_entry.focus()
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

    def _build_heading(self, main):
        """Build the title and the version line.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        frame = ttk.Frame(main, padding=PAD)
        frame.grid(column=0, row=0, columnspan=9)
        ttk.Label(
            frame, text=f"{TITLE} by Jan Klíma", font=("Courier", 20, "bold")
        ).grid(column=0, row=0)
        ttk.Label(
            frame,
            text=f"Version {__version__}, using qrcode "
            f"{package_version('qrcode')}.",
            font=("Courier", 12),
        ).grid(column=0, row=1, sticky=tk.W)

    def _build_output_section(self, main):
        """Build the message, save location and file name inputs.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        frame = _section(main, column=0, row=1)
        ttk.Label(frame, text="Message/URL to encode:").grid(
            column=0, row=0, sticky=tk.W
        )
        self.message_entry = ttk.Entry(
            frame, width=50, textvariable=self.message
        )
        self.message_entry.grid(column=0, row=1, sticky=tk.W)

        frame = _section(main, column=0, row=2)
        ttk.Label(frame, text="Location to save the QR code at:").grid(
            column=0, row=0, sticky=tk.W
        )
        ttk.Entry(frame, width=50, textvariable=self.save_dir).grid(
            column=0, row=1, sticky=tk.W
        )
        ttk.Button(frame, text="Browse…", command=self._browse_save_dir).grid(
            column=1, row=1, sticky=tk.W, padx=PAD
        )

        frame = _section(main, column=0, row=3)
        ttk.Label(frame, text="QR code name:").grid(
            column=0, row=0, sticky=tk.W
        )
        ttk.Label(frame, text="On collision:").grid(
            column=1, row=0, sticky=tk.E
        )
        collision = ttk.Combobox(
            frame,
            textvariable=self.on_collision,
            width=14,
            values=("ask", "overwrite", "warn & abort"),
        )
        collision.state(["readonly"])
        collision.grid(column=2, row=0, sticky=tk.E)
        ttk.Entry(frame, width=50, textvariable=self.file_name).grid(
            column=0, row=1, sticky=tk.W, columnspan=3
        )

    def _build_code_section(self, main):
        """Build the size, error correction, format and logo inputs.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        frame = _section(main, column=0, row=4)
        ttk.Label(frame, text="Size standard from 1 to 40 (1 ~ 21x21):").grid(
            column=0, row=0, sticky=tk.W
        )
        ttk.Entry(frame, width=25, textvariable=self.version).grid(
            column=0, row=1, sticky=tk.W
        )

        frame = _section(main, column=0, row=5)
        ttk.Label(
            frame, text="Error correction standard/quality/can recover:"
        ).grid(column=0, row=0, columnspan=2, sticky=tk.W)
        self._error_correction_buttons = _radio_group(
            frame, self.error_correction, ERROR_CORRECTION_OPTIONS, columns=2
        )

        frame = _section(main, column=0, row=6)
        ttk.Label(frame, text="Image extension:").grid(
            column=0, row=0, columnspan=2, sticky=tk.W
        )
        _radio_group(
            frame,
            self.extension,
            (("PNG", ".png"), ("SVG (fewer styles and color masks)", ".svg")),
            columns=2,
            command=self._update_states,
        )

        frame = _section(main, column=0, row=7)
        embed_check = ttk.Checkbutton(
            frame,
            text="Embed an image in the center (uses error correction H).",
            variable=self.embed_image,
            command=self._update_states,
        )
        embed_check.grid(column=0, row=0, sticky=tk.W, columnspan=3)
        self._embed_widgets = (
            _grid(ttk.Label(frame, text="   Path:"), 0, 1),
            _grid(
                ttk.Entry(
                    frame, width=40, textvariable=self.embedded_image_path
                ),
                1,
                1,
            ),
            _grid(
                ttk.Button(
                    frame,
                    text="Browse…",
                    command=lambda: self._browse_image(
                        self.embedded_image_path, "Image to embed"
                    ),
                ),
                2,
                1,
                padx=PAD,
            ),
            _grid(
                ttk.Label(
                    frame, text="   Logo size (% of width, 25 recommended):"
                ),
                0,
                2,
                columnspan=2,
            ),
            _grid(
                ttk.Spinbox(
                    frame,
                    from_=5,
                    to=50,
                    increment=5,
                    width=6,
                    textvariable=self.logo_size,
                ),
                2,
                2,
                padx=PAD,
            ),
        )

    def _build_color_section(self, main):
        """Build the background and face color inputs.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        for row, label, var, example in (
            (1, "Background", self.back_color, "(255, 255, 255) or #ffffff"),
            (2, "Face", self.front_color, "(0, 0, 0) or #000000"),
        ):
            frame = _section(main, column=4, row=row)
            self._color_input(
                frame, f"{label} color, e.g. {example}:", var, width=30
            )

    def _build_style_section(self, main):
        """Build the box size, border, box style and color mask inputs.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        frame = _section(main, column=4, row=3)
        ttk.Label(
            frame, text="Box size (pixels per each 'box' in the QR code):"
        ).grid(column=0, row=0, sticky=tk.W)
        ttk.Entry(frame, width=25, textvariable=self.box_size).grid(
            column=0, row=1, sticky=tk.W
        )

        frame = _section(main, column=4, row=4)
        ttk.Label(frame, text="Border size (in boxes, 4 recommended):").grid(
            column=0, row=0, sticky=tk.W
        )
        ttk.Entry(frame, width=25, textvariable=self.border).grid(
            column=0, row=1, sticky=tk.W
        )

        frame = _section(main, column=4, row=5)
        ttk.Label(frame, text="Box style:").grid(
            column=0, row=0, sticky=tk.W, columnspan=3
        )
        styles = _radio_group(
            frame,
            self.box_style,
            BOX_STYLE_OPTIONS,
            columns=3,
            command=self._update_states,
        )
        eye_frame = ttk.Frame(frame)
        eye_frame.grid(column=0, row=4, sticky=tk.W, columnspan=3)
        ttk.Label(eye_frame, text="Eye style (the 3 corner squares):").grid(
            column=0, row=0, sticky=tk.W
        )
        self.eye_combo = ttk.Combobox(eye_frame, width=16)
        self.eye_combo.state(["readonly"])
        self.eye_combo.grid(column=1, row=0, sticky=tk.W, padx=PAD)
        self.eye_combo.bind("<<ComboboxSelected>>", self._on_eye_selected)
        self.eye_style.trace_add("write", lambda *_: self._show_eye_style())
        self._show_eye_style()

        frame = _section(main, column=4, row=6, rowspan=2)
        ttk.Label(frame, text="Color mask:").grid(
            column=0, row=0, sticky=tk.W, columnspan=3
        )
        masks = _radio_group(
            frame,
            self.color_mask,
            COLOR_MASK_OPTIONS,
            columns=3,
            command=self._update_states,
        )
        mask_frame = ttk.Frame(frame)
        mask_frame.grid(column=0, row=3, sticky=tk.W, columnspan=3)
        self._mask_image_widgets = (
            _grid(ttk.Label(mask_frame, text="Image mask path:"), 0, 0),
            _grid(
                ttk.Entry(
                    mask_frame, width=40, textvariable=self.mask_image_path
                ),
                1,
                0,
            ),
            _grid(
                ttk.Button(
                    mask_frame,
                    text="Browse…",
                    command=lambda: self._browse_image(
                        self.mask_image_path, "Image mask"
                    ),
                ),
                2,
                0,
                padx=PAD,
            ),
        )
        edge_frame = ttk.Frame(frame)
        edge_frame.grid(column=0, row=4, sticky=tk.W, columnspan=3)
        self._edge_widgets = self._color_input(
            edge_frame, "2nd color, e.g. (0, 0, 255):", self.edge_color, 15
        )
        self._png_only_widgets = [
            button
            for value, button in styles.items()
            if value not in core.SVG_DRAWERS
        ] + [
            button
            for value, button in masks.items()
            if value not in core.SVG_GRADIENTS
        ]

    def _color_input(self, frame, text, var, width):
        """Build a labeled color entry with a palette button.

        Parameters
        ----------
        frame : tkinter.ttk.Frame
            Frame to build the widgets in.
        text : str
            Label text.
        var : tkinter.StringVar
            Variable holding the color.
        width : int
            Width of the entry in characters.

        Returns
        -------
        list of tkinter.ttk.Widget
            The label, the entry and the button.
        """
        stacked = width > 20  # long entries go below their label
        label = _grid(ttk.Label(frame, text=text), 0, 0, columnspan=2)
        entry = ttk.Entry(frame, width=width, textvariable=var)
        button = ttk.Button(
            frame, text="See palette", command=lambda: self._pick_color(var)
        )
        if stacked:
            _grid(entry, 0, 1)
            _grid(button, 1, 1)
        else:
            label.grid(columnspan=1)
            _grid(entry, 1, 0)
            _grid(button, 2, 0)
        return [label, entry, button]

    def _build_generate_section(self, main):
        """Build the generate button and the status line.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        frame = ttk.Frame(main, padding=PAD)
        frame.grid(column=2, row=9, columnspan=4)
        self.generate_button = ttk.Button(
            frame, text="Generate QR code (Ctrl+Enter)", command=self.generate
        )
        self.generate_button.grid(column=0, row=0, ipadx=10, ipady=5)
        ttk.Label(frame, textvariable=self.status).grid(column=0, row=1)

    def _build_presets_section(self, main):
        """Build the preset dropdown and its buttons.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        frame = ttk.Frame(main, padding=PAD)
        frame.grid(column=0, row=10, columnspan=5, sticky=tk.W)
        ttk.Label(frame, text="Presets:").grid(column=0, row=0, sticky=tk.W)
        self.preset_combo = ttk.Combobox(
            frame,
            width=25,
            textvariable=self.preset_name,
            postcommand=self._reload_preset_list,
        )
        self.preset_combo.grid(column=1, row=0, sticky=tk.W)
        for column, text, command in (
            (2, "Load", self.load_preset),
            (3, "Save", self.save_preset),
            (4, "Delete", self.delete_preset),
            (5, "Open folder", self.open_presets_folder),
        ):
            ttk.Button(frame, text=text, command=command).grid(
                column=column, row=0, sticky=tk.W, padx=(PAD, 0)
            )
        self._reload_preset_list()

    def _build_preview(self, main):
        """Build the preview area.

        Parameters
        ----------
        main : tkinter.ttk.Frame
            Main frame of the window.
        """
        frame = ttk.Frame(main, padding=PAD)
        frame.grid(column=8, row=1, rowspan=10, sticky=tk.N)
        ttk.Label(frame, text="Preview:").grid(column=0, row=0, sticky=tk.W)
        box = ttk.Frame(
            frame,
            width=PREVIEW_SIZE + 4,
            height=PREVIEW_SIZE + 4,
            relief="sunken",
            borderwidth=2,
        )
        box.grid(column=0, row=1)
        box.grid_propagate(False)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.preview_label = ttk.Label(
            box, anchor=tk.CENTER, justify=tk.CENTER, wraplength=PREVIEW_SIZE
        )
        self.preview_label.grid(column=0, row=0)

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
        _set_enabled(self._edge_widgets, mask not in ("solid", "image"))
        _set_enabled(
            [b for v, b in self._error_correction_buttons.items() if v != "H"],
            not embed,
        )
        self.eye_combo["values"] = [
            text
            for text, value in BOX_STYLE_OPTIONS
            if not svg or value in core.SVG_DRAWERS
        ]

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

    def _show_eye_style(self):
        """Show the eye style variable's value in its dropdown."""
        labels = {value: text for text, value in BOX_STYLE_OPTIONS}
        self.eye_combo.set(labels.get(self.eye_style.get(), ""))

    def _on_eye_selected(self, _event):
        """Store the eye style picked in the dropdown.

        Parameters
        ----------
        _event : tkinter.Event
            The selection event (unused).
        """
        values = {text: value for text, value in BOX_STYLE_OPTIONS}
        self.eye_style.set(values[self.eye_combo.get()])
        self._update_states()

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
        colors = {"back_color": _read_color(self.back_color, "Background")}
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
        """Tell whether a preview or a save is pending or running.

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

    def _set_saving(self, saving):
        """Switch the window between the idle and the saving state.

        Parameters
        ----------
        saving : bool
            Whether a save is running.
        """
        self._saving = saving
        self.generate_button.state(["disabled" if saving else "!disabled"])
        self.status.set("Generating…" if saving else "")

    # --- preview -----------------------------------------------------

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
            core.make_preview, settings, PREVIEW_SIZE
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


def _section(main, column, row, rowspan=1):
    """Create a padded frame spanning four grid columns.

    Parameters
    ----------
    main : tkinter.ttk.Frame
        Main frame of the window.
    column, row : int
        Grid position.
    rowspan : int, default 1
        Number of grid rows to span.

    Returns
    -------
    tkinter.ttk.Frame
        The new frame.
    """
    frame = ttk.Frame(main, padding=PAD)
    frame.grid(
        column=column, row=row, columnspan=4, rowspan=rowspan, sticky=tk.W
    )
    return frame


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


def _radio_group(frame, var, options, columns, command=None):
    """Create radio buttons laid out in rows below row 0.

    Parameters
    ----------
    frame : tkinter.ttk.Frame
        Frame to build the buttons in.
    var : tkinter.Variable
        Variable shared by the buttons.
    options : sequence of tuple of str
        ``(text, value)`` pairs, one per button.
    columns : int
        Number of buttons per row.
    command : callable, optional
        Called when a button is clicked.

    Returns
    -------
    dict
        Buttons keyed by their value.
    """
    buttons = {}
    for i, (text, value) in enumerate(options):
        button = ttk.Radiobutton(
            frame, text=text, variable=var, value=value, command=command
        )
        _grid(button, i % columns, 1 + i // columns)
        buttons[value] = button
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
