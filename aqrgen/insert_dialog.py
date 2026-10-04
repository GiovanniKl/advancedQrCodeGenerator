"""Form dialog that fills in the message with a standard format."""

import dataclasses
import tkinter as tk
from tkinter import messagebox, ttk

PAD = 5
"""Basic padding between widgets in pixels."""


def center_over(window, parent):
    """Place a window centered over another one.

    Parameters
    ----------
    window : tkinter.Toplevel
        Window to place; its size is taken from its contents.
    parent : tkinter.Misc
        Window to center on.
    """
    window.update_idletasks()
    top = parent.winfo_toplevel()
    x = top.winfo_rootx() + (top.winfo_width() - window.winfo_reqwidth()) // 2
    y = top.winfo_rooty() + (top.winfo_height() - window.winfo_reqheight()) // 2
    window.geometry(f"+{x}+{y}")


class InsertDialog:
    """Modal form for one message type of `aqrgen.payloads`.

    Parameters
    ----------
    parent : tkinter.Misc
        Window the dialog belongs to.
    payload_type : type
        One of `aqrgen.payloads.PAYLOAD_TYPES`.
    on_insert : callable
        Called with the built message and the form values (a dict)
        when the user clicks Insert and the inputs are valid.
    values : dict, optional
        Initial values of the inputs, e.g. from the last use.
    """

    def __init__(self, parent, payload_type, on_insert, values=None):
        self.payload_type = payload_type
        self.on_insert = on_insert
        self.window = tk.Toplevel(parent)
        self.window.withdraw()  # shown once it is centered
        self.window.title(f"Insert: {payload_type.title}")
        self.window.transient(parent)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Return>", self._on_return)
        self.window.bind("<Escape>", lambda _event: self.close())

        frame = ttk.Frame(self.window, padding=2 * PAD)
        frame.grid(sticky=tk.NSEW)
        row = 0
        if payload_type.note:
            ttk.Label(
                frame, text=payload_type.note, wraplength=420, foreground="gray"
            ).grid(column=0, row=row, columnspan=3, sticky=tk.W, pady=(0, PAD))
            row += 1
        self.inputs = {}
        values = values or {}
        for field in dataclasses.fields(payload_type):
            value = values.get(field.name, field.default)
            self.inputs[field.name] = self._add_input(frame, row, field, value)
            row += 1
        buttons = ttk.Frame(frame)
        buttons.grid(
            column=0, row=row, columnspan=3, sticky=tk.E, pady=(PAD, 0)
        )
        ttk.Button(
            buttons, text="Insert", command=self.insert, default="active"
        ).grid(column=0, row=0, padx=(0, PAD))
        ttk.Button(buttons, text="Cancel", command=self.close).grid(
            column=1, row=0
        )
        first = next(iter(self.inputs.values()))
        center_over(self.window, parent)
        self.window.deiconify()
        first[1].focus_set()
        try:
            self.window.grab_set()
        except tk.TclError:  # some window managers map windows later
            self.window.after_idle(self.window.grab_set)

    def _add_input(self, frame, row, field, value):
        """Add the label, input and hint of one field.

        Parameters
        ----------
        frame : tkinter.ttk.Frame
            Form frame.
        row : int
            Grid row.
        field : dataclasses.Field
            Payload field with the form metadata.
        value : str or bool
            Initial value.

        Returns
        -------
        tuple
            The kind of input and its widget or variable to read.
        """
        meta = field.metadata
        kind = meta["kind"]
        if kind == "check":
            var = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(frame, text=meta["label"], variable=var)
            widget.grid(column=1, row=row, sticky=tk.W, pady=1)
            return kind, widget, var
        ttk.Label(frame, text=meta["label"] + ":").grid(
            column=0,
            row=row,
            sticky=tk.NW if kind == "text" else tk.W,
            padx=(0, PAD),
            pady=1,
        )
        if kind == "text":
            widget = tk.Text(
                frame, width=40, height=3, wrap="word", font="TkDefaultFont"
            )
            widget.insert("1.0", value)
            var = None
        else:
            var = tk.StringVar(value=value)
            if kind == "choice":
                widget = ttk.Combobox(
                    frame, textvariable=var, values=meta["options"], width=38
                )
                widget.state(["readonly"])
            else:
                widget = ttk.Entry(frame, textvariable=var, width=40)
        widget.grid(column=1, row=row, sticky=tk.EW, pady=1)
        if meta["hint"]:
            ttk.Label(frame, text=meta["hint"], foreground="gray").grid(
                column=2, row=row, sticky=tk.W, padx=(PAD, 0)
            )
        return kind, widget, var

    def values(self):
        """Read the current form values.

        Returns
        -------
        dict
            Field names mapped to the typed text or checkbox state.
        """
        result = {}
        for name, (kind, widget, var) in self.inputs.items():
            if kind == "text":
                result[name] = widget.get("1.0", "end-1c")
            else:
                result[name] = var.get()
        return result

    def insert(self):
        """Build the message; insert it and close, or show the problem.

        Returns
        -------
        bool
            Whether the message was valid and inserted.
        """
        values = self.values()
        try:
            text = self.payload_type(**values).build()
        except ValueError as err:
            messagebox.showwarning(
                f"Insert: {self.payload_type.title}",
                str(err),
                parent=self.window,
            )
            return False
        self.close()
        self.on_insert(text, values)
        return True

    def _on_return(self, event):
        """Insert on Enter, except in multi-line text inputs.

        Parameters
        ----------
        event : tkinter.Event
            The key event.
        """
        if not isinstance(event.widget, tk.Text):
            self.insert()

    def close(self):
        """Close the dialog without inserting anything."""
        self.window.grab_release()
        self.window.destroy()
