import hashlib
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import zlib

from neoconv import __version__ as NEOCONV_VERSION
from neoconv.gui import (
    ExtractTab as NeoConvExtractTab,
    InfoTab as NeoConvInfoTab,
    PackTab as NeoConvPackTab,
    VerifyTab as NeoConvVerifyTab,
)

try:
    from tkinterdnd2 import COPY as DND_COPY, DND_FILES, TkinterDnD
except Exception:
    DND_COPY = "copy"
    DND_FILES = None
    TkinterDnD = None

APP_TITLE = "Rom PP - Rom Wizard"

DEFAULT_SLOTS = 4

TOOLS_HELP_TEXT = """Rom PP Tools Help

Where to find tools

The Tools menu in the top bar contains Split, Split Interleaved, Merge, Merge Interleaved, Padding, Double, Split C ROM, Split V ROM, NeoTool, and .neoConv.

The graphical ROM view right-click menu contains slot-specific actions: Unload, Padding, Double, Split, Split Interleaved, Split C ROM, Split V ROM, and Hex Viewer.

You can also drag and drop a file from Windows Explorer onto a graphical ROM view to load that file into the corresponding slot.

Tool descriptions

Split
Splits the selected ROM slot into a chosen number of equal-sized parts. The source file size must be exactly divisible by the number of parts.

Split Interleaved
Splits the selected ROM slot into two files by separating alternating bytes. This is useful for ROM data stored as high/low byte interleaved pairs.

Merge
Combines the loaded ROM data from multiple selected slots into one output file, in the order entered by the user.

Merge Interleaved (slots 1 & 2)
Builds one interleaved file from ROM slot 1 and ROM slot 2. Slot 1 provides the first byte of each pair, and slot 2 provides the second byte. Both files must have the same size.

Padding
Expands the selected ROM file to a target size by adding padding bytes. Use this when a ROM image must match a specific chip or board size.

Double
Expands the selected ROM by repeating its data a chosen number of times. This is useful when a smaller ROM must be mirrored into a larger address space.

Split C / Split C ROM
Splits Neo Geo C graphics ROM data into chip-sized parts. Available target sizes are 1 MB, 2 MB, 4 MB, and 8 MB.

Split V / Split V ROM
Splits Neo Geo V sound ROM data into chip-sized parts. Available target sizes are 1 MB, 2 MB, and 4 MB.

NeoTool
Analyzes a folder of Neo Geo ROM component files, detects C, V, P, S, and M files, and prepares output files using the selected target sizes.

.neoConv
Opens the integrated neoConv utility. It can extract TerraOnion .neo containers to MAME or Darksoft ROM sets, pack ROM sets into .neo files, verify roundtrip conversions, and inspect .neo metadata.
Credit: .neoConv is based on neoconv by d4NY0H.
Source project: https://github.com/d4NY0H/neoconv

Unload
Removes the file from the selected ROM slot and clears its filename, size, CRC32, SHA1, and graphical memory view.

Hex Viewer
Opens a read-only hexadecimal view of the loaded file in the selected ROM slot.
"""

GRID_COLS = 64
GRID_ROWS = 32
GRID_PADDING = 0
GRID_LINE_COLOR = "#141414"
GRID_LINE_WIDTH = 0
MARQUEE_STEP = 1
MARQUEE_DELAY_MS = 100

CHIP_WIDTH = 100
CHIP_HEIGHT = 200
CHIP_MARGIN_X = 6
CHIP_MARGIN_Y = 8
PIN_WIDTH = 8
PIN_HEIGHT = 8
PIN_GAP = 6
LABEL_HEIGHT = 22
LABEL_GAP = 8
LABEL_SIDE_PADDING = 0

CANVAS_WIDTH = CHIP_WIDTH + (CHIP_MARGIN_X + PIN_WIDTH) * 2
CANVAS_HEIGHT = CHIP_HEIGHT + CHIP_MARGIN_Y * 2 + LABEL_GAP + LABEL_HEIGHT

CHIP_COLOR = "#2b2b2b"
CHIP_OUTLINE = "#1a1a1a"
PIN_COLOR = "#c4b26a"
PIN_OUTLINE = "#8f7c3a"
WINDOW_BG = "#0c0c0c"
LABEL_BG = "#101010"
LABEL_FG = "#f5f5f5"
CANVAS_BG = "#efefef"

ZERO_COLOR = "#d32f2f"
FF_COLOR = "#1565c0"
OTHER_COLOR = "#2e7d32"
EMPTY_CELL_COLOR = "#1d1d1d"

C_ROM_EIGHT_MB_SIZE = 8 * 1024 * 1024
C_ROM_SHORT_FINAL_BANK_SIZE = 4 * 1024 * 1024
C_ROM_SPLIT_OPTIONS = (
    ("1MB", 1 * 1024 * 1024),
    ("2MB", 2 * 1024 * 1024),
    ("4MB", 4 * 1024 * 1024),
    ("8MB", C_ROM_EIGHT_MB_SIZE),
)
V_ROM_SPLIT_OPTIONS = (
    ("1MB", 1 * 1024 * 1024),
    ("2MB", 2 * 1024 * 1024),
    ("4MB", 4 * 1024 * 1024),
)
NEO_COMPONENT_LABELS = (
    *(f"C{i}" for i in range(1, 9)),
    *(f"V{i}" for i in range(1, 5)),
    *(f"P{i}" for i in range(1, 5)),
    "S",
    "M",
)
NEO_COMPONENT_ALIASES = {
    **{f"C{i}": [f"c{i}"] for i in range(1, 9)},
    **{f"V{i}": [f"v{i}"] for i in range(1, 5)},
    **{f"P{i}": [f"p{i}"] for i in range(1, 5)},
    "S": ["s1", "s"],
    "M": ["m1", "m"],
}
NEO_REQUIRED_SUMMARY_LABELS = ("C1", "C2", "V1", "P1", "S", "M")
NEO_TARGET_OPTIONS = {
    "C": ("2", "4", "8"),
    "V": ("1", "2", "4"),
    "P": ("1", "2", "4"),
    "S": ("64", "128"),
    "M": ("64", "128"),
}


def compute_hashes(data):
    crc_val = zlib.crc32(data) & 0xFFFFFFFF
    crc_hex = f"{crc_val:08X}"
    sha1_hex = hashlib.sha1(data).hexdigest().upper()
    return crc_hex, sha1_hex


def compute_bpp(size):
    total_cells = GRID_COLS * GRID_ROWS
    return max(1, int(math.ceil(size / float(total_cells))))


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def detect_c_rom_label(filename):
    labels = []
    lower_name = filename.lower()
    for label in ("c1", "c2"):
        if label in lower_name:
            labels.append(label)
    if len(labels) > 1:
        raise ValueError("Filename contains both c1 and c2.")
    return labels[0] if labels else None


def detect_v_rom_index(filename):
    matches = {int(match.group(1)) for match in re.finditer(r"v(\d+)", filename, re.IGNORECASE)}
    if len(matches) > 1:
        raise ValueError("Filename contains multiple V ROM indices.")
    return next(iter(matches), None)


def replace_case_insensitive(text, old, new):
    pattern = re.compile(re.escape(old), re.IGNORECASE)

    def _replace(match):
        value = match.group(0)
        if value.isupper():
            return new.upper()
        if value.islower():
            return new.lower()
        return new

    return pattern.sub(_replace, text)


def build_c_rom_part_name(filename, source_label, target_label):
    if source_label.lower() not in filename.lower():
        raise ValueError(f"Filename does not contain {source_label}.")
    stem, ext = os.path.splitext(filename)
    updated_stem = replace_case_insensitive(stem, source_label, target_label)
    updated_ext = replace_case_insensitive(ext, source_label, target_label)
    return f"{updated_stem}{updated_ext}"


def build_v_rom_part_name(filename, source_index, target_index):
    pattern = re.compile(rf"v{source_index}", re.IGNORECASE)
    if not pattern.search(filename):
        raise ValueError(f"Filename does not contain V{source_index}.")

    def _replace(match):
        prefix = "V" if match.group(0)[0].isupper() else "v"
        return f"{prefix}{target_index}"

    stem, ext = os.path.splitext(filename)
    updated_stem = pattern.sub(_replace, stem)
    updated_ext = pattern.sub(_replace, ext)
    return f"{updated_stem}{updated_ext}"


def build_numbered_component_name(filename, target_label):
    prefix = target_label[0]
    target_token = target_label.lower()
    stem, ext = os.path.splitext(filename)
    if target_token in get_filename_tokens(stem):
        return filename

    pattern = re.compile(rf"(?<![a-z0-9]){prefix}\d+(?![a-z0-9])", re.IGNORECASE)

    def _replace(match):
        value = match.group(0)
        return target_label.upper() if value.isupper() else target_label.lower()

    updated_stem = pattern.sub(_replace, stem)
    if updated_stem == stem:
        return f"{stem}-{target_token}{ext}"
    return f"{updated_stem}{ext}"


def build_single_component_name(filename, component):
    target_token = "s1" if component == "S" else "m1"
    stem, ext = os.path.splitext(filename)
    if target_token in get_filename_tokens(stem):
        return filename

    pattern = re.compile(rf"(?<![a-z0-9]){component.lower()}1?(?![a-z0-9])", re.IGNORECASE)

    def _replace(match):
        value = match.group(0)
        return target_token.upper() if value.isupper() else target_token.lower()

    updated_stem = pattern.sub(_replace, stem)
    if updated_stem == stem:
        return f"{stem}-{target_token}{ext}"
    return f"{updated_stem}{ext}"


def is_blank_padding(data):
    return is_ff_only(data)


def is_ff_only(data):
    return bool(data) and all(byte == 0xFF for byte in data)


def parse_size_input(value):
    text = value.strip()
    if not text:
        raise ValueError("Size is required.")

    if text.lower().startswith("0x"):
        size = int(text, 16)
    else:
        match = re.fullmatch(r"(\d+)\s*([kmg]?b?)?", text, re.IGNORECASE)
        if not match:
            raise ValueError("Use bytes or KB/MB/GB, for example 1048576, 0x100000, 1MB.")
        size = int(match.group(1))
        suffix = (match.group(2) or "").lower()
        multipliers = {
            "": 1,
            "b": 1,
            "k": 1024,
            "kb": 1024,
            "m": 1024 * 1024,
            "mb": 1024 * 1024,
            "g": 1024 * 1024 * 1024,
            "gb": 1024 * 1024 * 1024,
        }
        size *= multipliers[suffix]

    if size <= 0:
        raise ValueError("Size must be greater than zero.")
    return size


def get_filename_tokens(filename):
    return [token for token in re.split(r"[^a-z0-9]+", filename.lower()) if token]


def find_neo_component_candidates(folder_path):
    files = []
    for entry in sorted(os.scandir(folder_path), key=lambda item: item.name.lower()):
        if entry.is_file():
            files.append(entry.path)

    candidates = {label: [] for label in NEO_COMPONENT_LABELS}
    for path in files:
        tokens = get_filename_tokens(os.path.basename(path))
        for label, aliases in NEO_COMPONENT_ALIASES.items():
            if any(alias in tokens for alias in aliases):
                candidates[label].append(path)
    return candidates


def neo_label_sort_key(label):
    match = re.fullmatch(r"([CVP])(\d+)", label)
    if match:
        prefix_order = {"C": 0, "V": 1, "P": 2}
        return (prefix_order[match.group(1)], int(match.group(2)))
    special_order = {"S": (3, 0), "M": (4, 0)}
    return special_order.get(label, (5, 0))


def get_next_neo_label(label):
    match = re.fullmatch(r"([CVP])(\d+)", label)
    if not match:
        return None
    prefix = match.group(1)
    index = int(match.group(2))
    limits = {"C": 8, "V": 4, "P": 4}
    if index >= limits[prefix]:
        return None
    return f"{prefix}{index + 1}"


def get_file_size_text(path):
    if not path:
        return ""
    try:
        return f"{os.path.getsize(path)} bytes"
    except OSError:
        return ""


def get_neo_target_unit(label):
    return "KB" if label in ("S", "M") else "MB"


def get_neo_target_group(label):
    match = re.fullmatch(r"([CVP])\d+", label)
    if match:
        return match.group(1)
    if label in ("S", "M"):
        return label
    return None


def format_size_for_unit(size_bytes, unit):
    divisor = 1024 if unit == "KB" else 1024 * 1024
    value = size_bytes / float(divisor)
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_size_for_allowed_options(size_bytes, group):
    unit = get_neo_target_unit(group)
    value = format_size_for_unit(size_bytes, unit)
    allowed = NEO_TARGET_OPTIONS.get(group)
    if allowed is None:
        return value
    if group == "C":
        if C_ROM_SHORT_FINAL_BANK_SIZE < size_bytes <= C_ROM_EIGHT_MB_SIZE * 4:
            return f"8 {unit}"
    return f"{value} {unit}" if value in allowed else ""


def get_target_option_labels(group):
    unit = get_neo_target_unit(group)
    return tuple(f"{value} {unit}" for value in NEO_TARGET_OPTIONS.get(group, ()))


def detect_group_target_from_sizes(group, sizes):
    if not sizes:
        return ""
    if group not in NEO_TARGET_OPTIONS:
        return format_size_for_unit(max(sizes), get_neo_target_unit(group))

    matched_values = [format_size_for_allowed_options(size_bytes, group) for size_bytes in sizes]
    if any(not value for value in matched_values):
        return ""
    unique_values = set(matched_values)
    if len(unique_values) == 1:
        return next(iter(unique_values))
    return ""


def get_target_size_bytes(value):
    return parse_size_input(value.replace(" ", ""))


def split_ff_padded_chunks_with_report(data, chunk_size):
    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")

    full_chunks = len(data) // chunk_size
    remainder = data[full_chunks * chunk_size :]
    if remainder and not is_ff_only(remainder):
        raise ValueError("File size is not aligned to the selected chunk size.")

    kept_chunks = []
    skipped_indexes = []
    for index in range(full_chunks):
        chunk = data[index * chunk_size : (index + 1) * chunk_size]
        if is_ff_only(chunk):
            skipped_indexes.append(index + 1)
            continue
        kept_chunks.append((index + 1, chunk))
    return kept_chunks, skipped_indexes


def split_c_rom_chunks_with_report(data, chunk_size):
    if chunk_size != C_ROM_EIGHT_MB_SIZE:
        kept_chunks, skipped_indexes = split_ff_padded_chunks_with_report(data, chunk_size)
        return kept_chunks, skipped_indexes, 0

    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")

    full_chunks = len(data) // chunk_size
    remainder = data[full_chunks * chunk_size :]
    kept_chunks = []
    skipped_indexes = []
    padded_bytes = 0
    for index in range(full_chunks):
        chunk = data[index * chunk_size : (index + 1) * chunk_size]
        if is_ff_only(chunk):
            skipped_indexes.append(index + 1)
            continue
        kept_chunks.append((index + 1, chunk))

    if remainder:
        index = full_chunks + 1
        target_size = C_ROM_SHORT_FINAL_BANK_SIZE
        if len(remainder) > C_ROM_SHORT_FINAL_BANK_SIZE:
            target_size = C_ROM_EIGHT_MB_SIZE
        padded_remainder = remainder.ljust(target_size, b"\xFF")
        if is_ff_only(padded_remainder):
            skipped_indexes.append(index)
        else:
            kept_chunks.append((index, padded_remainder))
            padded_bytes += target_size - len(remainder)
    return kept_chunks, skipped_indexes, padded_bytes


def split_ff_padded_chunks(data, chunk_size):
    return [chunk for _index, chunk in split_ff_padded_chunks_with_report(data, chunk_size)[0]]


def split_c_rom_banks(data, part_size, max_banks=4):
    if part_size <= 0:
        raise ValueError("Part size must be greater than zero.")
    if max_banks <= 0:
        raise ValueError("Maximum bank count must be greater than zero.")

    max_size = part_size * max_banks
    padded_bank_bytes = 0
    trailing_padding_size = 0
    if len(data) > max_size:
        trailing = data[max_size:]
        if not is_blank_padding(trailing):
            raise ValueError(
                f"Loaded ROM is larger than {max_size} bytes and the extra data "
                "is not blank padding (FF)."
            )
        trailing_padding_size = len(trailing)
        data = data[:max_size]

    if part_size != C_ROM_EIGHT_MB_SIZE:
        full_banks, remainder_size = divmod(len(data), part_size)
        if full_banks == 0:
            raise ValueError(
                f"Loaded ROM is smaller than the selected part size ({part_size} bytes)."
            )
        if remainder_size:
            remainder = data[full_banks * part_size :]
            if not is_blank_padding(remainder):
                raise ValueError(
                    "ROM size is not divisible by the selected part size and the trailing data "
                    "is not blank padding (FF)."
                )
            trailing_padding_size += len(remainder)
            data = data[: full_banks * part_size]
        banks = [data[index * part_size : (index + 1) * part_size] for index in range(full_banks)]
        return banks, trailing_padding_size, padded_bank_bytes

    full_banks, remainder_size = divmod(len(data), part_size)
    banks = [data[index * part_size : (index + 1) * part_size] for index in range(full_banks)]
    if remainder_size:
        final_bank = data[full_banks * part_size :]
        target_size = C_ROM_SHORT_FINAL_BANK_SIZE
        if remainder_size > C_ROM_SHORT_FINAL_BANK_SIZE:
            target_size = C_ROM_EIGHT_MB_SIZE
        padded_bank_bytes = target_size - len(final_bank)
        banks.append(final_bank.ljust(target_size, b"\xFF"))
    if not banks:
        raise ValueError("No C ROM banks found to split.")
    return banks, trailing_padding_size, padded_bank_bytes



def duplicate_to_target_size(data, target_size):
    if len(data) > target_size:
        raise ValueError("Source file is larger than the selected target size.")
    if len(data) == target_size:
        return data
    repeats, remainder = divmod(target_size, len(data))
    return (data * repeats) + data[:remainder]


def format_hex_view(data, bytes_per_row=16):
    gap_offset = "    "
    gap_ascii = "    "
    lines = []
    for offset in range(0, len(data), bytes_per_row):
        chunk = data[offset : offset + bytes_per_row]
        hex_bytes = " ".join(f"{b:02X}" for b in chunk)
        padding = "   " * (bytes_per_row - len(chunk))
        ascii_text = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{offset:08X}{gap_offset}{hex_bytes}{padding}{gap_ascii}|{ascii_text}|")
    return "\n".join(lines)


def center_toplevel(window, width=None, height=None):
    window.update_idletasks()
    width = window.winfo_reqwidth() if width is None else width
    height = window.winfo_reqheight() if height is None else height
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def resize_toplevel_to_content(window):
    window.update_idletasks()
    width = window.winfo_reqwidth()
    height = window.winfo_reqheight()
    x = window.winfo_x()
    y = window.winfo_y()
    if x <= 0 and y <= 0:
        center_toplevel(window, width, height)
        return
    window.geometry(f"{width}x{height}+{x}+{y}")


class DoubleFactorDialog(simpledialog.Dialog):
    def __init__(self, parent, current_size):
        self.current_size = current_size
        self.factor = None
        self.factor_var = None
        self.final_size_var = None
        self.error_var = None
        self.ok_button = None
        super().__init__(parent, title="Double")

    def body(self, master):
        self.factor_var = tk.StringVar(value="2")
        self.final_size_var = tk.StringVar()
        self.error_var = tk.StringVar()

        ttk.Label(master, text=f"Current ROM size: {self.current_size} bytes").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 4)
        )
        ttk.Label(master, text="Multiplier:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )

        entry = ttk.Entry(master, textvariable=self.factor_var, width=12)
        entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        master.columnconfigure(1, weight=1)

        ttk.Label(master, textvariable=self.final_size_var).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 2)
        )
        ttk.Label(master, textvariable=self.error_var, foreground="#b00020").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6)
        )

        self.factor_var.trace_add("write", self._update_preview)
        self.after_idle(lambda: center_toplevel(self))
        self._update_preview()
        return entry

    def buttonbox(self):
        box = ttk.Frame(self)
        self.ok_button = ttk.Button(box, text="OK", command=self.ok)
        self.ok_button.pack(side="left", padx=6, pady=6)
        ttk.Button(box, text="Cancel", command=self.cancel).pack(side="left", padx=6, pady=6)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()
        self._update_preview()

    def _get_factor(self):
        text = self.factor_var.get().strip()
        if not text:
            return None, "Enter a multiplier."
        if not text.isdigit():
            return None, "Multiplier must be an integer."
        factor = int(text)
        if factor < 2:
            return None, "Multiplier must be at least 2."
        return factor, ""

    def _update_preview(self, *_args):
        factor, error = self._get_factor()
        if factor is None:
            self.final_size_var.set("Final size: -")
            self.error_var.set(error)
            if self.ok_button is not None:
                self.ok_button.configure(state=tk.DISABLED)
            return

        final_size = self.current_size * factor
        self.final_size_var.set(f"Final size: {final_size} bytes")
        self.error_var.set("")
        if self.ok_button is not None:
            self.ok_button.configure(state=tk.NORMAL)

    def validate(self):
        factor, error = self._get_factor()
        if factor is None:
            self.error_var.set(error)
            return False
        self.factor = factor
        return True

    def apply(self):
        self.result = self.factor


class NeoToolDialog(tk.Toplevel):
    def __init__(self, parent, folder_path):
        super().__init__(parent)
        self.owner = parent
        self.folder_path = folder_path
        self.summary_var = None
        self.candidates = {}
        self.rows = []
        self.rows_frame = None
        self.target_size_vars = {}
        self.target_size_modes = {}
        self.target_size_syncing = {}
        self.target_size_inputs = {}
        self.initial_focus = None

        self.withdraw()
        if self.owner is not None and self.owner.winfo_viewable():
            self.transient(self.owner)
        self.title("NeoTool")
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        body = ttk.Frame(self, padding=5)
        body.pack(fill="both", expand=True)
        self.initial_focus = self.body(body)
        self.buttonbox()

        if self.initial_focus is None:
            self.initial_focus = self

        self.deiconify()
        self.initial_focus.focus_set()
        self.after_idle(self._finish_open)

    def _finish_open(self):
        if not self.winfo_exists():
            return
        resize_toplevel_to_content(self)
        self.lift()

    def cancel(self, event=None):
        if self.owner is not None and self.owner.winfo_exists():
            self.owner.focus_set()
        self.destroy()

    def body(self, master):
        self.summary_var = tk.StringVar()

        ttk.Label(master, text="Folder:").grid(row=0, column=0, sticky="nw", padx=6, pady=(6, 2))
        folder_entry = tk.Entry(master, width=72, background="#ffffff", readonlybackground="#ffffff")
        folder_entry.insert(0, self.folder_path)
        folder_entry.configure(state="readonly")
        folder_entry.grid(row=0, column=1, columnspan=4, sticky="ew", padx=6, pady=(6, 2))

        ttk.Label(master, textvariable=self.summary_var).grid(
            row=1, column=0, columnspan=5, sticky="w", padx=6, pady=(0, 8)
        )

        target_row = 2
        target_frame = ttk.Frame(master)
        target_frame.grid(row=target_row, column=0, columnspan=5, sticky="w", padx=6, pady=(0, 8))
        for index, group in enumerate(("C", "V", "P", "S", "M")):
            ttk.Label(target_frame, text=f"{group}:").grid(row=0, column=index, sticky="w", padx=(0, 10), pady=(0, 2))
            var = tk.StringVar()
            self.target_size_vars[group] = var
            self.target_size_modes[group] = "auto"
            self.target_size_syncing[group] = False
            var.trace_add("write", lambda *_args, current=group: self._on_group_target_changed(current))
            if group in NEO_TARGET_OPTIONS:
                input_widget = ttk.Combobox(
                    target_frame,
                    textvariable=var,
                    values=get_target_option_labels(group),
                    width=7,
                    state="readonly",
                )
            else:
                input_widget = ttk.Entry(target_frame, textvariable=var, width=6)
            input_widget.grid(row=1, column=index, sticky="w", padx=(0, 10))
            self.target_size_inputs[group] = input_widget

        header_row = 3
        ttk.Label(master, text="Type").grid(row=header_row, column=0, sticky="w", padx=6, pady=(0, 4))
        ttk.Label(master, text="File").grid(row=header_row, column=1, sticky="w", padx=6, pady=(0, 4))
        ttk.Label(master, text="Size").grid(row=header_row, column=2, sticky="w", padx=6, pady=(0, 4))

        self.rows_frame = ttk.Frame(master)
        self.rows_frame.grid(row=header_row + 1, column=0, columnspan=5, sticky="nsew")
        master.columnconfigure(0, minsize=52)
        master.columnconfigure(1, weight=1, minsize=240)
        master.columnconfigure(2, minsize=66)
        master.columnconfigure(3, minsize=32)
        master.columnconfigure(4, minsize=24)
        self.rows_frame.columnconfigure(0, minsize=52)
        self.rows_frame.columnconfigure(1, weight=1, minsize=240)
        self.rows_frame.columnconfigure(2, minsize=66)
        self.rows_frame.columnconfigure(3, minsize=32)
        self.rows_frame.columnconfigure(4, minsize=24)

        self._auto_assign()
        self.after_idle(lambda: resize_toplevel_to_content(self))
        return None

    def destroy(self):
        super().destroy()

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Prepare", command=self._prepare_files).pack(side="left", padx=6, pady=6)
        ttk.Button(box, text="Close", command=self.cancel).pack(side="left", padx=6, pady=6)
        box.pack()

    def _has_p2_or_higher(self, rows):
        return any(
            row["path"] and re.fullmatch(r"P[2-4]", row["type_var"].get())
            for row in rows
        )

    def _prepare_files(self):
        grouped_rows = {group: [] for group in ("C", "V", "P", "S", "M")}
        for row in self.rows:
            if not row["path"]:
                continue
            group = get_neo_target_group(row["type_var"].get())
            if group:
                grouped_rows[group].append(row)

        if not any(grouped_rows.values()):
            messagebox.showwarning("NeoTool", "No files selected to prepare.", parent=self)
            return

        target_sizes = {}
        for group, rows in grouped_rows.items():
            if not rows:
                continue
            value = self.target_size_vars[group].get().strip()
            if not value:
                messagebox.showerror("NeoTool", f"Missing target size for {group}.", parent=self)
                return
            try:
                target_sizes[group] = get_target_size_bytes(value)
            except ValueError as exc:
                messagebox.showerror("NeoTool", f"Invalid target size for {group}:\n{exc}", parent=self)
                return

        output_dir = os.path.join(self.folder_path, "_prepared")
        counter = 2
        while os.path.exists(output_dir):
            output_dir = os.path.join(self.folder_path, f"_prepared_{counter:02d}")
            counter += 1
        os.makedirs(output_dir, exist_ok=False)

        try:
            notes = []
            details = []
            created_by_group = {group: [] for group in ("C", "V", "P", "S", "M")}
            created_by_group["C"] = self._prepare_c_group(
                grouped_rows["C"], target_sizes.get("C"), output_dir, details=details
            )
            created_by_group["V"] = self._prepare_sequential_group(
                grouped_rows["V"],
                target_sizes.get("V"),
                output_dir,
                "V",
                4,
                warnings=notes,
                details=details,
            )
            if self._has_p2_or_higher(grouped_rows["P"]):
                notes.append("P ROM skipped because P2 or higher already exists.")
            else:
                created_by_group["P"] = self._prepare_numbered_group(
                    grouped_rows["P"],
                    target_sizes.get("P"),
                    output_dir,
                    "P",
                    details=details,
                )
            created_by_group["S"] = self._prepare_single_group(
                grouped_rows["S"], target_sizes.get("S"), output_dir, "S", details=details
            )
            created_by_group["M"] = self._prepare_single_group(
                grouped_rows["M"], target_sizes.get("M"), output_dir, "M", details=details
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("NeoTool", f"Prepare failed:\n{exc}", parent=self)
            return

        created_files = [path for paths in created_by_group.values() for path in paths]
        if not created_files:
            messagebox.showwarning("NeoTool", "No output files were created.", parent=self)
            return

        self._show_prepare_summary(output_dir, created_by_group, notes, details)

    def _read_row_data(self, row):
        with open(row["path"], "rb") as handle:
            return handle.read()

    def _prepare_c_group(self, rows, chunk_size, output_dir, details=None):
        if not rows:
            return []
        created_files = []
        for parity, start_index in ((1, 1), (0, 2)):
            next_index = start_index
            parity_rows = [
                row for row in sorted(rows, key=lambda item: neo_label_sort_key(item["type_var"].get()))
                if int(row["type_var"].get()[1:]) % 2 == parity
            ]
            for row in parity_rows:
                data = self._read_row_data(row)
                kept_chunks, skipped_indexes, padded_bytes = split_c_rom_chunks_with_report(data, chunk_size)
                created_labels = []
                for _source_index, chunk in kept_chunks:
                    if next_index > 8:
                        raise ValueError("Too many C ROM banks for the selected cut.")
                    target_label = f"C{next_index}"
                    output_name = build_numbered_component_name(os.path.basename(row["path"]), target_label)
                    output_path = os.path.join(output_dir, output_name)
                    with open(output_path, "wb") as handle:
                        handle.write(chunk)
                    created_files.append(output_path)
                    created_labels.append(target_label)
                    next_index += 2
                if details is not None:
                    source_label = row["type_var"].get()
                    detail = (
                        f"{source_label} {os.path.basename(row['path'])}: split {len(data)} bytes "
                        f"into {', '.join(created_labels) if created_labels else 'no output'}"
                    )
                    if skipped_indexes:
                        detail += f"; skipped FF banks: {', '.join(str(index) for index in skipped_indexes)}"
                    if padded_bytes:
                        detail += f"; padded final bank with FF bytes: {padded_bytes}"
                    details.append(detail)
        return created_files

    def _prepare_sequential_group(self, rows, chunk_size, output_dir, prefix, limit, warnings=None, details=None):
        if not rows:
            return []
        created_files = []
        next_index = 1
        warned_over_limit = False
        for row in sorted(rows, key=lambda item: neo_label_sort_key(item["type_var"].get())):
            data = self._read_row_data(row)
            kept_chunks, skipped_indexes = split_ff_padded_chunks_with_report(data, chunk_size)
            created_labels = []
            for _source_index, chunk in kept_chunks:
                if next_index > limit:
                    if warnings is None:
                        raise ValueError(f"Too many {prefix} ROM banks for the selected cut.")
                    if not warned_over_limit:
                        warnings.append(
                            f"{prefix} ROM exceed {prefix}{limit}. Extra banks will be created anyway."
                        )
                        warned_over_limit = True
                target_label = f"{prefix}{next_index}"
                output_name = build_numbered_component_name(os.path.basename(row["path"]), target_label)
                output_path = os.path.join(output_dir, output_name)
                with open(output_path, "wb") as handle:
                    handle.write(chunk)
                created_files.append(output_path)
                created_labels.append(target_label)
                next_index += 1
            if details is not None:
                source_label = row["type_var"].get()
                detail = (
                    f"{source_label} {os.path.basename(row['path'])}: split {len(data)} bytes "
                    f"into {', '.join(created_labels) if created_labels else 'no output'}"
                )
                if skipped_indexes:
                    detail += f"; skipped FF banks: {', '.join(str(index) for index in skipped_indexes)}"
                details.append(detail)
        return created_files

    def _prepare_numbered_group(self, rows, target_size, output_dir, prefix, details=None):
        if not rows:
            return []
        created_files = []
        for row in sorted(rows, key=lambda item: neo_label_sort_key(item["type_var"].get())):
            target_label = row["type_var"].get()
            if not re.fullmatch(rf"{prefix}\d+", target_label):
                raise ValueError(f"Invalid {prefix} ROM label: {target_label}")
            source_data = self._read_row_data(row)
            prepared_data = duplicate_to_target_size(source_data, target_size)
            output_name = build_numbered_component_name(os.path.basename(row["path"]), target_label)
            output_path = os.path.join(output_dir, output_name)
            with open(output_path, "wb") as handle:
                handle.write(prepared_data)
            created_files.append(output_path)
            if details is not None:
                action = "copied unchanged" if len(source_data) == len(prepared_data) else "duplicated"
                details.append(
                    f"{target_label} {os.path.basename(row['path'])}: {action} "
                    f"{len(source_data)} -> {len(prepared_data)} bytes"
                )
        return created_files

    def _prepare_single_group(self, rows, target_size, output_dir, component, details=None):
        if not rows:
            return []
        created_files = []
        for row in rows:
            source_data = self._read_row_data(row)
            prepared_data = duplicate_to_target_size(source_data, target_size)
            output_name = build_single_component_name(os.path.basename(row["path"]), component)
            output_path = os.path.join(output_dir, output_name)
            with open(output_path, "wb") as handle:
                handle.write(prepared_data)
            created_files.append(output_path)
            if details is not None:
                action = "copied unchanged" if len(source_data) == len(prepared_data) else "duplicated"
                details.append(
                    f"{component} {os.path.basename(row['path'])}: {action} "
                    f"{len(source_data)} -> {len(prepared_data)} bytes"
                )
        return created_files

    def _show_prepare_summary(self, output_dir, created_by_group, notes, details):
        total_files = sum(len(paths) for paths in created_by_group.values())
        report_path = os.path.join(output_dir, "prepare_summary.txt")
        summary_lines = [
            f"Output folder: {output_dir}",
            f"Summary file: {report_path}",
            f"Created files: {total_files}",
            "",
        ]

        if notes:
            summary_lines.append("Notes:")
            for note in notes:
                summary_lines.append(f"- {note}")
            summary_lines.append("")

        if details:
            summary_lines.append("Actions:")
            for detail in details:
                summary_lines.append(f"- {detail}")
            summary_lines.append("")

        for group in ("C", "V", "P", "S", "M"):
            paths = created_by_group[group]
            if not paths:
                continue
            summary_lines.append(f"{group}:")
            for path in paths:
                size_text = get_file_size_text(path) or "unknown size"
                summary_lines.append(f"- {os.path.basename(path)} ({size_text})")
            summary_lines.append("")

        summary_text = "\n".join(summary_lines).rstrip() + "\n"
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(summary_text)

        viewer = tk.Toplevel(self)
        viewer.title("NeoTool Prepare Summary")
        viewer.minsize(980, 320)

        frame = ttk.Frame(viewer, padding=6)
        frame.grid(row=0, column=0, sticky="nsew")
        viewer.rowconfigure(0, weight=1)
        viewer.columnconfigure(0, weight=1)

        text = tk.Text(
            frame,
            wrap="word",
            width=132,
            height=18,
            font=("Consolas", 10),
            background="#ffffff",
        )
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        text.insert("1.0", summary_text)
        text.configure(state="disabled")
        center_toplevel(viewer, width=1100, height=360)

    def _auto_assign(self):
        self.candidates = find_neo_component_candidates(self.folder_path)
        detected_rows = []
        used_paths = set()
        for label in NEO_COMPONENT_LABELS:
            selected_path = None
            for candidate in self.candidates[label]:
                if candidate not in used_paths:
                    selected_path = candidate
                    used_paths.add(candidate)
                    break
            if selected_path:
                detected_rows.append(self._make_row(label, selected_path, "auto"))

        self.rows = detected_rows
        self._normalize_rows()
        self._render_rows()
        self._refresh_rows()

    def _render_rows(self):
        for child in self.rows_frame.winfo_children():
            child.destroy()

        for row_index, row in enumerate(self.rows):
            type_box = ttk.Combobox(
                self.rows_frame,
                textvariable=row["type_var"],
                values=NEO_COMPONENT_LABELS,
                width=4,
                state="readonly",
            )
            type_box.grid(row=row_index, column=0, sticky="ew", padx=6, pady=2)
            type_box.bind("<<ComboboxSelected>>", lambda _event, current=row: self._on_type_changed(current))

            path_entry = tk.Entry(
                self.rows_frame,
                textvariable=row["path_var"],
                width=34,
                background="#ffffff",
                readonlybackground="#ffffff",
            )
            path_entry.configure(state="readonly")
            path_entry.grid(row=row_index, column=1, sticky="ew", padx=6, pady=2)

            ttk.Label(self.rows_frame, textvariable=row["size_var"]).grid(
                row=row_index, column=2, sticky="w", padx=6, pady=2
            )
            ttk.Button(self.rows_frame, text="...", width=2, command=lambda current=row: self._select_file(current)).grid(
                row=row_index, column=3, sticky="ew", padx=4, pady=2
            )
            ttk.Button(
                self.rows_frame,
                text="X",
                width=1,
                style="Danger.TButton",
                command=lambda current=row: self._clear_file(current),
            ).grid(
                row=row_index, column=4, sticky="ew", padx=(0, 6), pady=2
            )
        self.after_idle(lambda: resize_toplevel_to_content(self))
        self._refresh_rows()

    def _on_type_changed(self, _row):
        self._normalize_rows()
        self._render_rows()
        self._refresh_rows()

    def _select_file(self, row):
        path = filedialog.askopenfilename(
            title=f"Select file for {row['type_var'].get()}",
            initialdir=self.folder_path,
            filetypes=[("Binary files", "*.*")],
            parent=self,
        )
        if not path:
            return
        row["path"] = path
        row["source"] = "manual"
        row["path_var"].set(self._display_path(path))
        self._normalize_rows()
        self._render_rows()
        self._refresh_rows()

    def _clear_file(self, row):
        row["path"] = None
        row["source"] = None
        row["path_var"].set("")
        self._normalize_rows()
        self._render_rows()
        self._refresh_rows()

    def _make_row(self, label, path=None, source=None):
        return {
            "type_var": tk.StringVar(value=label),
            "path_var": tk.StringVar(value=self._display_path(path)),
            "size_var": tk.StringVar(value=get_file_size_text(path)),
            "path": path,
            "source": source,
        }

    def _on_group_target_changed(self, group):
        if self.target_size_syncing.get(group):
            return
        self.target_size_modes[group] = "manual"

    def _normalize_rows(self):
        populated_rows = [row for row in self.rows if row["path"]]
        normalized_rows = []

        for prefix, limit in (("C", 8), ("V", 4), ("P", 4)):
            family_rows = [
                row
                for row in populated_rows
                if re.fullmatch(rf"{prefix}\d+", row["type_var"].get())
            ]
            family_rows.sort(
                key=lambda row: (
                    int(re.fullmatch(rf"{prefix}(\d+)", row["type_var"].get()).group(1)),
                    self._display_path(row["path"]).lower(),
                )
            )
            for index, row in enumerate(family_rows, start=1):
                row["type_var"].set(f"{prefix}{min(index, limit)}")
                normalized_rows.append(row)

        for label in ("S", "M"):
            family_rows = [row for row in populated_rows if row["type_var"].get() == label]
            family_rows.sort(key=lambda row: self._display_path(row["path"]).lower())
            normalized_rows.extend(family_rows)

        empty_rows = []
        for prefix, limit in (("C", 8), ("V", 4), ("P", 4)):
            assigned_count = sum(1 for row in normalized_rows if re.fullmatch(rf"{prefix}\d+", row["type_var"].get()))
            next_index = assigned_count + 1
            if next_index <= limit:
                empty_rows.append(self._make_row(f"{prefix}{next_index}"))
        for label in ("S", "M"):
            if not any(row["type_var"].get() == label for row in normalized_rows):
                empty_rows.append(self._make_row(label))

        self.rows = normalized_rows + empty_rows
        self._sort_rows()

    def _display_path(self, path):
        if not path:
            return ""
        if os.path.dirname(path) == self.folder_path:
            return os.path.basename(path)
        return path

    def _sort_rows(self):
        self.rows.sort(
            key=lambda row: (
                neo_label_sort_key(row["type_var"].get()),
                1 if not row["path"] else 0,
                self._display_path(row["path"]).lower(),
            )
        )

    def _refresh_rows(self):
        assigned_labels = []
        seen_labels = set()
        for row in self.rows:
            label = row["type_var"].get()
            path = row["path"]
            if path:
                assigned_labels.append(label)
                if label not in seen_labels:
                    seen_labels.add(label)

        found_labels = sorted(set(assigned_labels), key=neo_label_sort_key)
        missing_required = [label for label in NEO_REQUIRED_SUMMARY_LABELS if label not in found_labels]

        for row in self.rows:
            path = row["path"]
            row["path_var"].set(self._display_path(path))
            row["size_var"].set(get_file_size_text(path))

        self._refresh_group_targets()

        summary_labels = {
            "C1": "C1",
            "C2": "C2",
            "V1": "V1",
            "P1": "P1",
            "S": "S1",
            "M": "M1",
        }
        if missing_required:
            self.summary_var.set(
                "Missing: " + ", ".join(summary_labels[label] for label in missing_required)
            )
        else:
            self.summary_var.set("")

    def _refresh_group_targets(self):
        group_sizes = {"C": [], "V": [], "P": [], "S": [], "M": []}
        for row in self.rows:
            if not row["path"]:
                continue
            label = row["type_var"].get()
            group = get_neo_target_group(label)
            if group is None:
                continue
            try:
                group_sizes[group].append(os.path.getsize(row["path"]))
            except OSError:
                continue

        has_p2_or_higher = self._has_p2_or_higher(self.rows)
        for group, sizes in group_sizes.items():
            if group == "P" and has_p2_or_higher:
                self.target_size_modes[group] = "forced"
                self.target_size_syncing[group] = True
                self.target_size_vars[group].set("")
                self.target_size_syncing[group] = False
                if group in self.target_size_inputs:
                    self.target_size_inputs[group].configure(state=tk.DISABLED)
                continue

            if group == "P" and self.target_size_modes.get(group) == "forced":
                self.target_size_modes[group] = "auto"
            if group in self.target_size_inputs and group in NEO_TARGET_OPTIONS:
                self.target_size_inputs[group].configure(state="readonly")
            if self.target_size_modes.get(group) != "auto":
                continue
            value = detect_group_target_from_sizes(group, sizes)
            self.target_size_syncing[group] = True
            self.target_size_vars[group].set(value)
            self.target_size_syncing[group] = False


class MemoryView(ttk.Frame):
    def __init__(
        self,
        parent,
        on_click,
        on_unload,
        on_padding,
        on_double,
        on_split,
        on_split_interleaved,
        on_split_c_rom,
        on_split_v_rom,
        on_open_hex,
        on_drop_file=None,
    ):
        super().__init__(parent)

        self.canvas = tk.Canvas(
            self,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            background=CANVAS_BG,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.canvas.bind("<Double-Button-1>", on_click)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Button-2>", self._show_menu)
        self.canvas.bind("<Control-Button-1>", self._show_menu)

        self.on_unload = on_unload
        self.on_padding = on_padding
        self.on_double = on_double
        self.on_split = on_split
        self.on_split_interleaved = on_split_interleaved
        self.on_split_c_rom = on_split_c_rom
        self.on_split_v_rom = on_split_v_rom
        self.on_open_hex = on_open_hex
        self.on_drop_file = on_drop_file
        self.has_data = False
        self.file_drop_handler = None
        self.label_text_id = None
        self.label_bounds = None
        self.label_center_y = None
        self.label_mask_left = None
        self.label_mask_right = None
        self.marquee_job = None
        self.marquee_text_width = None
        self.marquee_direction = -1
        self.col_positions = None
        self.row_positions = None
        self.grid_bounds = None
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Unload", command=self._handle_unload)
        self.menu.add_command(label="Padding...", command=self._handle_padding)
        self.menu.add_command(label="Double...", command=self._handle_double)
        self.menu.add_command(label="Split...", command=self._handle_split)
        self.menu.add_command(label="Split Interleaved...", command=self._handle_split_interleaved)
        self.c_rom_menu = tk.Menu(self.menu, tearoff=0)
        for size_label, size_bytes in C_ROM_SPLIT_OPTIONS:
            self.c_rom_menu.add_command(
                label=size_label,
                command=lambda s=size_bytes: self._handle_split_c_rom(s),
            )
        self.menu.add_cascade(label="Split C ROM", menu=self.c_rom_menu)
        self.v_rom_menu = tk.Menu(self.menu, tearoff=0)
        for size_label, size_bytes in V_ROM_SPLIT_OPTIONS:
            self.v_rom_menu.add_command(
                label=size_label,
                command=lambda s=size_bytes: self._handle_split_v_rom(s),
            )
        self.menu.add_cascade(label="Split V ROM", menu=self.v_rom_menu)
        self.menu.add_command(label="Hex Viewer...", command=self._handle_open_hex)
        self._draw_chip()
        self.set_data(None, None, None)
        self.after_idle(self._enable_file_drop)

    def _enable_file_drop(self):
        if self.file_drop_handler is not None or self.on_drop_file is None:
            return
        if DND_FILES is None or not hasattr(self.canvas, "drop_target_register"):
            return
        try:
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind("<<DropEnter>>", self._accept_file_drop)
            self.canvas.dnd_bind("<<DropPosition>>", self._accept_file_drop)
            self.canvas.dnd_bind("<<Drop>>", self._handle_file_drop)
        except (RuntimeError, tk.TclError):
            return
        self.file_drop_handler = True

    def _accept_file_drop(self, event):
        return DND_COPY

    def _handle_file_drop(self, event):
        paths = self._parse_drop_files(event.data)
        if paths:
            self.on_drop_file(paths[0])
        return DND_COPY

    def _parse_drop_files(self, data):
        if not data:
            return []
        try:
            paths = self.canvas.tk.splitlist(data)
        except tk.TclError:
            paths = (data,)
        return [path for path in paths if path]

    def _show_menu(self, event):
        state = tk.NORMAL if self.has_data else tk.DISABLED
        last_index = self.menu.index("end")
        if last_index is not None:
            for idx in range(last_index + 1):
                self.menu.entryconfigure(idx, state=state)
        self.menu.tk_popup(event.x_root, event.y_root)

    def _handle_unload(self):
        if self.on_unload:
            self.on_unload()

    def _handle_padding(self):
        if self.on_padding:
            self.on_padding()

    def _handle_double(self):
        if self.on_double:
            self.on_double()

    def _handle_split(self):
        if self.on_split:
            self.on_split()

    def _handle_split_interleaved(self):
        if self.on_split_interleaved:
            self.on_split_interleaved()

    def _handle_split_c_rom(self, part_size):
        if self.on_split_c_rom:
            self.on_split_c_rom(part_size)

    def _handle_split_v_rom(self, part_size):
        if self.on_split_v_rom:
            self.on_split_v_rom(part_size)

    def _handle_open_hex(self):
        if self.on_open_hex:
            self.on_open_hex()

    def _draw_chip(self):
        self.canvas.delete("all")

        chip_x = CHIP_MARGIN_X + PIN_WIDTH
        chip_y = CHIP_MARGIN_Y
        chip_right = chip_x + CHIP_WIDTH
        chip_bottom = chip_y + CHIP_HEIGHT

        pin_count = 14
        total_pins = pin_count * PIN_HEIGHT + (pin_count - 1) * PIN_GAP
        pin_start_y = chip_y + max(0, (CHIP_HEIGHT - total_pins) // 2)

        for i in range(pin_count):
            y1 = pin_start_y + i * (PIN_HEIGHT + PIN_GAP)
            y2 = y1 + PIN_HEIGHT
            self.canvas.create_rectangle(
                chip_x - PIN_WIDTH,
                y1,
                chip_x,
                y2,
                fill=PIN_COLOR,
                outline=PIN_OUTLINE,
            )
            self.canvas.create_rectangle(
                chip_right,
                y1,
                chip_right + PIN_WIDTH,
                y2,
                fill=PIN_COLOR,
                outline=PIN_OUTLINE,
            )

        self.canvas.create_rectangle(
            chip_x,
            chip_y,
            chip_right,
            chip_bottom,
            fill="",
            outline=CHIP_OUTLINE,
            width=2,
            tags="chip_border",
        )

        grid_x = chip_x + GRID_PADDING
        grid_y = chip_y + GRID_PADDING
        grid_right = chip_right - GRID_PADDING
        grid_bottom = chip_bottom - GRID_PADDING
        self.grid_bounds = (grid_x, grid_y, grid_right, grid_bottom)
        grid_width = grid_right - grid_x
        grid_height = grid_bottom - grid_y

        self.canvas.create_rectangle(
            grid_x,
            grid_y,
            grid_right,
            grid_bottom,
            fill=EMPTY_CELL_COLOR,
            outline="",
        )

        self.col_positions = [
            grid_x + (grid_width * col) // GRID_COLS for col in range(GRID_COLS + 1)
        ]
        self.row_positions = [
            grid_y + (grid_height * row) // GRID_ROWS for row in range(GRID_ROWS + 1)
        ]

        label_y = chip_bottom + LABEL_GAP
        label_x = chip_x + LABEL_SIDE_PADDING
        label_right = chip_right - LABEL_SIDE_PADDING

        self.canvas.create_rectangle(
            label_x,
            label_y,
            label_right,
            label_y + LABEL_HEIGHT,
            fill=LABEL_BG,
            outline="#202020",
        )
        self.label_bounds = (label_x, label_y, label_right, label_y + LABEL_HEIGHT)
        self.label_center_y = label_y + LABEL_HEIGHT / 2
        self.label_text_id = self.canvas.create_text(
            label_x,
            self.label_center_y,
            text="",
            anchor="w",
            fill=LABEL_FG,
            font=("Segoe UI", 9, "bold"),
        )
        self.label_mask_left = self.canvas.create_rectangle(
            0,
            label_y,
            label_x,
            label_y + LABEL_HEIGHT,
            fill=CANVAS_BG,
            outline="",
        )
        self.label_mask_right = self.canvas.create_rectangle(
            label_right,
            label_y,
            CANVAS_WIDTH,
            label_y + LABEL_HEIGHT,
            fill=CANVAS_BG,
            outline="",
        )
        self.canvas.tag_raise(self.label_mask_left)
        self.canvas.tag_raise(self.label_mask_right)

    def set_data(self, data, filename, bpp):
        if data is None:
            self._set_label_text("No file loaded")
            data = b""
            self.has_data = False
        else:
            self._set_label_text(filename or "ROM")
            self.has_data = len(data) > 0

        if bpp is None:
            bpp = 1

        self.canvas.delete("gridcell")
        data_len = len(data)
        if data_len == 0:
            self.canvas.tag_raise("chip_border")
            if self.label_mask_left is not None:
                self.canvas.tag_raise(self.label_mask_left)
            if self.label_mask_right is not None:
                self.canvas.tag_raise(self.label_mask_right)
            return

        view = memoryview(data) if data_len else None
        for row in range(GRID_ROWS):
            y1 = self.row_positions[row]
            y2 = self.row_positions[row + 1]
            row_base = row * GRID_COLS
            for col in range(GRID_COLS):
                index = row_base + col
                start = index * bpp
                if start >= data_len or data_len == 0:
                    color = EMPTY_CELL_COLOR
                else:
                    end = min(start + bpp, data_len)
                    chunk = view[start:end]
                    if all(b == 0x00 for b in chunk):
                        color = ZERO_COLOR
                    elif all(b == 0xFF for b in chunk):
                        color = FF_COLOR
                    else:
                        color = OTHER_COLOR
                x1 = self.col_positions[col]
                x2 = self.col_positions[col + 1]
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=color,
                    outline=GRID_LINE_COLOR,
                    width=GRID_LINE_WIDTH,
                    tags="gridcell",
                )
        self.canvas.tag_raise("chip_border")
        if self.label_mask_left is not None:
            self.canvas.tag_raise(self.label_mask_left)
        if self.label_mask_right is not None:
            self.canvas.tag_raise(self.label_mask_right)

    def _set_label_text(self, text):
        if self.label_text_id is None or self.label_bounds is None:
            return
        if self.marquee_job is not None:
            self.after_cancel(self.marquee_job)
            self.marquee_job = None

        self.canvas.itemconfigure(self.label_text_id, text=text)
        self.canvas.update_idletasks()

        bbox = self.canvas.bbox(self.label_text_id)
        if not bbox:
            return
        text_width = bbox[2] - bbox[0]
        label_width = self.label_bounds[2] - self.label_bounds[0]

        if text_width > label_width:
            self.marquee_text_width = text_width
            self.marquee_direction = -1
            start_x = self.label_bounds[0]
            self.canvas.coords(self.label_text_id, start_x, self.label_center_y)
            self._run_marquee()
        else:
            centered_x = self.label_bounds[0] + (label_width - text_width) / 2
            self.canvas.coords(self.label_text_id, centered_x, self.label_center_y)

    def _run_marquee(self):
        if self.label_text_id is None or self.label_bounds is None or self.marquee_text_width is None:
            return
        x, y = self.canvas.coords(self.label_text_id)
        x += self.marquee_direction * MARQUEE_STEP
        left_limit = self.label_bounds[0]
        right_limit = self.label_bounds[2]
        min_x = right_limit - self.marquee_text_width
        max_x = left_limit
        if self.marquee_direction < 0 and x <= min_x:
            x = min_x
            self.marquee_direction = 1
        elif self.marquee_direction > 0 and x >= max_x:
            x = max_x
            self.marquee_direction = -1
        self.canvas.coords(self.label_text_id, x, y)
        self.marquee_job = self.after(MARQUEE_DELAY_MS, self._run_marquee)


class SlotPanel:
    def __init__(self, parent_info, parent_mem, index):
        self.index = index
        self.data = None
        self.file_path = None

        self.info_frame = ttk.Labelframe(parent_info, text=f"File Info ROM #{index}")
        self.info_frame.columnconfigure(1, weight=1)

        self.filename_var = tk.StringVar()
        self.size_var = tk.StringVar()
        self.crc_var = tk.StringVar()
        self.sha1_var = tk.StringVar()
        self.copy_popup = None

        ttk.Label(self.info_frame, text="Filename:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        filename_entry = tk.Entry(
            self.info_frame,
            textvariable=self.filename_var,
            width=30,
            background="#ffffff",
            readonlybackground="#ffffff",
        )
        filename_entry.configure(state="readonly")
        filename_entry.grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=4, pady=2
        )
        ttk.Button(self.info_frame, text="Load...", command=self.load_file).grid(
            row=0, column=4, sticky="e", padx=4, pady=2
        )

        ttk.Label(self.info_frame, text="Filesize:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        size_frame = ttk.Frame(self.info_frame)
        size_frame.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        size_entry = tk.Entry(
            size_frame,
            textvariable=self.size_var,
            width=12,
            background="#ffffff",
            readonlybackground="#ffffff",
        )
        size_entry.configure(state="readonly")
        size_entry.grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(size_frame, text="Byte").grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(self.info_frame, text="CRC32:").grid(row=1, column=3, sticky="e", padx=4, pady=2)
        crc_entry = tk.Entry(
            self.info_frame,
            textvariable=self.crc_var,
            width=12,
            background="#ffffff",
            readonlybackground="#ffffff",
        )
        crc_entry.configure(state="readonly")
        crc_entry.bind(
            "<Double-Button-1>",
            lambda event: self.copy_checksum_to_clipboard(event, self.crc_var),
        )
        crc_entry.grid(
            row=1, column=4, sticky="w", padx=4, pady=2
        )

        ttk.Label(self.info_frame, text="SHA1:").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        sha1_entry = tk.Entry(
            self.info_frame,
            textvariable=self.sha1_var,
            width=35,
            background="#ffffff",
            readonlybackground="#ffffff",
        )
        sha1_entry.configure(state="readonly")
        sha1_entry.bind(
            "<Double-Button-1>",
            lambda event: self.copy_checksum_to_clipboard(event, self.sha1_var),
        )
        sha1_entry.grid(
            row=2, column=1, columnspan=4, sticky="ew", padx=4, pady=2
        )

        self.mem_frame = ttk.Labelframe(parent_mem, text=f"ROM #{index} (--- B/P)")
        self.mem_frame.rowconfigure(0, weight=1)
        self.mem_frame.columnconfigure(0, weight=1)

        self.mem_view = MemoryView(
            self.mem_frame,
            on_click=lambda event: self.load_file(),
            on_unload=self.unload_file,
            on_padding=self.pad_file,
            on_double=self.double_file,
            on_split=self.split_file,
            on_split_interleaved=self.split_interleaved,
            on_split_c_rom=self.split_c_rom,
            on_split_v_rom=self.split_v_rom,
            on_open_hex=self.open_hex_viewer,
            on_drop_file=self.load_file_path,
        )
        self.mem_view.grid(row=0, column=0, sticky="nsew")

    def copy_checksum_to_clipboard(self, event, value_var):
        value = value_var.get().strip()
        if not value:
            return "break"

        widget = event.widget if event else self.info_frame
        try:
            widget.clipboard_clear()
            widget.clipboard_append(value)
            widget.update()
            self.show_copy_popup(widget, "Copiato")
        except tk.TclError as exc:
            messagebox.showerror("Copy error", f"Failed to copy value:\n{exc}", parent=self.info_frame)
        return "break"

    def show_copy_popup(self, widget, text):
        if self.copy_popup is not None and self.copy_popup.winfo_exists():
            self.copy_popup.destroy()

        popup = tk.Toplevel(widget)
        self.copy_popup = popup
        popup.withdraw()
        popup.overrideredirect(True)
        try:
            popup.attributes("-topmost", True)
        except tk.TclError:
            pass

        label = tk.Label(
            popup,
            text=text,
            background="#1f1f1f",
            foreground="#ffffff",
            borderwidth=1,
            relief="solid",
            padx=10,
            pady=4,
        )
        label.pack()
        popup.update_idletasks()

        x = widget.winfo_rootx() + max(0, (widget.winfo_width() - popup.winfo_width()) // 2)
        y = widget.winfo_rooty() - popup.winfo_height() - 6
        if y < 0:
            y = widget.winfo_rooty() + widget.winfo_height() + 6
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()

        def close_popup():
            if self.copy_popup is popup:
                self.copy_popup = None
            if popup.winfo_exists():
                popup.destroy()

        popup.after(1100, close_popup)

    def load_file(self):
        path = filedialog.askopenfilename(
            title=f"Select ROM #{self.index}",
            filetypes=[("Binary files", "*.*")],
            parent=self.info_frame,
        )
        if not path:
            return
        self.load_file_path(path)

    def load_file_path(self, path):
        if not os.path.isfile(path):
            messagebox.showerror("Load error", f"Not a file:\n{path}", parent=self.info_frame)
            return
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            messagebox.showerror("Load error", f"Failed to read file:\n{exc}", parent=self.info_frame)
            return

        self.data = data
        self.file_path = path
        file_name = os.path.basename(path)
        self.filename_var.set(file_name)
        self.size_var.set(str(len(data)))
        crc_hex, sha1_hex = compute_hashes(data)
        self.crc_var.set(crc_hex)
        self.sha1_var.set(sha1_hex)

        bpp = compute_bpp(len(data))
        self.mem_frame.configure(text=f"ROM #{self.index} ({bpp} B/P)")
        self.mem_view.set_data(data, file_name, bpp)

    def unload_file(self):
        self.data = None
        self.file_path = None
        self.filename_var.set("")
        self.size_var.set("")
        self.crc_var.set("")
        self.sha1_var.set("")
        self.mem_frame.configure(text=f"ROM #{self.index} (--- B/P)")
        self.mem_view.set_data(None, None, None)

    def split_file(self):
        if not self.data:
            messagebox.showwarning("Split file", "No file loaded.")
            return

        parts = simpledialog.askinteger(
            "Split file",
            "Number of parts:",
            minvalue=2,
            parent=self.mem_frame,
        )
        if parts is None:
            return

        total_size = len(self.data)
        if total_size % parts != 0:
            messagebox.showerror(
                "Split file",
                "File size is not divisible by the number of parts.",
            )
            return

        initial_name = os.path.basename(self.file_path) if self.file_path else "rom.bin"
        base_path = filedialog.asksaveasfilename(
            title="Save split parts as",
            initialfile=initial_name,
            parent=self.mem_frame,
        )
        if not base_path:
            return

        part_size = total_size // parts
        for i in range(parts):
            part_data = self.data[i * part_size : (i + 1) * part_size]
            part_path = f"{base_path}.part{i + 1:02d}"
            try:
                with open(part_path, "wb") as handle:
                    handle.write(part_data)
            except OSError as exc:
                messagebox.showerror("Split file", f"Failed to save part {i + 1}:\n{exc}")
                return

        messagebox.showinfo(
            "Split file",
            f"Saved {parts} parts to:\n{os.path.dirname(base_path)}",
        )

    def pad_file(self):
        if not self.data or not self.file_path:
            messagebox.showwarning("Padding", "No file loaded.")
            return

        current_size = len(self.data)
        size_text = simpledialog.askstring(
            "Padding",
            "Target total size (bytes, hex, KB/MB/GB):",
            initialvalue=str(current_size),
            parent=self.mem_frame,
        )
        if size_text is None:
            return

        try:
            target_size = parse_size_input(size_text)
        except ValueError as exc:
            messagebox.showerror("Padding", str(exc))
            return

        if target_size < current_size:
            messagebox.showerror(
                "Padding",
                f"Target size ({target_size} bytes) is smaller than the current ROM ({current_size} bytes).",
            )
            return

        initial_name = os.path.basename(self.file_path)
        stem, ext = os.path.splitext(initial_name)
        base_path = filedialog.asksaveasfilename(
            title="Save padded ROM as",
            initialfile=f"{stem}_pad{ext}",
            parent=self.mem_frame,
        )
        if not base_path:
            return

        padded_data = self.data + (b"\xFF" * (target_size - current_size))
        try:
            with open(base_path, "wb") as handle:
                handle.write(padded_data)
        except OSError as exc:
            messagebox.showerror("Padding", f"Failed to save padded ROM:\n{exc}")
            return

        added_size = target_size - current_size
        messagebox.showinfo(
            "Padding",
            f"Saved padded ROM:\n{base_path}\n\nAdded FF bytes: {added_size}",
        )

    def double_file(self):
        if not self.data or not self.file_path:
            messagebox.showwarning("Double", "No file loaded.")
            return

        current_size = len(self.data)
        factor = DoubleFactorDialog(self.mem_frame, current_size).result
        if factor is None:
            return

        initial_name = os.path.basename(self.file_path)
        stem, ext = os.path.splitext(initial_name)
        base_path = filedialog.asksaveasfilename(
            title="Save doubled ROM as",
            initialfile=f"{stem}_double{ext}",
            parent=self.mem_frame,
        )
        if not base_path:
            return

        doubled_data = self.data * factor
        try:
            with open(base_path, "wb") as handle:
                handle.write(doubled_data)
        except OSError as exc:
            messagebox.showerror("Double", f"Failed to save doubled ROM:\n{exc}")
            return

        final_size = current_size * factor
        messagebox.showinfo(
            "Double",
            f"Saved doubled ROM:\n{base_path}\n\nMultiplier: {factor}x\nFinal size: {final_size} bytes",
        )

    def split_interleaved(self):
        if not self.data:
            messagebox.showwarning("Split interleaved", "No file loaded.")
            return

        if len(self.data) % 2 != 0:
            messagebox.showerror(
                "Split interleaved",
                "File size must be even for interleaved split.",
            )
            return

        initial_name = os.path.basename(self.file_path) if self.file_path else "rom.bin"
        base_path = filedialog.asksaveasfilename(
            title="Save interleaved parts as",
            initialfile=initial_name,
            parent=self.mem_frame,
        )
        if not base_path:
            return

        hi_bytes = self.data[0::2]
        lo_bytes = self.data[1::2]

        hi_path = f"{base_path}.H"
        lo_path = f"{base_path}.L"
        try:
            with open(hi_path, "wb") as handle:
                handle.write(hi_bytes)
            with open(lo_path, "wb") as handle:
                handle.write(lo_bytes)
        except OSError as exc:
            messagebox.showerror("Split interleaved", f"Failed to save files:\n{exc}")
            return

        messagebox.showinfo(
            "Split interleaved",
            f"Saved:\n{hi_path}\n{lo_path}",
        )

    def split_c_rom(self, part_size):
        if not self.data or not self.file_path:
            messagebox.showwarning("Split C ROM", "No file loaded.")
            return

        file_name = os.path.basename(self.file_path)
        try:
            source_label = detect_c_rom_label(file_name)
        except ValueError as exc:
            messagebox.showerror("Split C ROM", str(exc))
            return

        if source_label is None:
            messagebox.showerror(
                "Split C ROM",
                "Filename must contain c1 or c2.",
            )
            return

        try:
            bank_chunks, trailing_padding_size, padded_bank_bytes = split_c_rom_banks(self.data, part_size)
        except ValueError as exc:
            messagebox.showerror(
                "Split C ROM",
                str(exc),
            )
            return

        skipped_bank_bytes = 0

        target_labels = ("c1", "c3", "c5", "c7") if source_label == "c1" else ("c2", "c4", "c6", "c8")
        source_dir = os.path.dirname(self.file_path)
        output_dir_name = f"{os.path.splitext(file_name)[0]}_split_crom_{part_size // (1024 * 1024)}mb"
        output_dir = os.path.join(source_dir, output_dir_name)
        os.makedirs(output_dir, exist_ok=True)

        output_items = []
        skipped_labels = []
        for target_label, bank_data in zip(target_labels, bank_chunks):
            if is_blank_padding(bank_data):
                skipped_labels.append(target_label.upper())
                skipped_bank_bytes += len(bank_data)
                continue
            output_items.append(
                (
                    os.path.join(output_dir, build_c_rom_part_name(file_name, source_label, target_label)),
                    bank_data,
                )
            )

        if not output_items:
            messagebox.showwarning(
                "Split C ROM",
                "All target banks are empty padding (FF). No files created.",
            )
            return

        output_paths = [path for path, _ in output_items]
        existing_paths = [path for path in output_paths if os.path.exists(path)]
        if existing_paths and not messagebox.askyesno(
            "Split C ROM",
            "Some destination files already exist.\nOverwrite them?",
            parent=self.mem_frame,
        ):
            return

        for output_path, bank_data in output_items:
            try:
                with open(output_path, "wb") as handle:
                    handle.write(bank_data)
            except OSError as exc:
                messagebox.showerror("Split C ROM", f"Failed to save file:\n{exc}")
                return

        saved_message = f"Saved {len(output_items)} file(s) to:\n{output_dir}"
        if skipped_labels:
            saved_message += f"\n\nSkipped empty banks: {', '.join(skipped_labels)}"
        if skipped_bank_bytes:
            saved_message += f"\nSkipped empty bank bytes: {skipped_bank_bytes}"
        if padded_bank_bytes:
            saved_message += f"\nPadded final bank with FF bytes: {padded_bank_bytes}"
        if trailing_padding_size:
            saved_message += f"\nDiscarded trailing padding: {trailing_padding_size} bytes"
        messagebox.showinfo(
            "Split C ROM",
            saved_message,
        )

    def split_v_rom(self, part_size):
        if not self.data or not self.file_path:
            messagebox.showwarning("Split V ROM", "No file loaded.")
            return

        file_name = os.path.basename(self.file_path)
        try:
            source_index = detect_v_rom_index(file_name)
        except ValueError as exc:
            messagebox.showerror("Split V ROM", str(exc))
            return

        if source_index is None:
            messagebox.showerror(
                "Split V ROM",
                "Filename must contain V1, V2, V3, ...",
            )
            return

        total_size = len(self.data)
        full_parts = total_size // part_size
        remainder_size = total_size % part_size
        if full_parts == 0:
            messagebox.showerror(
                "Split V ROM",
                f"Loaded ROM is smaller than the selected part size ({part_size} bytes).",
            )
            return

        trailing_padding_size = 0
        if remainder_size:
            remainder = self.data[full_parts * part_size :]
            if is_blank_padding(remainder):
                trailing_padding_size = len(remainder)
            else:
                messagebox.showerror(
                    "Split V ROM",
                    "ROM size is not divisible by the selected part size and the trailing data "
                    "is not blank padding (FF).",
                )
                return

        source_dir = os.path.dirname(self.file_path)
        output_dir_name = f"{os.path.splitext(file_name)[0]}_split_vrom_{part_size // (1024 * 1024)}mb"
        output_dir = os.path.join(source_dir, output_dir_name)
        os.makedirs(output_dir, exist_ok=True)

        output_items = []
        for offset in range(full_parts):
            start = offset * part_size
            end = start + part_size
            target_index = source_index + offset
            output_items.append(
                (
                    os.path.join(output_dir, build_v_rom_part_name(file_name, source_index, target_index)),
                    self.data[start:end],
                )
            )

        output_paths = [path for path, _ in output_items]
        existing_paths = [path for path in output_paths if os.path.exists(path)]
        if existing_paths and not messagebox.askyesno(
            "Split V ROM",
            "Some destination files already exist.\nOverwrite them?",
            parent=self.mem_frame,
        ):
            return

        for output_path, part_data in output_items:
            try:
                with open(output_path, "wb") as handle:
                    handle.write(part_data)
            except OSError as exc:
                messagebox.showerror("Split V ROM", f"Failed to save file:\n{exc}")
                return

        saved_message = f"Saved {len(output_items)} file(s) to:\n{output_dir}"
        if trailing_padding_size:
            saved_message += f"\n\nDiscarded trailing padding: {trailing_padding_size} bytes"
        messagebox.showinfo(
            "Split V ROM",
            saved_message,
        )

    def open_hex_viewer(self):
        if not self.data:
            messagebox.showwarning("Hex Viewer", "No file loaded.")
            return

        viewer = tk.Toplevel(self.mem_frame)
        title = self.filename_var.get() or f"ROM #{self.index}"
        viewer.title(f"Hex Viewer - {title}")
        viewer.minsize(600, 600)

        frame = ttk.Frame(viewer, padding=6)
        frame.grid(row=0, column=0, sticky="nsew")
        viewer.rowconfigure(0, weight=1)
        viewer.columnconfigure(0, weight=1)

        text = tk.Text(
            frame,
            wrap="none",
            font=("Consolas", 10),
            background="#ffffff",
        )
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        text.insert("1.0", format_hex_view(self.data))
        text.configure(state="disabled")
        center_toplevel(viewer)


class NeoConvDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"neoConv {NEOCONV_VERSION}")
        self.resizable(False, False)
        self.transient(parent)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        tabs = (
            (NeoConvExtractTab(notebook), "Extract (.neo -> files)"),
            (NeoConvPackTab(notebook), "Pack (files -> .neo)"),
            (NeoConvVerifyTab(notebook), "Verify"),
            (NeoConvInfoTab(notebook), "Info"),
        )
        for tab, label in tabs:
            notebook.add(tab, text=label)

        center_toplevel(self)
        self.focus_set()


class App:
    def __init__(self, root):
        self.root = root
        self.main_frame = None
        self.panels = []
        self._initial_layout_pending = True
        self.slot_count = tk.IntVar(value=DEFAULT_SLOTS)
        self.padding_menu = None
        self.double_menu = None
        self.split_menu = None
        self.split_interleaved_menu = None
        self.split_c_rom_menu = None
        self.split_v_rom_menu = None
        self.neoconv_window = None

        self.root.title(APP_TITLE)
        self.root.minsize(650, 500)
        self._apply_styles()

        self._build_menu()
        self._build_ui()
        self.root.after_idle(self._finalize_initial_layout)

    def _apply_styles(self):
        style = ttk.Style(self.root)
        style.configure("Info.TEntry", fieldbackground="#ffffff")
        style.map("Info.TEntry", fieldbackground=[("readonly", "#ffffff")])
        style.configure("Danger.TButton", foreground="#c62828")

    def _center_window(self):
        self.root.update_idletasks()
        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()
        min_w, min_h = self.root.minsize()
        width = max(req_w, min_w)
        height = max(req_h, min_h)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _resize_to_content(self):
        if self.main_frame is None:
            return
        self.root.update_idletasks()
        req_w = self.main_frame.winfo_reqwidth()
        req_h = self.main_frame.winfo_reqheight()
        min_w, min_h = self.root.minsize()
        width = max(req_w, min_w)
        height = max(req_h, min_h)
        self.root.geometry(f"{width}x{height}")

    def _finalize_initial_layout(self):
        if not self._initial_layout_pending:
            return
        self._resize_to_content()
        self._center_window()
        self._initial_layout_pending = False

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        slots_menu = tk.Menu(menubar, tearoff=0)
        for count in (4, 8, 12):
            slots_menu.add_radiobutton(
                label=f"{count} Slots",
                value=count,
                variable=self.slot_count,
                command=self._build_ui,
            )
        menubar.add_cascade(label="Slots", menu=slots_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        self.split_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Split", menu=self.split_menu)
        self.split_interleaved_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Split Interleaved", menu=self.split_interleaved_menu)
        tools_menu.add_command(label="Merge...", command=self.merge_files)
        tools_menu.add_command(
            label="Merge Interleaved (slots 1 & 2)",
            command=self.merge_interleaved,
        )
        tools_menu.add_separator()
        self.padding_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Padding", menu=self.padding_menu)
        self.double_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Double", menu=self.double_menu)
        self.split_c_rom_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Split C ROM", menu=self.split_c_rom_menu)
        self.split_v_rom_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Split V ROM", menu=self.split_v_rom_menu)
        tools_menu.add_separator()
        tools_menu.add_command(label="NeoTool...", command=self.open_neo_tool)
        tools_menu.add_command(label=".neoConv", command=self.open_neoconv)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        info_menu = tk.Menu(menubar, tearoff=0)
        info_menu.add_command(label="Help", command=self.show_help)
        info_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Info", menu=info_menu)
        self.root.config(menu=menubar)

    def _build_ui(self):
        if self.main_frame is not None:
            self.main_frame.destroy()

        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        info_grid = ttk.Frame(main)
        info_grid.grid(row=0, column=0, sticky="ew")
        info_grid.columnconfigure(0, weight=1)
        info_grid.columnconfigure(1, weight=1)

        mem_grid = ttk.Frame(main)
        mem_grid.grid(row=1, column=0, sticky="", pady=(6, 0))

        main.rowconfigure(0, weight=0)
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        slot_count = self.slot_count.get()
        mem_grid.rowconfigure(0, weight=1)
        for col in range(slot_count):
            mem_grid.columnconfigure(col, weight=0)

        self.panels = []
        for i in range(slot_count):
            panel = SlotPanel(info_grid, mem_grid, index=i + 1)
            info_row = i // 2
            info_col = i % 2
            panel.info_frame.grid(row=info_row, column=info_col, sticky="ew", padx=4, pady=4)
            panel.mem_frame.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)
            self.panels.append(panel)

        self.main_frame = main
        self._refresh_split_menu()
        if not self._initial_layout_pending:
            self._resize_to_content()

    def _refresh_split_menu(self):
        if self.padding_menu is not None:
            self.padding_menu.delete(0, "end")
            for panel in self.panels:
                self.padding_menu.add_command(
                    label=f"ROM #{panel.index}",
                    command=lambda p=panel: p.pad_file(),
                )
        if self.double_menu is not None:
            self.double_menu.delete(0, "end")
            for panel in self.panels:
                self.double_menu.add_command(
                    label=f"ROM #{panel.index}",
                    command=lambda p=panel: p.double_file(),
                )
        if self.split_menu is None:
            return
        self.split_menu.delete(0, "end")
        for panel in self.panels:
            self.split_menu.add_command(
                label=f"ROM #{panel.index}",
                command=lambda p=panel: p.split_file(),
            )
        if self.split_interleaved_menu is not None:
            self.split_interleaved_menu.delete(0, "end")
            for panel in self.panels:
                self.split_interleaved_menu.add_command(
                    label=f"ROM #{panel.index}",
                    command=lambda p=panel: p.split_interleaved(),
                )
        if self.split_c_rom_menu is not None:
            self.split_c_rom_menu.delete(0, "end")
            for panel in self.panels:
                panel_menu = tk.Menu(self.split_c_rom_menu, tearoff=0)
                for size_label, size_bytes in C_ROM_SPLIT_OPTIONS:
                    panel_menu.add_command(
                        label=size_label,
                        command=lambda p=panel, s=size_bytes: p.split_c_rom(s),
                    )
                self.split_c_rom_menu.add_cascade(label=f"ROM #{panel.index}", menu=panel_menu)
        if self.split_v_rom_menu is not None:
            self.split_v_rom_menu.delete(0, "end")
            for panel in self.panels:
                panel_menu = tk.Menu(self.split_v_rom_menu, tearoff=0)
                for size_label, size_bytes in V_ROM_SPLIT_OPTIONS:
                    panel_menu.add_command(
                        label=size_label,
                        command=lambda p=panel, s=size_bytes: p.split_v_rom(s),
                    )
                self.split_v_rom_menu.add_cascade(label=f"ROM #{panel.index}", menu=panel_menu)

    def merge_files(self):
        if not self.panels:
            messagebox.showwarning("Merge files", "No slots available.")
            return

        prompt = "Enter slots to merge (e.g. 1 + 2 + 3):"
        text = simpledialog.askstring("Merge files", prompt, parent=self.root)
        if text is None:
            return

        slots = [int(value) for value in re.findall(r"\d+", text)]
        if not slots:
            messagebox.showerror("Merge files", "No slot numbers found.")
            return

        max_slot = len(self.panels)
        for slot in slots:
            if slot < 1 or slot > max_slot:
                messagebox.showerror("Merge files", f"Slot {slot} is out of range.")
                return

        data_parts = []
        for slot in slots:
            panel = self.panels[slot - 1]
            if not panel.data:
                messagebox.showerror("Merge files", f"Slot {slot} has no file loaded.")
                return
            data_parts.append(panel.data)

        merged = b"".join(data_parts)
        path = filedialog.asksaveasfilename(
            title="Save merged file as",
            initialfile="merged.bin",
            parent=self.root,
        )
        if not path:
            return

        try:
            with open(path, "wb") as handle:
                handle.write(merged)
        except OSError as exc:
            messagebox.showerror("Merge files", f"Failed to save file:\n{exc}")
            return

        messagebox.showinfo("Merge files", f"Merged file saved:\n{path}")

    def open_neo_tool(self):
        folder_path = filedialog.askdirectory(
            title="Select folder to analyze",
            mustexist=True,
            parent=self.root,
        )
        if not folder_path:
            return
        candidates = find_neo_component_candidates(folder_path)
        if not any(candidates.values()):
            messagebox.showwarning("NeoTool", "Nessun file trovato.", parent=self.root)
            return
        NeoToolDialog(self.root, folder_path)

    def open_neoconv(self):
        if self.neoconv_window is not None and self.neoconv_window.winfo_exists():
            self.neoconv_window.lift()
            self.neoconv_window.focus_set()
            return
        self.neoconv_window = NeoConvDialog(self.root)
        self.neoconv_window.protocol("WM_DELETE_WINDOW", self.close_neoconv)

    def close_neoconv(self):
        if self.neoconv_window is not None and self.neoconv_window.winfo_exists():
            self.neoconv_window.destroy()
        self.neoconv_window = None

    def merge_interleaved(self):
        if len(self.panels) < 2:
            messagebox.showwarning("Merge interleaved", "Need at least 2 slots.")
            return

        panel_hi = self.panels[0]
        panel_lo = self.panels[1]
        if not panel_hi.data or not panel_lo.data:
            messagebox.showerror("Merge interleaved", "Slot 1 and 2 must be loaded.")
            return

        if len(panel_hi.data) != len(panel_lo.data):
            messagebox.showerror(
                "Merge interleaved",
                "Slot 1 and 2 must be the same size.",
            )
            return

        size = len(panel_hi.data)
        merged = bytearray(size * 2)
        hi = panel_hi.data
        lo = panel_lo.data
        for i in range(size):
            merged[i * 2] = hi[i]
            merged[i * 2 + 1] = lo[i]

        path = filedialog.asksaveasfilename(
            title="Save interleaved file as",
            initialfile="merged_interleaved.bin",
            parent=self.root,
        )
        if not path:
            return

        try:
            with open(path, "wb") as handle:
                handle.write(merged)
        except OSError as exc:
            messagebox.showerror("Merge interleaved", f"Failed to save file:\n{exc}")
            return

        messagebox.showinfo("Merge interleaved", f"Interleaved file saved:\n{path}")

    def show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("Help")
        help_window.minsize(560, 420)
        help_window.transient(self.root)

        frame = ttk.Frame(help_window, padding=8)
        frame.grid(row=0, column=0, sticky="nsew")
        help_window.rowconfigure(0, weight=1)
        help_window.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        text = tk.Text(
            frame,
            wrap="word",
            width=84,
            height=28,
            background="#ffffff",
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.insert("1.0", TOOLS_HELP_TEXT)
        text.configure(state="disabled")

        close_button = ttk.Button(help_window, text="Close", command=help_window.destroy)
        close_button.grid(row=1, column=0, pady=(0, 8))
        center_toplevel(help_window, width=760, height=560)
        close_button.focus_set()

    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("About")
        about.resizable(False, False)
        about_width = 250
        about_height = 150

        frame = ttk.Frame(about, padding=16)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        try:
            image = tk.PhotoImage(file=resource_path("about.png"))
        except tk.TclError:
            image = None

        if image is not None:
            img_label = ttk.Label(frame, image=image)
            img_label.image = image
            img_label.grid(row=0, column=0, rowspan=4, sticky="w", padx=(0, 16))

        text_col = 1 if image is not None else 0
        ttk.Label(frame, text="Rom PP", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=text_col, sticky="w"
        )
        ttk.Label(frame, text="Pierpa86").grid(row=1, column=text_col, sticky="w")
        ttk.Label(frame, text="Version 1.1").grid(row=2, column=text_col, sticky="w")
        ttk.Label(frame, text="01/05/2026").grid(row=3, column=text_col, sticky="w")
        center_toplevel(about, width=about_width, height=about_height)


def main():
    if TkinterDnD is not None:
        try:
            root = TkinterDnD.Tk()
        except (RuntimeError, tk.TclError):
            root = tk.Tk()
    else:
        root = tk.Tk()
    icon_path = resource_path("icon.ico")
    if os.path.isfile(icon_path):
        try:
            root.iconbitmap(icon_path)
        except tk.TclError:
            pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
