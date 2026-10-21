"""Reusable consistent typography for CustomTkinter controls."""
import customtkinter as ctk

FONT_FAMILY = "Segoe UI"
BODY_SIZE = 13
TITLE_SIZE = 26

STYLE_WIDGETS = (
    ctk.CTkButton, ctk.CTkLabel, ctk.CTkOptionMenu,
    ctk.CTkCheckBox, ctk.CTkEntry, ctk.CTkRadioButton,
)


def apply_body_font(root, *, excluded=()):
    """Unify button, label, checkbox and dropdown fonts recursively."""
    font = ctk.CTkFont(family=FONT_FAMILY, size=BODY_SIZE)
    omitted = set(excluded)

    def visit(widget):
        if widget not in omitted and isinstance(widget, STYLE_WIDGETS):
            widget.configure(font=font)
        for child in widget.winfo_children():
            visit(child)

    visit(root)
    return font
