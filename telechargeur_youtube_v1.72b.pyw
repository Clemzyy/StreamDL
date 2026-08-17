import os
import sys
import re
import json
import shutil
import hashlib
import threading
import subprocess
import time
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "Téléchargeur Vidéo V7.3 by Clemzy"
WINDOW_SIZE = "650x780"

PROGRESS_UI_INTERVAL = 0.150
LOG_UI_INTERVAL = 1.000

AUDIO_CONVERSION_OPTIONS = [
    "Aucune conversion",
    "MP3",
    "WAV",
    "FLAC",
    "AAC",
]

VIDEO_CONVERSION_OPTIONS = [
    "Aucune conversion",
    "MP4",
    "AVI",
    "MKV",
    "WEBM",
]

SOCIAL_LINKS = [
    (
        "TikTok",
        "social_tiktok.png",
        "https://www.tiktok.com/@__clemzy__",
    ),
    (
        "YouTube",
        "social_youtube.png",
        "https://www.youtube.com/@Clemzy",
    ),
    (
        "PC32",
        "social_pc32.png",
        "https://www.pc32.fr/",
    ),
    (
        "Donation PayPal",
        "social_paypal.png",
        "https://www.paypal.com/donate/?hosted_button_id=NKCR6KK739WGS",
    ),
]

PROGRESS_RE = re.compile(
    r"\[download\]\s+(\d+(?:\.\d+)?)%\s+of\s+.*?\s+at\s+([^\s]+)\s+ETA\s+(.+)$"
)
PROGRESS_RE_NO_ETA = re.compile(
    r"\[download\]\s+(\d+(?:\.\d+)?)%\s+of\s+.*?\s+at\s+([^\s]+)$"
)
PROGRESS_RE_SIMPLE = re.compile(
    r"\[download\]\s+(\d+(?:\.\d+)?)%"
)


def get_base_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def find_downloader():
    for folder in (get_base_dir(), get_app_dir()):
        local_exe = os.path.join(folder, "yt-dlp.exe")

        if os.path.isfile(local_exe):
            return [local_exe]

    if shutil.which("yt-dlp"):
        return ["yt-dlp"]

    return [sys.executable, "-m", "yt_dlp"]


def find_ffmpeg():
    for folder in (get_base_dir(), get_app_dir()):
        local_exe = os.path.join(folder, "ffmpeg.exe")

        if os.path.isfile(local_exe):
            return local_exe

    path_ffmpeg = shutil.which("ffmpeg")
    if path_ffmpeg:
        return path_ffmpeg

    return None


def find_app_icon():
    for folder in (get_base_dir(), get_app_dir()):
        for filename in ("download.ico", "download.png"):
            icon_path = os.path.join(folder, filename)

            if os.path.isfile(icon_path):
                return icon_path

    return None


def find_asset(filename):
    for folder in (get_base_dir(), get_app_dir()):
        asset_path = os.path.join(folder, filename)

        if os.path.isfile(asset_path):
            return asset_path

    return None


def apply_app_icon(root):
    icon_path = find_app_icon()

    if not icon_path:
        return

    try:
        if icon_path.lower().endswith(".ico"):
            root.iconbitmap(icon_path)

        else:
            icon_image = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, icon_image)
            root._app_icon_image = icon_image

    except Exception:
        pass


def open_url(url):
    try:
        webbrowser.open_new_tab(url)

    except Exception as e:
        messagebox.showwarning(
            "Lien",
            f"Impossible d'ouvrir le lien.\n\n{e}"
        )


def open_folder(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showwarning("Dossier", f"Impossible d'ouvrir le dossier.\n\n{e}")


def human_size(num):
    if num is None:
        return "?"
    value = float(num)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def sha256_of_file(file_path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def clean_filename_title(title):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " - ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")

    return cleaned or "video"


def get_hidden_process_kwargs():
    kwargs = {
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }

    if sys.platform.startswith("win"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    return kwargs


def get_live_process_kwargs():
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
    }

    if sys.platform.startswith("win"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    return kwargs


class FormatSelector(tk.Toplevel):
    def __init__(self, parent, formats_list, title_text):
        super().__init__(parent)

        self.title("Choisir un format")
        self.geometry("1220x560")
        self.resizable(True, True)

        self.selected_format = None
        self.formats_list = formats_list

        self.transient(parent)
        self.grab_set()

        self.build_ui(title_text)
        self.populate()

    def build_ui(self, title_text):
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 6))

        tk.Label(
            top,
            text=title_text,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            justify="left"
        ).pack(fill="x")

        tk.Label(
            top,
            text=(
                "Conseils :\n"
                "• ⭐ automatique = meilleure vidéo + meilleur audio\n"
                "• combined = image + son\n"
                "• video only = image sans son\n"
                "• audio only = audio seul"
            ),
            justify="left",
            anchor="w"
        ).pack(fill="x", pady=(6, 0))

        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        columns = (
            "id",
            "type",
            "ext",
            "resolution",
            "fps",
            "audio",
            "video",
            "size",
            "note"
        )

        self.tree = ttk.Treeview(frame, columns=columns, show="headings")

        headings = {
            "id": "Format ID",
            "type": "Type",
            "ext": "Ext",
            "resolution": "Résolution",
            "fps": "FPS",
            "audio": "Audio",
            "video": "Vidéo",
            "size": "Taille",
            "note": "Description",
        }

        widths = {
            "id": 110,
            "type": 160,
            "ext": 70,
            "resolution": 130,
            "fps": 60,
            "audio": 140,
            "video": 170,
            "size": 100,
            "note": 420,
        }

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)

        self.tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        btns = tk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))

        tk.Button(
            btns,
            text="Choisir",
            width=14,
            command=self.choose_selected
        ).pack(side="right")

        tk.Button(
            btns,
            text="Annuler",
            width=14,
            command=self.cancel
        ).pack(side="right", padx=(0, 8))

        self.tree.bind("<Double-1>", lambda e: self.choose_selected())

    def populate(self):
        for f in self.formats_list:
            self.tree.insert(
                "",
                "end",
                values=(
                    f["format_id"],
                    f["type"],
                    f["ext"],
                    f["resolution"],
                    f["fps"],
                    f["audio"],
                    f["video"],
                    f["size"],
                    f["note"],
                ),
            )

        children = self.tree.get_children()

        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])

    def choose_selected(self):
        sel = self.tree.selection()

        if not sel:
            messagebox.showerror(
                "Erreur",
                "Choisis un format dans la liste."
            )
            return

        values = self.tree.item(sel[0], "values")
        self.selected_format = values[0]
        self.destroy()

    def cancel(self):
        self.selected_format = None
        self.destroy()


class App:
    def __init__(self, root):
        self.root = root

        self.root.title(APP_TITLE)
        apply_app_icon(self.root)
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(True, True)

        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar()

        self.audio_conversion_var = tk.StringVar(value="MP3")
        self.video_conversion_var = tk.StringVar(value="Aucune conversion")
        self.delete_audio_source_var = tk.BooleanVar(value=True)
        self.delete_video_source_var = tk.BooleanVar(value=True)
        self.playlist_mode_var = tk.BooleanVar(value=False)

        self.progress_percent_var = tk.StringVar(value="0.0 %")
        self.progress_speed_var = tk.StringVar(value="Vitesse : -")
        self.progress_eta_var = tk.StringVar(value="ETA : -")

        self.last_downloaded_file = None
        self.download_history = []
        self.selected_download_format = None
        self.selected_download_title = None
        self.selected_download_url = None
        self.selected_playlist_mode = False

        self.last_progress_ui_update = 0.0
        self.last_log_ui_update = 0.0

        self.pending_progress_percent = 0.0
        self.pending_progress_speed = "-"
        self.pending_progress_eta = "-"

        self.current_speed = "-"
        self.current_eta = "-"

        self.progress_log_start_index = None
        self.progress_log_line_exists = False

        self.current_formats_list = []
        self.social_icon_images = []

        self.build_ui()

    def build_ui(self):
        pad = {"padx": 12, "pady": 8}

        top_bar = tk.Frame(self.root)
        top_bar.pack(fill="x", padx=12, pady=(8, 2))

        links_frame = tk.Frame(top_bar)
        links_frame.pack(side="right")

        for label, icon_name, url in SOCIAL_LINKS:
            icon_path = find_asset(icon_name)
            icon_image = None

            if icon_path:
                try:
                    icon_image = tk.PhotoImage(file=icon_path)
                    self.social_icon_images.append(icon_image)

                except Exception:
                    icon_image = None

            button = tk.Button(
                links_frame,
                image=icon_image,
                text="" if icon_image else label,
                width=28 if icon_image else 10,
                height=28 if icon_image else 1,
                command=lambda link=url: open_url(link),
                relief="flat",
                cursor="hand2"
            )

            button.pack(side="left", padx=(4, 0))

        tk.Label(
            self.root,
            text="URL de la vidéo :",
            anchor="w"
        ).pack(fill="x", **pad)

        url_frame = tk.Frame(self.root)
        url_frame.pack(fill="x", padx=12)

        self.url_entry = tk.Entry(
            url_frame,
            textvariable=self.url_var,
            font=("Segoe UI", 10)
        )

        self.url_entry.pack(
            side="left",
            fill="x",
            expand=True
        )

        self.url_entry.focus_set()

        tk.Button(
            url_frame,
            text="Coller",
            width=10,
            command=self.paste_clipboard
        ).pack(side="left", padx=(8, 0))

        tk.Checkbutton(
            self.root,
            text="Autoriser le téléchargement d'une playlist complète",
            variable=self.playlist_mode_var
        ).pack(fill="x", padx=12, pady=(6, 0))

        button_style = ttk.Style()
        button_style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(18, 8)
        )

        self.choose_format_btn = ttk.Button(
            self.root,
            text="Choisir le format",
            command=self.choose_format_flow,
            style="Primary.TButton",
            width=22
        )

        self.choose_format_btn.pack(
            padx=12,
            pady=(10, 8)
        )

        audio_options_frame = tk.Frame(self.root)
        audio_options_frame.pack(fill="x", padx=12, pady=(8, 0))

        self.audio_conversion_label = tk.Label(
            audio_options_frame,
            text="Conversion audio :",
            width=18,
            anchor="w"
        )
        self.audio_conversion_label.pack(side="left")

        self.audio_conversion_combo = ttk.Combobox(
            audio_options_frame,
            textvariable=self.audio_conversion_var,
            values=AUDIO_CONVERSION_OPTIONS,
            state="readonly",
            width=24
        )

        self.audio_conversion_combo.pack(side="left", padx=(8, 0))
        self.audio_conversion_combo.current(1)

        self.delete_audio_check = tk.Checkbutton(
            audio_options_frame,
            text="Supprimer l'original après conversion",
            variable=self.delete_audio_source_var
        )
        self.delete_audio_check.pack(side="left", padx=(16, 0))

        video_options_frame = tk.Frame(self.root)
        video_options_frame.pack(fill="x", padx=12, pady=(8, 0))

        self.video_conversion_label = tk.Label(
            video_options_frame,
            text="Conversion vidéo :",
            width=18,
            anchor="w"
        )
        self.video_conversion_label.pack(side="left")

        self.video_conversion_combo = ttk.Combobox(
            video_options_frame,
            textvariable=self.video_conversion_var,
            values=VIDEO_CONVERSION_OPTIONS,
            state="readonly",
            width=24
        )

        self.video_conversion_combo.pack(side="left", padx=(8, 0))
        self.video_conversion_combo.current(0)

        self.delete_video_check = tk.Checkbutton(
            video_options_frame,
            text="Supprimer l'original après conversion",
            variable=self.delete_video_source_var
        )
        self.delete_video_check.pack(side="left", padx=(16, 0))

        tk.Label(
            self.root,
            text="Dossier de sauvegarde :",
            anchor="w"
        ).pack(fill="x", **pad)

        folder_frame = tk.Frame(self.root)
        folder_frame.pack(fill="x", padx=12)

        self.folder_entry = tk.Entry(
            folder_frame,
            textvariable=self.folder_var,
            font=("Segoe UI", 10)
        )

        self.folder_entry.pack(
            side="left",
            fill="x",
            expand=True
        )

        tk.Button(
            folder_frame,
            text="Choisir...",
            width=10,
            command=self.choose_folder
        ).pack(side="left", padx=(8, 0))

        self.start_btn = ttk.Button(
            self.root,
            text="Lancer le telechargement",
            command=self.start_download_flow,
            style="Primary.TButton",
            width=26
        )

        self.start_btn.pack(
            padx=12,
            pady=(16, 8)
        )
        self.start_btn.config(state="disabled")

        self.set_conversion_controls("none")

        self.status_label = tk.Label(
            self.root,
            text="Prêt.",
            anchor="w",
            justify="left",
            fg="#333333"
        )

        self.status_label.pack(
            fill="x",
            padx=12,
            pady=(4, 6)
        )

        progress_outer = tk.Frame(self.root)
        progress_outer.pack(fill="x", padx=12, pady=(0, 8))

        self.progress = ttk.Progressbar(
            progress_outer,
            orient="horizontal",
            mode="determinate",
            maximum=100
        )

        self.progress.pack(fill="x", pady=(0, 6))

        progress_info = tk.Frame(progress_outer)
        progress_info.pack(fill="x")

        tk.Label(
            progress_info,
            textvariable=self.progress_percent_var,
            anchor="w",
            width=12
        ).pack(side="left")

        tk.Label(
            progress_info,
            textvariable=self.progress_speed_var,
            anchor="w",
            width=24
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            progress_info,
            textvariable=self.progress_eta_var,
            anchor="w"
        ).pack(side="left", padx=(8, 0))

        history_frame = tk.LabelFrame(
            self.root,
            text="Historique des téléchargements"
        )
        history_frame.pack(fill="x", padx=12, pady=(0, 8))
        history_frame.grid_columnconfigure(0, weight=1)
        history_frame.grid_columnconfigure(1, weight=0)

        history_columns = (
            "time",
            "file",
            "conversion",
            "folder"
        )

        self.history_tree = ttk.Treeview(
            history_frame,
            columns=history_columns,
            show="headings",
            height=4
        )

        self.history_tree.heading("time", text="Heure")
        self.history_tree.heading("file", text="Fichier")
        self.history_tree.heading("conversion", text="Conversion")
        self.history_tree.heading("folder", text="Dossier")

        self.history_tree.column("time", width=80, minwidth=45, stretch=True)
        self.history_tree.column("file", width=360, minwidth=90, stretch=True)
        self.history_tree.column(
            "conversion",
            width=140,
            minwidth=70,
            stretch=True
        )
        self.history_tree.column("folder", width=420, minwidth=90, stretch=True)

        self.history_tree.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(8, 6),
            pady=8
        )
        self.history_tree.bind(
            "<Configure>",
            self.resize_history_columns
        )

        history_buttons = tk.Frame(history_frame)
        history_buttons.grid(
            row=0,
            column=1,
            sticky="n",
            padx=(0, 8),
            pady=8
        )

        tk.Button(
            history_buttons,
            text="Ouvrir dossier",
            width=14,
            command=self.open_selected_history_folder
        ).pack(fill="x")

        tk.Button(
            history_buttons,
            text="Ouvrir fichier",
            width=14,
            command=self.open_selected_history_file
        ).pack(fill="x", pady=(6, 0))

        self.log_box = tk.Text(
            self.root,
            height=14,
            wrap="word"
        )

        self.log_box.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 12)
        )

        self.log_box.insert(
            "end",
            "Le journal apparaîtra ici.\n"
        )

        self.log_box.config(state="disabled")

    def append_log(self, text):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def append_log_threadsafe(self, text):
        self.root.after(0, lambda: self.append_log(text))

    def resize_history_columns(self, event):
        total_width = max(event.width - 8, 1)
        proportions = {
            "time": 0.12,
            "file": 0.36,
            "conversion": 0.17,
            "folder": 0.35,
        }
        minimums = {
            "time": 45,
            "file": 90,
            "conversion": 70,
            "folder": 90,
        }

        for column, ratio in proportions.items():
            self.history_tree.column(
                column,
                width=max(minimums[column], int(total_width * ratio))
            )

    def set_conversion_controls(self, active_kind):
        audio_state = "readonly" if active_kind == "audio" else "disabled"
        video_state = "readonly" if active_kind == "video" else "disabled"

        self.audio_conversion_combo.config(state=audio_state)
        self.delete_audio_check.config(
            state="normal" if active_kind == "audio" else "disabled"
        )
        self.audio_conversion_label.config(
            fg="#000000" if active_kind == "audio" else "#777777"
        )

        self.video_conversion_combo.config(state=video_state)
        self.delete_video_check.config(
            state="normal" if active_kind == "video" else "disabled"
        )
        self.video_conversion_label.config(
            fg="#000000" if active_kind == "video" else "#777777"
        )

    def get_selected_format_kind(self, selected_format):
        if selected_format == "BEST_AUTO":
            return "video"

        for item in self.current_formats_list:
            if item["format_id"] == selected_format:
                if item["type"] == "audio only":
                    return "audio"

                return "video"

        return "video"

    def add_history_entry(self, file_path, conversion_text):
        folder = (
            os.path.dirname(file_path)
            if file_path
            else self.folder_var.get().strip()
        )

        item = {
            "time": time.strftime("%H:%M:%S"),
            "file": file_path or "(fichier non detecte)",
            "conversion": conversion_text,
            "folder": folder,
        }

        self.download_history.insert(0, item)

        self.history_tree.insert(
            "",
            0,
            values=(
                item["time"],
                os.path.basename(item["file"]),
                item["conversion"],
                item["folder"],
            )
        )

    def get_selected_history_item(self):
        selection = self.history_tree.selection()

        if not selection:
            messagebox.showinfo(
                "Historique",
                "Selectionne une ligne de l'historique."
            )
            return None

        index = self.history_tree.index(selection[0])

        if index >= len(self.download_history):
            return None

        return self.download_history[index]

    def open_selected_history_folder(self):
        item = self.get_selected_history_item()

        if item and item["folder"]:
            open_folder(item["folder"])

    def open_selected_history_file(self):
        item = self.get_selected_history_item()

        if not item:
            return

        file_path = item["file"]

        if file_path and os.path.isfile(file_path):
            try:
                os.startfile(file_path)  # type: ignore[attr-defined]

            except Exception as e:
                messagebox.showwarning(
                    "Fichier",
                    f"Impossible d'ouvrir le fichier.\n\n{e}"
                )

        else:
            messagebox.showinfo(
                "Fichier",
                "Le fichier n'existe plus a cet emplacement."
            )

    def replace_progress_log_line(self, text):
        self.log_box.config(state="normal")

        if not self.progress_log_line_exists:
            self.progress_log_start_index = self.log_box.index(
                "end-1c linestart"
            )

            self.log_box.insert("end", text + "\n")
            self.progress_log_line_exists = True

        else:
            start = self.progress_log_start_index
            end = self.log_box.index(f"{start} lineend +1c")

            self.log_box.delete(start, end)
            self.log_box.insert(start, text + "\n")

        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def replace_progress_log_line_threadsafe(self, text):
        self.root.after(
            0,
            lambda: self.replace_progress_log_line(text)
        )

    def clear_progress_log_line_marker(self):
        self.progress_log_start_index = None
        self.progress_log_line_exists = False

    def set_status(self, text):
        self.status_label.config(text=text)
        self.root.update_idletasks()

    def set_status_threadsafe(self, text):
        self.root.after(0, lambda: self.set_status(text))

    def reset_progress(self):
        self.progress["value"] = 0

        self.progress_percent_var.set("0.0 %")
        self.progress_speed_var.set("Vitesse : -")
        self.progress_eta_var.set("ETA : -")

        self.last_progress_ui_update = 0.0
        self.last_log_ui_update = 0.0

        self.pending_progress_percent = 0.0
        self.pending_progress_speed = "-"
        self.pending_progress_eta = "-"

        self.current_speed = "-"
        self.current_eta = "-"

        self.clear_progress_log_line_marker()

    def set_progress(self, percent, speed="-", eta="-"):
        percent = max(0, min(100, percent))

        display_speed = self.current_speed if speed in ("", "-", None) else speed
        display_eta = self.current_eta if eta in ("", "-", None) else eta

        if display_speed in ("", None):
            display_speed = "-"

        if display_eta in ("", None):
            display_eta = "-"

        self.current_speed = display_speed
        self.current_eta = display_eta

        self.progress["value"] = percent

        self.progress_percent_var.set(f"{percent:.1f} %")
        self.progress_speed_var.set(f"Vitesse : {display_speed}")
        self.progress_eta_var.set(f"ETA : {display_eta}")

    def set_progress_threadsafe(self, percent, speed="-", eta="-"):
        self.root.after(
            0,
            lambda: self.set_progress(percent, speed, eta)
        )

    def mark_progress_done_threadsafe(self):
        self.root.after(
            0,
            lambda: self.set_progress(100.0, "terminé", "0s")
        )

    def parse_progress_line(self, line):
        m = PROGRESS_RE.search(line)

        if m:
            return (
                float(m.group(1)),
                m.group(2),
                m.group(3)
            )

        m = PROGRESS_RE_NO_ETA.search(line)

        if m:
            return (
                float(m.group(1)),
                m.group(2),
                None
            )

        m = PROGRESS_RE_SIMPLE.search(line)

        if m:
            return (
                float(m.group(1)),
                None,
                None
            )

        return None

    def handle_live_output_line(self, line):
        now = time.time()
        stripped = line.strip()

        progress_info = self.parse_progress_line(line)

        if progress_info:
            percent, speed, eta = progress_info

            if speed not in (None, "", "-"):
                self.pending_progress_speed = speed

            if eta not in (None, "", "-"):
                self.pending_progress_eta = eta

            self.pending_progress_percent = percent

            if (
                now - self.last_progress_ui_update
            ) >= PROGRESS_UI_INTERVAL:

                self.set_progress_threadsafe(
                    self.pending_progress_percent,
                    self.pending_progress_speed,
                    self.pending_progress_eta
                )

                self.last_progress_ui_update = now

            if (
                now - self.last_log_ui_update
            ) >= LOG_UI_INTERVAL:

                progress_log_line = (
                    f"[progress] "
                    f"{self.pending_progress_percent:.1f}% | "
                    f"vitesse: {self.pending_progress_speed} | "
                    f"ETA: {self.pending_progress_eta}"
                )

                self.replace_progress_log_line_threadsafe(
                    progress_log_line
                )

                self.last_log_ui_update = now

            return

        lower_line = line.lower()

        if "merging formats into" in lower_line:
            self.set_status_threadsafe("Fusion en cours...")
            self.set_progress_threadsafe(
                99.0,
                "fusion",
                "presque fini"
            )

            self.append_log_threadsafe(line)

            self.clear_progress_log_line_marker()
            self.last_log_ui_update = now
            return

        if stripped:
            if (
                now - self.last_log_ui_update
            ) >= LOG_UI_INTERVAL:

                self.append_log_threadsafe(line)

                self.clear_progress_log_line_marker()
                self.last_log_ui_update = now

    def paste_clipboard(self):
        try:
            text = self.root.clipboard_get().strip()

            if text:
                self.url_var.set(text)

        except Exception:
            pass

    def choose_folder(self):
        folder = filedialog.askdirectory(
            title="Choisir le dossier de sauvegarde"
        )

        if folder:
            self.folder_var.set(folder)

    def run_command_json(self, cmd):
        result = subprocess.run(
            cmd,
            capture_output=True,
            **get_hidden_process_kwargs(),
        )

        return (
            result.returncode,
            result.stdout,
            result.stderr
        )

    def run_command_live(self, cmd):
        process = subprocess.Popen(
            cmd,
            **get_live_process_kwargs()
        )

        collected_lines = []

        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.rstrip("\n").rstrip("\r")

                collected_lines.append(line)
                self.handle_live_output_line(line)

        returncode = process.wait()

        output_text = "\n".join(collected_lines)

        return returncode, output_text

    def build_unique_output_path(self, input_file, extension):
        base = os.path.splitext(input_file)[0]
        output_file = base + extension

        if os.path.abspath(output_file) != os.path.abspath(input_file):
            if not os.path.exists(output_file):
                return output_file

        output_file = base + "_converti" + extension
        counter = 2

        while os.path.exists(output_file):
            output_file = f"{base}_converti_{counter}{extension}"
            counter += 1

        return output_file

    def build_unique_path_in_folder(self, folder, basename, extension):
        output_file = os.path.join(folder, basename + extension)
        counter = 2

        while os.path.exists(output_file):
            output_file = os.path.join(
                folder,
                f"{basename} ({counter}){extension}"
            )
            counter += 1

        return output_file

    def get_selected_format_ext(self, selected_format):
        if selected_format == "BEST_AUTO":
            return ".mp4"

        for item in self.current_formats_list:
            if item["format_id"] == selected_format:
                ext = item.get("ext") or ""

                if ext and ext != "?":
                    return "." + ext.lstrip(".")

        return ""

    def get_conversion_ext(self, conversion, is_audio_only):
        if conversion == "Aucune conversion":
            return ""

        if is_audio_only and conversion == "AAC":
            return ".m4a"

        return "." + conversion.lower()

    def rename_to_detected_title(
        self,
        file_path,
        detected_title,
        selected_format,
        conversion,
        is_audio_only
    ):
        if not file_path or not os.path.isfile(file_path):
            return file_path

        folder = os.path.dirname(file_path)
        clean_title = clean_filename_title(detected_title)

        extension = self.get_conversion_ext(
            conversion,
            is_audio_only
        )

        if not extension:
            current_ext = os.path.splitext(file_path)[1]
            selected_ext = self.get_selected_format_ext(selected_format)

            if re.fullmatch(r"\.f\d+", current_ext.lower()):
                extension = selected_ext or ".mp4"
            else:
                extension = current_ext or selected_ext or ".mp4"

        target_path = os.path.join(folder, clean_title + extension)

        if os.path.abspath(file_path) == os.path.abspath(target_path):
            return file_path

        if os.path.exists(target_path):
            target_path = self.build_unique_path_in_folder(
                folder,
                clean_title,
                extension
            )

        os.rename(file_path, target_path)

        self.append_log_threadsafe(
            f"Fichier renomme : {target_path}"
        )

        return target_path

    def choose_downloaded_media_files(self, new_files):
        media_exts = {
            ".mp4",
            ".mkv",
            ".webm",
            ".m4a",
            ".mp3",
            ".wav",
            ".flac",
            ".avi",
            ".mov",
        }

        existing = [
            f for f in new_files
            if (
                os.path.isfile(f)
                and os.path.splitext(f)[1].lower() in media_exts
            )
        ]

        existing.sort(key=lambda path: path.lower())

        return existing

    def convert_audio_file(self, input_file, output_format, ffmpeg_path):
        ext = output_format.lower()

        if ext == "aac":
            output_file = self.build_unique_output_path(input_file, ".m4a")

            codec_args = [
                "-c:a", "aac",
                "-b:a", "256k"
            ]

        elif ext == "mp3":
            output_file = self.build_unique_output_path(input_file, ".mp3")

            codec_args = [
                "-codec:a", "libmp3lame",
                "-q:a", "2"
            ]

        elif ext == "wav":
            output_file = self.build_unique_output_path(input_file, ".wav")

            codec_args = []

        elif ext == "flac":
            output_file = self.build_unique_output_path(input_file, ".flac")

            codec_args = [
                "-c:a", "flac"
            ]

        else:
            raise RuntimeError(
                f"Format audio non supporté : {output_format}"
            )

        cmd = [
            ffmpeg_path,
            "-y",
            "-i", input_file,
            "-vn",
        ] + codec_args + [output_file]

        process = subprocess.Popen(
            cmd,
            **get_live_process_kwargs()
        )

        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.rstrip("\n").rstrip("\r")

                if line.strip():
                    self.append_log_threadsafe(
                        "[ffmpeg] " + line
                    )

        returncode = process.wait()

        if returncode != 0:
            raise RuntimeError(
                f"Échec conversion {output_format}"
            )

        return output_file

    def convert_video_file(self, input_file, output_format, ffmpeg_path):
        ext = output_format.lower()

        if ext == "mp4":
            output_file = self.build_unique_output_path(input_file, ".mp4")

            codec_args = [
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
            ]

        elif ext == "avi":
            output_file = self.build_unique_output_path(input_file, ".avi")

            codec_args = [
                "-c:v", "mpeg4",
                "-q:v", "4",
                "-c:a", "libmp3lame",
                "-q:a", "3",
            ]

        elif ext == "mkv":
            output_file = self.build_unique_output_path(input_file, ".mkv")

            codec_args = [
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
            ]

        elif ext == "webm":
            output_file = self.build_unique_output_path(input_file, ".webm")

            codec_args = [
                "-c:v", "libvpx-vp9",
                "-crf", "32",
                "-b:v", "0",
                "-c:a", "libopus",
                "-b:a", "160k",
            ]

        else:
            raise RuntimeError(
                f"Format video non supporte : {output_format}"
            )

        cmd = [
            ffmpeg_path,
            "-y",
            "-i", input_file,
        ] + codec_args + [output_file]

        process = subprocess.Popen(
            cmd,
            **get_live_process_kwargs()
        )

        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.rstrip("\n").rstrip("\r")

                if line.strip():
                    self.append_log_threadsafe(
                        "[ffmpeg] " + line
                    )

        returncode = process.wait()

        if returncode != 0:
            raise RuntimeError(
                f"Echec conversion {output_format}"
            )

        return output_file

    def is_audio_only_format(
        self,
        selected_format,
        formats_list
    ):
        for f in formats_list:
            if f["format_id"] == selected_format:
                return f["type"] == "audio only"

        return False

    def choose_format_flow(self):
        url = self.url_var.get().strip()
        playlist_mode = self.playlist_mode_var.get()

        if not url:
            messagebox.showerror(
                "Erreur",
                "Colle l'URL de la vidéo."
            )
            return

        self.choose_format_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.selected_download_format = None
        self.selected_download_title = None
        self.selected_download_url = None
        self.selected_playlist_mode = playlist_mode
        self.set_conversion_controls("none")

        self.reset_progress()

        self.set_status(
            "Lecture des formats disponibles..."
        )

        self.append_log(
            "Récupération des formats disponibles..."
        )

        threading.Thread(
            target=self.fetch_formats_worker,
            args=(url, playlist_mode),
            daemon=True
        ).start()

    def start_download_flow(self):
        folder = self.folder_var.get().strip()

        if not self.selected_download_format:
            messagebox.showerror(
                "Erreur",
                "Choisis d'abord un format."
            )
            return

        if not folder:
            messagebox.showerror(
                "Erreur",
                "Choisis un dossier de sauvegarde."
            )
            return

        if not os.path.isdir(folder):
            messagebox.showerror(
                "Erreur",
                "Le dossier choisi n'existe pas."
            )
            return

        self.start_btn.config(state="disabled")
        self.choose_format_btn.config(state="disabled")

        self.reset_progress()

        self.set_status(
            "Telechargement en cours..."
        )

        threading.Thread(
            target=self.download_worker,
            args=(
                self.selected_download_url,
                folder,
                self.selected_download_format,
                self.selected_playlist_mode,
                self.selected_download_title,
            ),
            daemon=True
        ).start()

    def fetch_formats_worker(self, url, playlist_mode):
        try:
            downloader = find_downloader()

            cmd = downloader + [
                "-J",
                "--yes-playlist" if playlist_mode else "--no-playlist",
                url
            ]

            returncode, stdout_text, stderr_text = (
                self.run_command_json(cmd)
            )

            if returncode != 0:
                err = (
                    stderr_text
                    or stdout_text
                    or "Erreur inconnue"
                ).strip()

                self.root.after(
                    0,
                    lambda: self.on_fetch_error(err)
                )

                return

            data = json.loads(stdout_text)

            if playlist_mode and data.get("_type") == "playlist":
                entries = data.get("entries") or []
                first_entry = next(
                    (
                        entry for entry in entries
                        if entry and entry.get("formats")
                    ),
                    None
                )

                if first_entry:
                    data = first_entry

            formats_raw = data.get("formats", [])
            title = data.get("title", "(titre inconnu)")

            parsed = [{
                "format_id": "BEST_AUTO",
                "type": "⭐ automatique",
                "ext": "mp4",
                "resolution": "max",
                "fps": "-",
                "audio": "best",
                "video": "best",
                "size": "?",
                "note": "Meilleure qualité vidéo + audio",
            }]

            for f in formats_raw:
                acodec = f.get("acodec")
                vcodec = f.get("vcodec")

                ext = f.get("ext", "?")
                format_id = f.get("format_id", "?")

                width = f.get("width")
                height = f.get("height")

                fps = f.get("fps") or ""

                note = (
                    f.get("format_note")
                    or f.get("format")
                    or ""
                )

                filesize = (
                    f.get("filesize")
                    or f.get("filesize_approx")
                )

                if vcodec != "none" and acodec != "none":
                    ftype = "combined"

                elif vcodec != "none" and acodec == "none":
                    ftype = "video only"

                elif vcodec == "none" and acodec != "none":
                    ftype = "audio only"

                else:
                    ftype = "other"

                resolution = (
                    f"{width}x{height}"
                    if width and height
                    else (f.get("resolution") or "-")
                )

                parsed.append({
                    "format_id": format_id,
                    "type": ftype,
                    "ext": ext,
                    "resolution": resolution,
                    "fps": fps,
                    "audio": acodec if acodec else "-",
                    "video": vcodec if vcodec else "-",
                    "size": human_size(filesize),
                    "note": note,
                })

            parsed_rest = parsed[1:]

            parsed_rest.sort(
                key=lambda x: (
                    0 if x["type"] == "combined"
                    else 1 if x["type"] == "video only"
                    else 2 if x["type"] == "audio only"
                    else 3,
                    x["resolution"],
                    x["ext"],
                )
            )

            parsed = [parsed[0]] + parsed_rest

            self.root.after(
                0,
                lambda: self.show_format_dialog(
                    url,
                    parsed,
                    title,
                    playlist_mode
                )
            )

        except Exception as e:
            self.root.after(
                0,
                lambda: self.on_fetch_error(str(e))
            )

    def show_format_dialog(
        self,
        url,
        formats_list,
        title,
        playlist_mode
    ):
        self.current_formats_list = formats_list

        self.choose_format_btn.config(state="normal")

        self.set_status("Choisis un format.")

        self.append_log(
            f"{len(formats_list)} options détectées."
        )

        self.append_log(
            f"Titre détecté : {title}"
        )

        ffmpeg_path = find_ffmpeg()

        ffmpeg_msg = (
            f"ffmpeg détecté : {ffmpeg_path}"
            if ffmpeg_path
            else "ffmpeg non détecté."
        )

        dlg = FormatSelector(
            self.root,
            formats_list,
            f"Vidéo : {title}\n{ffmpeg_msg}"
        )

        self.root.wait_window(dlg)

        selected = dlg.selected_format

        if not selected:
            self.set_status("Choix annulé.")
            self.append_log("Choix du format annulé.")
            self.reset_progress()
            return

        self.append_log(
            f"Format choisi : {selected}"
        )

        self.selected_download_format = selected
        self.selected_download_title = title
        self.selected_download_url = url
        self.selected_playlist_mode = playlist_mode

        selected_kind = self.get_selected_format_kind(selected)
        self.set_conversion_controls(selected_kind)

        self.start_btn.config(state="normal")

        self.set_status(
            "Format choisi. Choisis le dossier puis lance le telechargement."
        )

    def list_files_recursive(self, folder):
        found = []

        for root_dir, _, files in os.walk(folder):
            for name in files:
                found.append(
                    os.path.join(root_dir, name)
                )

        return set(found)

    def choose_main_downloaded_file(self, new_files):
        if not new_files:
            return None

        media_exts_priority = [
            ".mp4",
            ".mkv",
            ".webm",
            ".m4a",
            ".mp3",
            ".wav",
            ".flac",
            ".avi",
            ".mov",
        ]

        existing = [
            f for f in new_files
            if os.path.isfile(f)
        ]

        if not existing:
            return None

        def score(path):
            ext = os.path.splitext(path)[1].lower()

            try:
                size = os.path.getsize(path)

            except OSError:
                size = 0

            ext_rank = (
                media_exts_priority.index(ext)
                if ext in media_exts_priority
                else 999
            )

            return (
                ext_rank,
                -size,
                path.lower()
            )

        existing.sort(key=score)

        return existing[0]

    def download_worker(
        self,
        url,
        folder,
        selected_format,
        playlist_mode,
        detected_title
    ):
        try:
            downloader = find_downloader()
            ffmpeg_path = find_ffmpeg()

            format_string = (
                "bv*+ba/b"
                if selected_format == "BEST_AUTO"
                else selected_format
            )

            before_files = self.list_files_recursive(folder)

            cmd = downloader + [
                "--continue",
                "--yes-playlist" if playlist_mode else "--no-playlist",
                "--no-part",
                "--windows-filenames",
                "--newline",
                "-f", format_string,
                "-o",
                os.path.join(
                    folder,
                    "%(title)s.%(ext)s"
                ),
                url,
            ]

            if ffmpeg_path:
                cmd.extend([
                    "--ffmpeg-location",
                    ffmpeg_path
                ])

            if selected_format == "BEST_AUTO":
                cmd.extend([
                    "--merge-output-format",
                    "mp4"
                ])

            self.set_status_threadsafe(
                "Téléchargement en cours..."
            )

            returncode, output_text = (
                self.run_command_live(cmd)
            )

            after_files = self.list_files_recursive(folder)

            new_files = list(
                after_files - before_files
            )

            media_files = self.choose_downloaded_media_files(
                new_files
            )

            main_file = self.choose_main_downloaded_file(
                new_files
            )

            converted_file = None

            is_audio_only = self.is_audio_only_format(
                selected_format,
                self.current_formats_list
            )

            selected_conversion = (
                self.audio_conversion_var.get()
            )

            selected_video_conversion = (
                self.video_conversion_var.get()
            )

            original_main_file = main_file
            extra_history_files = []

            if (
                returncode == 0
                and is_audio_only
                and selected_conversion != "Aucune conversion"
            ):
                if (
                    main_file
                    and os.path.isfile(main_file)
                    and ffmpeg_path
                ):
                    self.set_status_threadsafe(
                        f"Conversion {selected_conversion}..."
                    )

                    self.append_log_threadsafe(
                        f"Conversion audio vers "
                        f"{selected_conversion}..."
                    )

                    try:
                        converted_file = (
                            self.convert_audio_file(
                                main_file,
                                selected_conversion,
                                ffmpeg_path
                                )
                        )

                        self.append_log_threadsafe(
                            f"Conversion terminée : "
                            f"{converted_file}"
                        )

                        if self.delete_audio_source_var.get():
                            try:
                                os.remove(main_file)

                                self.append_log_threadsafe(
                                    "Fichier source supprime : "
                                    f"{main_file}"
                                )

                            except Exception:
                                pass

                        main_file = converted_file

                    except Exception as e:
                        self.append_log_threadsafe(
                            f"Erreur conversion : {e}"
                        )

            if (
                returncode == 0
                and not is_audio_only
                and selected_video_conversion != "Aucune conversion"
            ):
                if (
                    main_file
                    and os.path.isfile(main_file)
                    and ffmpeg_path
                ):
                    self.set_status_threadsafe(
                        f"Conversion video {selected_video_conversion}..."
                    )

                    self.append_log_threadsafe(
                        f"Conversion video vers "
                        f"{selected_video_conversion}..."
                    )

                    try:
                        converted_file = (
                            self.convert_video_file(
                                main_file,
                                selected_video_conversion,
                                ffmpeg_path
                            )
                        )

                        self.append_log_threadsafe(
                            f"Conversion terminee : "
                            f"{converted_file}"
                        )

                        if self.delete_video_source_var.get():
                            try:
                                os.remove(main_file)

                                self.append_log_threadsafe(
                                    f"Fichier source supprime : "
                                    f"{main_file}"
                                )

                            except Exception:
                                pass

                        main_file = converted_file

                    except Exception as e:
                        self.append_log_threadsafe(
                            f"Erreur conversion video : {e}"
                        )

                elif not ffmpeg_path:
                    self.append_log_threadsafe(
                        "Conversion video ignoree : ffmpeg non detecte."
                    )

            if (
                returncode == 0
                and playlist_mode
                and not is_audio_only
                and selected_video_conversion != "Aucune conversion"
                and ffmpeg_path
            ):
                remaining_files = [
                    path for path in media_files
                    if path != original_main_file
                ]

                for source_file in remaining_files:
                    if not os.path.isfile(source_file):
                        continue

                    try:
                        converted_file = (
                            self.convert_video_file(
                                source_file,
                                selected_video_conversion,
                                ffmpeg_path
                            )
                        )

                        extra_history_files.append(converted_file)

                        self.append_log_threadsafe(
                            f"Conversion terminee : "
                            f"{converted_file}"
                        )

                        if self.delete_video_source_var.get():
                            try:
                                os.remove(source_file)

                                self.append_log_threadsafe(
                                    f"Fichier source supprime : "
                                    f"{source_file}"
                                )

                            except Exception:
                                pass

                    except Exception as e:
                        self.append_log_threadsafe(
                            f"Erreur conversion video : {e}"
                        )

            if returncode == 0:
                rename_conversion = "Aucune conversion"

                if (
                    is_audio_only
                    and selected_conversion != "Aucune conversion"
                    and main_file != original_main_file
                ):
                    rename_conversion = selected_conversion

                elif (
                    not is_audio_only
                    and selected_video_conversion != "Aucune conversion"
                    and main_file != original_main_file
                ):
                    rename_conversion = selected_video_conversion

                if not playlist_mode and main_file:
                    try:
                        main_file = self.rename_to_detected_title(
                            main_file,
                            detected_title,
                            selected_format,
                            rename_conversion,
                            is_audio_only
                        )

                    except Exception as e:
                        self.append_log_threadsafe(
                            f"Renommage impossible : {e}"
                        )

                history_files = (
                    ([main_file] if main_file else [])
                    + extra_history_files
                )

                if (
                    playlist_mode
                    and (
                        (
                            is_audio_only
                            and selected_conversion == "Aucune conversion"
                        )
                        or (
                            not is_audio_only
                            and selected_video_conversion == "Aucune conversion"
                        )
                    )
                ):
                    history_files = media_files

                if not history_files:
                    history_files = media_files

                conversion_label = "Aucune"

                if is_audio_only:
                    if selected_conversion != "Aucune conversion":
                        conversion_label = selected_conversion

                elif selected_video_conversion != "Aucune conversion":
                    conversion_label = selected_video_conversion

                for history_file in history_files:
                    self.root.after(
                        0,
                        lambda path=history_file: self.add_history_entry(
                            path,
                            conversion_label
                        )
                    )

                self.last_downloaded_file = main_file

                self.mark_progress_done_threadsafe()

                self.root.after(
                    0,
                    lambda: self.on_success(
                        folder,
                        main_file
                    )
                )

            else:
                err = (
                    output_text
                    or "Erreur inconnue"
                ).strip()

                self.root.after(
                    0,
                    lambda: self.on_download_error(err)
                )

        except Exception as e:
            self.root.after(
                0,
                lambda: self.on_download_error(str(e))
            )

    def on_fetch_error(self, error_text):
        self.choose_format_btn.config(state="normal")
        self.start_btn.config(state="disabled")

        self.set_status(
            "Échec de lecture des formats."
        )

        self.append_log(error_text)

        messagebox.showerror(
            "Erreur",
            f"Impossible de récupérer les formats.\n\n"
            f"{error_text}"
        )

    def on_download_error(self, error_text):
        self.start_btn.config(state="normal")
        self.choose_format_btn.config(state="normal")

        self.set_status(
            "Échec du téléchargement."
        )

        self.append_log(error_text)

        messagebox.showerror(
            "Erreur",
            f"Le téléchargement a échoué.\n\n"
            f"{error_text}"
        )

    def on_success(self, folder, main_file):
        self.start_btn.config(state="normal")
        self.choose_format_btn.config(state="normal")

        self.set_status(
            "Téléchargement terminé."
        )

        self.append_log(
            "Téléchargement terminé avec succès."
        )

        self.clear_progress_log_line_marker()

        if main_file:
            self.append_log(
                f"Fichier principal détecté : "
                f"{main_file}"
            )

        else:
            self.append_log(
                "Impossible de détecter "
                "automatiquement le fichier principal."
            )

        messagebox.showinfo(
            "Succès",
            "Téléchargement terminé."
        )

        if (
            main_file
            and os.path.isfile(main_file)
        ):
            do_hash = messagebox.askyesno(
                "SHA-256",
                "Veux-tu calculer le hash "
                "SHA-256 du fichier téléchargé ?\n\n"
                "Cela peut être utile "
                "pour ton dossier de preuve."
            )

            if do_hash:
                self.set_status(
                    "Calcul du SHA-256 en cours..."
                )

                self.append_log(
                    "Calcul du SHA-256 demandé."
                )

                self.start_btn.config(state="disabled")
                self.choose_format_btn.config(state="disabled")

                threading.Thread(
                    target=self.hash_worker,
                    args=(main_file, folder),
                    daemon=True
                ).start()

                return

        open_folder(folder)

    def hash_worker(self, main_file, folder):
        try:
            digest = sha256_of_file(main_file)

            hash_txt_path = os.path.join(
                folder,
                os.path.basename(main_file)
                + ".sha256.txt"
            )

            with open(
                hash_txt_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    "Fichier : "
                    + main_file
                    + "\n"
                )

                f.write(
                    "SHA-256 : "
                    + digest
                    + "\n"
                )

            self.root.after(
                0,
                lambda: self.on_hash_success(
                    folder,
                    main_file,
                    digest,
                    hash_txt_path
                )
            )

        except Exception as e:
            self.root.after(
                0,
                lambda: self.on_hash_error(
                    folder,
                    str(e)
                )
            )

    def on_hash_success(
        self,
        folder,
        main_file,
        digest,
        hash_txt_path
    ):
        self.start_btn.config(state="normal")
        self.choose_format_btn.config(state="normal")

        self.set_status(
            "SHA-256 calculé."
        )

        self.append_log(
            f"SHA-256 de {main_file} : "
            f"{digest}"
        )

        self.append_log(
            f"Fichier de hash créé : "
            f"{hash_txt_path}"
        )

        messagebox.showinfo(
            "SHA-256 terminé",
            "Le hash SHA-256 a été calculé.\n\n"
            f"SHA-256 :\n{digest}\n\n"
            f"Enregistré dans :\n"
            f"{hash_txt_path}"
        )

        open_folder(folder)

    def on_hash_error(self, folder, error_text):
        self.start_btn.config(state="normal")
        self.choose_format_btn.config(state="normal")

        self.set_status(
            "Erreur pendant le calcul du SHA-256."
        )

        self.append_log(error_text)

        messagebox.showerror(
            "Erreur SHA-256",
            f"Impossible de calculer "
            f"le SHA-256.\n\n{error_text}"
        )

        open_folder(folder)

    def mainloop(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    app = App(root)
    app.mainloop()


if __name__ == "__main__":
    main()
