import hashlib
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import zlib

APP_TITLE = "Rom PP - Rom Wizard"

DEFAULT_SLOTS = 4

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


def center_toplevel(window):
    window.update_idletasks()
    width = window.winfo_reqwidth()
    height = window.winfo_reqheight()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class MemoryView(ttk.Frame):
    def __init__(
        self,
        parent,
        on_click,
        on_unload,
        on_split,
        on_split_interleaved,
        on_open_hex,
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
        self.on_split = on_split
        self.on_split_interleaved = on_split_interleaved
        self.on_open_hex = on_open_hex
        self.has_data = False
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
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Unload", command=self._handle_unload)
        self.menu.add_command(label="Split...", command=self._handle_split)
        self.menu.add_command(label="Split Interleaved...", command=self._handle_split_interleaved)
        self.menu.add_command(label="Hex Viewer...", command=self._handle_open_hex)
        self._draw_chip()
        self.set_data(None, None, None)

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

    def _handle_split(self):
        if self.on_split:
            self.on_split()

    def _handle_split_interleaved(self):
        if self.on_split_interleaved:
            self.on_split_interleaved()

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
        grid_width = grid_right - grid_x
        grid_height = grid_bottom - grid_y

        self.canvas.create_rectangle(
            grid_x,
            grid_y,
            grid_right,
            grid_bottom,
            fill=WINDOW_BG,
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
            on_split=self.split_file,
            on_split_interleaved=self.split_interleaved,
            on_open_hex=self.open_hex_viewer,
        )
        self.mem_view.grid(row=0, column=0, sticky="nsew")

    def load_file(self):
        path = filedialog.askopenfilename(
            title=f"Select ROM #{self.index}",
            filetypes=[("Binary files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            messagebox.showerror("Load error", f"Failed to read file:\n{exc}")
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


class App:
    def __init__(self, root):
        self.root = root
        self.main_frame = None
        self.panels = []
        self.slot_count = tk.IntVar(value=DEFAULT_SLOTS)
        self.split_menu = None
        self.split_interleaved_menu = None

        self.root.title(APP_TITLE)
        self.root.minsize(650, 500)
        self._apply_styles()

        self._build_menu()
        self._build_ui()
        self._center_window()

    def _apply_styles(self):
        style = ttk.Style(self.root)
        style.configure("Info.TEntry", fieldbackground="#ffffff")
        style.map("Info.TEntry", fieldbackground=[("readonly", "#ffffff")])

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
        menubar.add_cascade(label="Tools", menu=tools_menu)

        info_menu = tk.Menu(menubar, tearoff=0)
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
        self._resize_to_content()

    def _refresh_split_menu(self):
        if self.split_menu is None:
            return
        self.split_menu.delete(0, "end")
        for panel in self.panels:
            self.split_menu.add_command(
                label=f"ROM #{panel.index}",
                command=lambda p=panel: p.split_file(),
            )
        if self.split_interleaved_menu is None:
            return
        self.split_interleaved_menu.delete(0, "end")
        for panel in self.panels:
            self.split_interleaved_menu.add_command(
                label=f"ROM #{panel.index}",
                command=lambda p=panel: p.split_interleaved(),
            )

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

    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("About")
        about.resizable(False, False)
        about.geometry("250x200")

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
        ttk.Label(frame, text="Version 1.0").grid(row=2, column=text_col, sticky="w")
        ttk.Label(frame, text="30/12/2025").grid(row=3, column=text_col, sticky="w")
        center_toplevel(about)


def main():
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
