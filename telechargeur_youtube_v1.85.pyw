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
from dataclasses import replace
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from auth_support import (
    AuthErrorDetector,
    AuthErrorInfo,
    AuthErrorType,
    CookiePreferenceStore,
    CookieSource,
    CookieSourceKind,
    create_youtube_only_cookie_copy,
    delete_temporary_cookie_file,
    find_chrome_download_folder,
    find_firefox,
    find_windows_downloads_folder,
    sanitize_technical_text,
    validate_netscape_cookie_file,
)
from tools_manager import (
    DENO,
    FFMPEG,
    MB,
    TOOL_SPECS,
    YTDLP,
    ChecksumMismatch,
    default_storage_dir,
    describe_error,
    fetch_latest_release,
    find_installed_copies,
    install_release,
    is_check_due,
    is_newer_release,
    record_check,
    remove_legacy_copies,
    remove_superseded_copies,
    resolve_tool,
    find_exe_on_path,
    run_version_command,
)


# Windows otherwise searches the current folder first for executables found
# through PATH; child processes such as yt-dlp inherit this setting.
os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"

APP_VERSION = "1.85"
APP_TITLE = f"Téléchargeur Vidéo v{APP_VERSION} by Clemzy"
WINDOW_SIZE = "650x780"

PROGRESS_UI_INTERVAL = 0.150
LOG_UI_INTERVAL = 1.000

TOOL_LABELS = {
    "yt-dlp": "yt-dlp",
    "deno": "Deno",
    "ffmpeg": "ffmpeg",
}

# One-click shortcuts: format asked to yt-dlp, then conversions applied.
PRESETS = {
    "video": {
        "format": "BEST_AUTO",
        "audio_conversion": "MP3",
        "video_conversion": "Aucune conversion",
        "label": "Vidéo MP4 (meilleure qualité)",
    },
    "audio": {
        "format": "BEST_AUDIO",
        "audio_conversion": "MP3",
        "video_conversion": "Aucune conversion",
        "label": "Audio MP3",
    },
}

SUCCESS_COLOR = "#1E7B34"
CANCEL_COLOR = "#8A5200"

# Files written by yt-dlp, removed if the download is cancelled.
YTDLP_OUTPUT_RES = (
    re.compile(r"^\[download\] Destination: (.+)$"),
    re.compile(r'^\[Merger\] Merging formats into "(.+)"$'),
)
CLIPBOARD_URL_RE = re.compile(r"https?://\S{1,2000}", re.IGNORECASE)

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

COOKIE_BROWSER_OPTIONS = [
    "Aucun",
    "Chrome",
    "Edge",
    "Firefox",
    "Brave",
    "Opera",
]

COOKIE_BROWSER_IDS = {
    "Chrome": "chrome",
    "Edge": "edge",
    "Firefox": "firefox",
    "Brave": "brave",
    "Opera": "opera",
}

# Referenced by the official yt-dlp FAQ for a manual Netscape cookies.txt export.
# This is intentionally a manual, opt-in fallback: the application never exports
# browser cookies and never receives their contents.
CHROME_COOKIE_EXPORT_EXTENSION_URL = (
    "https://chromewebstore.google.com/detail/get-cookiestxt-locally/"
    "cclelndahbckbenkjhflpdbgdldlbecc"
)

AUTH_ERROR_SUMMARIES = {
    AuthErrorType.AGE_RESTRICTED: (
        "Cette vidéo nécessite probablement une vérification d'âge.",
        "Le site demande de vérifier ton compte ou ton âge avant de donner accès à la vidéo.",
    ),
    AuthErrorType.LOGIN_REQUIRED: (
        "Cette vidéo nécessite probablement une connexion.",
        "Le site demande une session connectée pour accéder à ce contenu.",
    ),
    AuthErrorType.COOKIES_REQUIRED: (
        "Cette vidéo nécessite des cookies de session.",
        "yt-dlp indique qu'une session de navigateur est nécessaire pour continuer.",
    ),
    AuthErrorType.COOKIE_EXTRACTION_FAILED: (
        "Impossible de lire les cookies du navigateur choisi.",
        "Tes cookies ne sont pas endommagés : Windows ou le navigateur peut empêcher une application externe de les lire.",
    ),
    AuthErrorType.COOKIE_DECRYPTION_FAILED: (
        "Impossible de déchiffrer les cookies du navigateur choisi.",
        "Tes cookies ne sont pas endommagés : la protection de Windows ou du navigateur peut empêcher yt-dlp de les utiliser.",
    ),
    AuthErrorType.COOKIES_EXPIRED_OR_INVALID: (
        "Les cookies utilisés ne semblent plus utilisables.",
        "La session a peut-être expiré, le compte n'est peut-être pas connecté au site, ou le site a refusé ces cookies.",
    ),
    AuthErrorType.UNKNOWN_AUTH_ERROR: (
        "Cette vidéo semble nécessiter une authentification.",
        "Le site demande probablement de vérifier ton compte, ton âge ou ta session.",
    ),
}

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
    (
        "GitHub du projet",
        "social_github.png",
        "https://github.com/Clemzyy/StreamDL",
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


def is_nuitka_build():
    return "__compiled__" in globals()


def is_packaged_build():
    return getattr(sys, "frozen", False) or is_nuitka_build()


def get_base_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    if is_nuitka_build():
        # Nuitka unpacks the program and its data files beside this module.
        return os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    if is_nuitka_build():
        # Folder of the onefile executable the user started, not the unpack folder.
        original = getattr(__compiled__, "original_argv0", None)  # type: ignore[name-defined]  # noqa: F821
        return os.path.dirname(os.path.abspath(original or sys.argv[0]))
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_local_tool_dirs():
    # A packaged build trusts only the tools embedded in it (--full), never
    # an exe dropped beside StreamDL.exe, e.g. in the Downloads folder.
    # Running the .pyw uses the tools of the source folder.
    if is_packaged_build():
        return [get_base_dir()]
    return [get_app_dir()]


def find_on_path(name):
    # Development only: a packaged build uses verified or embedded tools.
    return None if is_packaged_build() else find_exe_on_path(name)


def remove_old_app_caches():
    # Each Nuitka build is unpacked once into its own folder,
    # %LOCALAPPDATA%\StreamDL\app\<build id>; earlier builds are removed.
    if not is_nuitka_build():
        return

    current = os.path.normcase(os.path.abspath(get_base_dir()))
    cache_root = os.path.dirname(current)
    # Paths are compared in normcase form: lowercase on Windows.
    if (
        os.path.basename(cache_root) != os.path.normcase("app")
        or os.path.basename(os.path.dirname(cache_root))
        != os.path.normcase("StreamDL")
    ):
        return

    for name in os.listdir(cache_root):
        entry = os.path.normcase(os.path.join(cache_root, name))
        if os.path.isdir(entry) and entry != current:
            shutil.rmtree(entry, ignore_errors=True)


def find_downloader(preferred_path=None):
    # The startup tools check selects a local or verified managed copy.
    if preferred_path and os.path.isfile(preferred_path):
        return [preferred_path]

    path_downloader = find_on_path("yt-dlp")
    if path_downloader:
        return [path_downloader]

    if is_packaged_build():
        # sys.executable is StreamDL itself here, not a Python interpreter.
        raise RuntimeError(
            "yt-dlp n'est pas installé. Clique sur « Réessayer » en haut "
            "de la fenêtre."
        )

    return [sys.executable, "-m", "yt_dlp"]


def find_ffmpeg(preferred_path=None):
    if preferred_path and os.path.isfile(preferred_path):
        return preferred_path

    path_ffmpeg = find_on_path("ffmpeg")
    if path_ffmpeg:
        return path_ffmpeg

    return None


def find_js_runtime(deno_path=None):
    # Deno is the runtime officially recommended by yt-dlp for YouTube EJS.
    # The startup tools check provides a local or verified managed copy.
    if deno_path and os.path.isfile(deno_path):
        return "deno", deno_path

    path_deno = find_on_path("deno")
    if path_deno:
        return "deno", path_deno

    # Keep compatibility with existing portable Node deployments.
    for folder in get_local_tool_dirs():
        node_path = os.path.join(folder, "node.exe")

        if os.path.isfile(node_path):
            return "node", node_path

    path_node = find_on_path("node")
    if path_node:
        return "node", path_node

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


def open_path(path):
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except Exception as e:
        messagebox.showwarning("Ouverture", f"Impossible d'ouvrir :\n{path}\n\n{e}")


def kill_process_tree(process):
    # yt-dlp.exe starts a second process, which starts ffmpeg: stopping only
    # the first one would leave the download running.
    if process.poll() is not None:
        return

    if sys.platform.startswith("win"):
        taskkill = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32",
            "taskkill.exe"
        )
        try:
            subprocess.run(
                [taskkill, "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                timeout=15,
                **get_hidden_process_kwargs(),
            )
            return
        except (OSError, subprocess.SubprocessError):
            pass

    process.kill()


class AppSettings:
    """Small preferences stored in %LOCALAPPDATA%\\StreamDL\\settings.json."""

    def __init__(self, folder):
        self.path = os.path.join(folder, "settings.json")

    def read(self):
        try:
            with open(self.path, encoding="utf-8") as settings_file:
                data = json.load(settings_file)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, key):
        return self.read().get(key)

    def set(self, key, value):
        data = self.read()
        data[key] = value
        temporary_path = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(temporary_path, "w", encoding="utf-8") as settings_file:
                json.dump(data, settings_file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.path)
        except OSError:
            pass


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


class AuthenticationAssistant(tk.Toplevel):
    """Compact, opt-in recovery window for yt-dlp authentication failures."""

    def __init__(self, parent, error_info, firefox_path, remembered_cookie_path, callbacks):
        super().__init__(parent)
        self.error_info = error_info
        self.firefox_path = firefox_path
        self.remembered_cookie_path = remembered_cookie_path
        self.callbacks = callbacks
        self.details_visible = False

        self.title("Aide à l'authentification")
        self.geometry("620x500")
        self.minsize(560, 445)
        self.resizable(True, True)
        apply_app_icon(self)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.build_ui()

    def build_ui(self):
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=18, pady=16)

        title, explanation = AUTH_ERROR_SUMMARIES[self.error_info.error_type]
        tk.Label(
            frame,
            text=title,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            justify="left",
        ).pack(fill="x")
        tk.Label(
            frame,
            text=explanation + "\n\nLe logiciel peut essayer plusieurs méthodes simples.",
            anchor="w",
            justify="left",
            wraplength=560,
        ).pack(fill="x", pady=(8, 14))

        action_frame = tk.Frame(frame)
        action_frame.pack(fill="x")

        if self.firefox_path:
            firefox_text = "Utiliser ma connexion Firefox  —  Recommandé"
            firefox_state = "normal"
        else:
            firefox_text = "Firefox n'a pas été détecté sur cet ordinateur"
            firefox_state = "disabled"
        tk.Button(
            action_frame,
            text=firefox_text,
            command=self.use_firefox,
            state=firefox_state,
            anchor="w",
        ).pack(fill="x", pady=(0, 7), ipady=4)

        tk.Label(
            action_frame,
            text=(
                "Si tu es connecté au site dans Firefox, yt-dlp utilisera temporairement "
                "les cookies de cette session. Aucune copie n'est conservée."
            ),
            fg="#555555",
            anchor="w",
            justify="left",
            wraplength=555,
        ).pack(fill="x", padx=4, pady=(0, 10))

        tk.Button(
            action_frame,
            text="Exporter un cookies.txt depuis Chrome (méthode manuelle)",
            command=self.open_chrome_cookie_export_help,
            anchor="w",
        ).pack(fill="x", pady=(0, 4), ipady=2)
        tk.Label(
            action_frame,
            text=(
                "Étapes : installe l'extension, clique sur « Export All Cookies », ouvre le "
                "dossier de téléchargement Chrome ci-dessous, puis choisis le fichier. "
                "Préfère Firefox si possible et n'utilise cette méthode que sur ton ordinateur personnel."
            ),
            fg="#8A5200",
            anchor="w",
            justify="left",
            wraplength=555,
        ).pack(fill="x", padx=4, pady=(0, 10))

        tk.Button(
            action_frame,
            text="Ouvrir le dossier de téléchargement Chrome",
            command=self.open_chrome_download_folder,
            anchor="w",
        ).pack(fill="x", pady=(0, 7), ipady=2)

        tk.Button(
            action_frame,
            text="Choisir un fichier cookies.txt",
            command=self.choose_cookie_file,
            anchor="w",
        ).pack(fill="x", pady=(0, 7), ipady=4)

        if self.remembered_cookie_path and os.path.isfile(self.remembered_cookie_path):
            tk.Button(
                action_frame,
                text="Réutiliser le fichier cookies.txt mémorisé",
                command=self.use_remembered_cookie_file,
                anchor="w",
            ).pack(fill="x", pady=(0, 7), ipady=4)
            tk.Button(
                action_frame,
                text="Oublier le fichier mémorisé",
                command=lambda: self.callbacks["forget_remembered_cookie_file"](self),
                anchor="w",
            ).pack(fill="x", pady=(0, 7), ipady=2)

        # A repeat can help for transient account/rate checks, but is omitted
        # for explicit age restrictions and browser decryption failures.
        if self.error_info.error_type in {
            AuthErrorType.LOGIN_REQUIRED,
            AuthErrorType.UNKNOWN_AUTH_ERROR,
        }:
            tk.Button(
                action_frame,
                text="Réessayer normalement",
                command=self.retry_normally,
                anchor="w",
            ).pack(fill="x", pady=(0, 7), ipady=3)

        footer = tk.Frame(frame)
        footer.pack(fill="x", side="bottom", pady=(12, 0))
        tk.Button(footer, text="En savoir plus", command=self.toggle_details).pack(side="left")
        tk.Button(footer, text="Annuler", command=self.destroy).pack(side="right")

    def _run_callback(self, name, *args):
        self.destroy()
        self.callbacks[name](*args)

    def use_firefox(self):
        self._run_callback("use_firefox")

    def choose_cookie_file(self):
        self.callbacks["choose_cookie_file"](self)

    def use_remembered_cookie_file(self):
        self._run_callback("use_remembered_cookie_file")

    def retry_normally(self):
        self._run_callback("retry_normally")

    def open_chrome_cookie_export_help(self):
        """Ask for informed consent before opening the third-party extension page."""
        should_open = messagebox.askokcancel(
            "Exporter les cookies depuis Chrome",
            "Firefox reste la méthode recommandée.\n\n"
            "Cette solution manuelle utilise une extension Chrome pour créer un fichier "
            "cookies.txt lisible par yt-dlp. Ce fichier peut contenir des données donnant "
            "accès à ta session sur plusieurs sites : traite-le comme un mot de passe.\n\n"
            "Ne l'utilise pas sur un ordinateur public, partagé ou professionnel, et ne "
            "transmets jamais le fichier à quelqu'un.\n\n"
            "Le navigateur va ouvrir la page Chrome Web Store de « Get cookies.txt LOCALLY », "
            "citée par la FAQ de yt-dlp.\n\n"
            "Après son installation, ouvre l'extension dans Chrome et clique sur le grand bouton "
            "bleu « Export All Cookies ». Chrome enregistrera le fichier dans son dossier de "
            "téléchargement. Utilise ensuite le bouton « Ouvrir le dossier de téléchargement Chrome » "
            "dans cette fenêtre, puis choisis le fichier créé ici. Le logiciel en utilisera "
            "uniquement une copie temporaire limitée à YouTube.",
            parent=self,
        )
        if not should_open:
            return

        try:
            opened = webbrowser.open(CHROME_COOKIE_EXPORT_EXTENSION_URL)
        except Exception as exc:
            messagebox.showerror(
                "Ouverture impossible",
                f"Impossible d'ouvrir le Chrome Web Store.\n\n{exc}",
                parent=self,
            )
            return

        if not opened:
            messagebox.showwarning(
                "Ouverture du navigateur",
                "Le navigateur n'a pas pu être ouvert automatiquement. Tu peux chercher "
                "« Get cookies.txt LOCALLY » dans le Chrome Web Store.",
                parent=self,
            )

    def open_chrome_download_folder(self):
        folder = find_chrome_download_folder()
        if not folder:
            messagebox.showinfo(
                "Dossier Chrome non détecté",
                "Ni le dossier configuré dans Chrome ni le dossier Téléchargements Windows n'ont été détectés. "
                "Après l'export, utilise « Choisir un fichier cookies.txt » pour sélectionner "
                "manuellement le fichier téléchargé.",
                parent=self,
            )
            return
        open_folder(folder)

    def toggle_details(self):
        if self.details_visible:
            self.details_box.destroy()
            self.details_visible = False
            self.geometry("620x500")
            return

        source = self.error_info.cookie_source.label()
        technical = self.error_info.safe_output or "(yt-dlp n'a pas fourni de détail supplémentaire.)"
        details = (
            "Pourquoi cela arrive\n"
            "Certaines vidéos demandent une session connectée, une vérification d'âge ou une vérification anti-robot.\n\n"
            "Méthodes disponibles\n"
            "Firefox est recommandé : il évite souvent les limites des navigateurs Chromium sous Windows. "
            "Tu peux aussi sélectionner un fichier Netscape cookies.txt. En dernier recours, le bouton "
            "« Exporter un cookies.txt depuis Chrome » ouvre une extension citée par la FAQ officielle de yt-dlp. "
            "Installe-la uniquement sur un ordinateur personnel. Dans l'extension, clique sur « Export All Cookies », "
            "ouvre ensuite le dossier de téléchargement Chrome avec le bouton prévu, puis sélectionne le fichier ici. "
            "Un cookies.txt peut contenir des sessions de plusieurs sites : ne le partage pas, et évite de mémoriser "
            "son emplacement sur un ordinateur partagé.\n\n"
            "Chromium sous Windows\n"
            "Chrome et plusieurs navigateurs Chromium utilisent des protections comme DPAPI et App-Bound Encryption. "
            "Selon Windows et le navigateur, yt-dlp peut ne pas réussir à lire leurs cookies. Le logiciel ne désactive "
            "jamais ces protections.\n\n"
            "Détails techniques\n"
            f"Catégorie : {self.error_info.error_type.value}\n"
            f"Code de retour yt-dlp : {self.error_info.returncode}\n"
            f"Source de cookies : {source}\n\n"
            f"Message yt-dlp :\n{technical}"
        )
        self.details_box = tk.Text(self, height=13, wrap="word")
        self.details_box.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.details_box.insert("1.0", details)
        self.details_box.config(state="disabled")
        self.details_visible = True
        self.geometry("620x700")


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
        self.cookies_browser_var = tk.StringVar(value="Aucun")
        self.create_sha256_var = tk.BooleanVar(value=False)

        self.progress_percent_var = tk.StringVar(value="0.0 %")
        self.progress_speed_var = tk.StringVar(value="Vitesse : -")
        self.progress_eta_var = tk.StringVar(value="ETA : -")

        self.last_downloaded_file = None
        self.download_history = []
        self.selected_download_format = None
        self.selected_download_title = None
        self.selected_download_url = None
        self.selected_playlist_mode = False
        self.selected_cookies_browser = "Aucun"
        self.selected_cookie_source = CookieSource.none()
        self.auth_preferences = CookiePreferenceStore()
        self.pending_cookie_file_for_preference = None
        self.temporary_cookie_file_paths = set()
        self.last_auth_error_info = None
        self.tool_storage_dir = default_storage_dir()
        self.tool_copies = {}
        self.tool_status = {}
        self.tools_status_var = tk.StringVar()
        self.tools_worker_running = False
        self.choose_blocked_by_tools = False
        self.start_blocked_by_tools = False
        self.settings = AppSettings(os.path.dirname(self.tool_storage_dir))
        self.folder_var.set(self.initial_download_folder())
        self.pending_preset = None
        self.current_process = None
        self.cancel_requested = False
        self.current_download_outputs = []
        self.last_auto_pasted = None
        self.last_result_file = None
        self.last_result_folder = None
        self.show_details_var = tk.BooleanVar(value=False)

        self.root.protocol("WM_DELETE_WINDOW", self.on_application_close)

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

        self.resolve_tools()
        self.build_ui()
        self.render_tools_status()
        self.enable_choose_format_button()
        self.root.bind("<Activate>", self.auto_paste_clipboard, add="+")
        # Started once the window is drawn, so it never delays the first paint.
        self.tools_worker_after_id = self.root.after(
            300,
            self.start_tools_worker
        )

    def build_ui(self):
        pad = {"padx": 12, "pady": 8}

        top_bar = tk.Frame(self.root)
        top_bar.pack(fill="x", padx=12, pady=(8, 2))

        tk.Label(
            top_bar,
            textvariable=self.tools_status_var,
            fg="#666666",
            anchor="w"
        ).pack(side="left")

        # Shown only when a first-launch installation failed.
        self.tools_retry_btn = tk.Button(
            top_bar,
            text="Réessayer",
            command=self.start_tools_worker
        )

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
        self.url_entry.bind("<Return>", self.on_url_return)

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

        self.cookies_frame = tk.Frame(self.root)
        self.cookies_frame.pack(fill="x", padx=12, pady=(4, 0))

        tk.Label(
            self.cookies_frame,
            text="Cookies YouTube :",
            width=18,
            anchor="w"
        ).pack(side="left")

        self.cookies_browser_combo = ttk.Combobox(
            self.cookies_frame,
            textvariable=self.cookies_browser_var,
            values=COOKIE_BROWSER_OPTIONS,
            state="readonly",
            width=22
        )
        self.cookies_browser_combo.pack(side="left", padx=(8, 0))
        self.cookies_browser_combo.current(0)

        tk.Button(
            self.cookies_frame,
            text="Aide à l'authentification",
            command=self.open_authentication_assistant_manually,
        ).pack(side="left", padx=(12, 0))

        tk.Label(
            self.root,
            text="Choisis ton navigateur seulement si YouTube demande une connexion.",
            fg="#666666",
            anchor="w"
        ).pack(fill="x", padx=12)

        button_style = ttk.Style()
        button_style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(18, 8)
        )

        # One click for the usual cases; « Format avancé... » keeps the full list.
        self.actions_frame = tk.Frame(self.root)
        self.actions_frame.pack(padx=12, pady=(8, 4))

        self.video_preset_btn = ttk.Button(
            self.actions_frame,
            text="Vidéo MP4",
            command=lambda: self.start_preset("video"),
            style="Primary.TButton",
            width=14
        )
        self.video_preset_btn.pack(side="left")

        self.audio_preset_btn = ttk.Button(
            self.actions_frame,
            text="Audio MP3",
            command=lambda: self.start_preset("audio"),
            style="Primary.TButton",
            width=14
        )
        self.audio_preset_btn.pack(side="left", padx=(8, 0))

        self.choose_format_btn = ttk.Button(
            self.actions_frame,
            text="Format avancé...",
            command=self.choose_format_flow,
            width=16
        )
        self.choose_format_btn.pack(side="left", padx=(8, 0), ipady=4)

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

        tk.Checkbutton(
            self.root,
            text="Créer un fichier SHA-256 avec le téléchargement",
            variable=self.create_sha256_var,
        ).pack(fill="x", padx=12, pady=(6, 0))

        start_frame = tk.Frame(self.root)
        start_frame.pack(padx=12, pady=(8, 4))

        self.start_btn = ttk.Button(
            start_frame,
            text="Lancer le téléchargement",
            command=self.start_download_flow,
            style="Primary.TButton",
            width=26
        )
        self.start_btn.pack(side="left")
        self.start_btn.config(state="disabled")

        self.cancel_btn = ttk.Button(
            start_frame,
            text="Annuler",
            command=self.cancel_download,
            width=10,
            state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=(8, 0), ipady=4)

        self.set_conversion_controls("none")

        status_row = tk.Frame(self.root)
        status_row.pack(fill="x", padx=12, pady=(2, 4))

        self.status_label = tk.Label(
            status_row,
            text="Prêt.",
            anchor="w",
            justify="left",
            fg="#333333"
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        # Shown after a download, instead of a dialog box.
        self.result_frame = tk.Frame(status_row)
        self.open_result_file_btn = tk.Button(
            self.result_frame,
            text="Ouvrir le fichier",
            command=self.open_result_file
        )
        self.open_result_file_btn.pack(side="left")
        tk.Button(
            self.result_frame,
            text="Ouvrir le dossier",
            command=self.open_result_folder
        ).pack(side="left", padx=(6, 0))

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
            height=3
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

        log_header = tk.Frame(self.root)
        log_header.pack(fill="x", padx=12)

        tk.Label(log_header, text="Journal", anchor="w").pack(side="left")

        tk.Checkbutton(
            log_header,
            text="Afficher les détails techniques",
            variable=self.show_details_var,
            command=self.toggle_details_visibility
        ).pack(side="right")

        self.log_box = tk.Text(
            self.root,
            height=14,
            wrap="word"
        )
        # Raw yt-dlp and ffmpeg output, hidden unless the user asks for it.
        self.log_box.tag_configure("detail", elide=True, foreground="#777777")

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

    def append_log(self, text, detail=False):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n", ("detail",) if detail else ())
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def append_log_threadsafe(self, text, detail=False):
        self.root.after(0, lambda: self.append_log(text, detail))

    def toggle_details_visibility(self):
        self.log_box.tag_configure(
            "detail",
            elide=not self.show_details_var.get()
        )
        self.log_box.see("end")

    def tool_path(self, name):
        copy = self.tool_copies.get(name)
        return copy.path if copy else None

    def tool_label(self, spec, copy):
        label = TOOL_LABELS[spec.name]
        # ffmpeg builds are named by date, which means little to the user.
        if copy and copy.version and spec is not FFMPEG:
            return f"{label} {copy.version}"
        return f"{label} ✓"

    def resolve_tools(self):
        # Instant: nothing is executed, so the window opens without waiting.
        local_dirs = get_local_tool_dirs()
        for spec in TOOL_SPECS:
            copy = resolve_tool(
                spec,
                local_dirs,
                self.tool_storage_dir,
                allow_path=not is_packaged_build()
            )
            if copy:
                self.tool_copies[spec.name] = copy
                self.tool_status[spec.name] = self.tool_label(spec, copy)
            elif spec is DENO and find_js_runtime() is not None:
                self.tool_status[spec.name] = "Node ✓"
            else:
                self.tool_status[spec.name] = (
                    f"{TOOL_LABELS[spec.name]} : à installer"
                )

    def render_tools_status(self):
        self.tools_status_var.set(
            " · ".join(self.tool_status[spec.name] for spec in TOOL_SPECS)
        )

    def set_tool_status_threadsafe(self, name, text):
        def apply():
            self.tool_status[name] = text
            self.render_tools_status()

        self.root.after(0, apply)

    def set_tool_copy_threadsafe(self, spec, copy):
        def apply():
            self.tool_copies[spec.name] = copy
            self.tool_status[spec.name] = self.tool_label(spec, copy)
            self.render_tools_status()
            self.on_tools_changed()

        self.root.after(0, apply)

    def tools_ready_for_formats(self):
        return (
            self.tool_path("yt-dlp") is not None
            and find_js_runtime(self.tool_path("deno")) is not None
        )

    def tools_ready_for_download(self):
        return (
            self.tools_ready_for_formats()
            and find_ffmpeg(self.tool_path("ffmpeg")) is not None
        )

    def enable_choose_format_button(self):
        ready = self.tools_ready_for_formats()
        self.choose_format_btn.config(state="normal" if ready else "disabled")
        # The shortcuts also need ffmpeg: merging into MP4, converting to MP3.
        presets_ready = self.tools_ready_for_download()
        for button in (self.video_preset_btn, self.audio_preset_btn):
            button.config(state="normal" if presets_ready else "disabled")
        self.choose_blocked_by_tools = not presets_ready

    def enable_start_button(self):
        ready = self.tools_ready_for_download()
        self.start_btn.config(state="normal" if ready else "disabled")
        self.start_blocked_by_tools = not ready

    def disable_action_buttons(self):
        # The running step re-enables the buttons itself when it ends.
        self.choose_format_btn.config(state="disabled")
        self.video_preset_btn.config(state="disabled")
        self.audio_preset_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.choose_blocked_by_tools = False
        self.start_blocked_by_tools = False
        self.hide_result()

    def on_tools_changed(self):
        if self.choose_blocked_by_tools:
            self.enable_choose_format_button()
        if self.start_blocked_by_tools:
            self.enable_start_button()

    def start_tools_worker(self):
        if self.tools_worker_running:
            return
        self.tools_worker_running = True
        self.tools_retry_btn.pack_forget()
        threading.Thread(
            target=self.tools_worker,
            daemon=True
        ).start()

    def tool_needs_install(self, spec):
        copy = self.tool_copies.get(spec.name)
        if spec is YTDLP:
            # A yt-dlp found on PATH may be too old for YouTube.
            return copy is None or copy.source == "path"
        if spec is DENO:
            return copy is None and find_js_runtime() is None
        return copy is None

    def tools_worker(self):
        # yt-dlp is checked at each launch: it often needs a new release
        # within days when YouTube changes. Deno and ffmpeg are checked every
        # 30 days. Present tools keep working while checks and updates run.
        try:
            missing = [
                TOOL_LABELS[spec.name]
                for spec in TOOL_SPECS
                if self.tool_needs_install(spec)
            ]
            if missing:
                self.append_log_threadsafe(
                    "Installation des outils nécessaires ("
                    + ", ".join(missing)
                    + ") depuis GitHub. Cette étape n'a lieu qu'une fois."
                )

            for spec in TOOL_SPECS:
                try:
                    self.update_tool(spec)
                except Exception as e:
                    self.set_tool_status_threadsafe(
                        spec.name,
                        f"{TOOL_LABELS[spec.name]} : échec"
                    )
                    self.append_log_threadsafe(
                        f"Installation de {TOOL_LABELS[spec.name]} impossible : "
                        + describe_error(e)
                    )

            remove_legacy_copies(self.tool_storage_dir)
            remove_old_app_caches()

        except Exception as e:
            self.append_log_threadsafe(
                "Préparation des outils interrompue : " + describe_error(e)
            )

        finally:
            self.root.after(0, self.on_tools_worker_done)

    def on_tools_worker_done(self):
        self.tools_worker_running = False
        self.on_tools_changed()

        if not self.tools_ready_for_download():
            self.tools_retry_btn.pack(side="left", padx=(8, 0))
            self.set_status(
                "Outils manquants. Vérifie ta connexion Internet, "
                "puis clique sur « Réessayer »."
            )

    def update_tool(self, spec):
        label = TOOL_LABELS[spec.name]
        current = self.tool_copies.get(spec.name)
        needs_install = self.tool_needs_install(spec)

        if spec is not YTDLP and current is None and not needs_install:
            # Node already solves the YouTube challenges.
            return

        if spec is not YTDLP and current and current.source != "managed":
            # Deno or ffmpeg embedded in a full build, or found on PATH
            # when the source is run.
            return

        if spec is YTDLP and current and current.source == "local":
            # A full build or the source folder ships yt-dlp: a newer
            # verified managed copy still wins.
            current = replace(
                current,
                version=run_version_command(spec, current.path)
            )
            installed = find_installed_copies(spec, self.tool_storage_dir)
            if installed and installed[0].version_key > current.version_key:
                current = installed[0]
            self.set_tool_copy_threadsafe(spec, current)

        if current and current.source != "path":
            # Copies replaced during an earlier launch. A copy replaced during
            # this session may still be used by a download: it waits until the
            # next launch.
            remove_superseded_copies(
                spec,
                self.tool_storage_dir,
                current.path if current.source == "managed" else None
            )

        if not needs_install and not is_check_due(spec, self.tool_storage_dir):
            return

        try:
            release = fetch_latest_release(spec)

        except Exception as e:
            if current is None:
                raise
            self.set_tool_status_threadsafe(
                spec.name,
                self.tool_label(spec, current) + " (non vérifié)"
            )
            self.append_log_threadsafe(
                f"Vérification des mises à jour de {label} impossible : "
                + describe_error(e)
            )
            return

        if not needs_install and not is_newer_release(release, current):
            record_check(spec, self.tool_storage_dir)
            return

        if not needs_install:
            self.append_log_threadsafe(
                f"Nouvelle version de {label} disponible : {release.version}. "
                "Téléchargement depuis GitHub..."
            )

        try:
            installed_copy = self.install_tool(spec, release)

        except Exception as e:
            if current is None:
                raise
            self.set_tool_status_threadsafe(
                spec.name,
                self.tool_label(spec, current) + " (mise à jour échouée)"
            )
            self.append_log_threadsafe(
                f"Mise à jour de {label} impossible : " + describe_error(e)
            )
            return

        # Recorded only once installed, so a failed update is retried at the
        # next launch instead of 30 days later.
        record_check(spec, self.tool_storage_dir)
        self.set_tool_copy_threadsafe(spec, installed_copy)
        installed_name = (
            label
            if spec is FFMPEG
            else f"{label} {installed_copy.version}"
        )
        self.append_log_threadsafe(
            f"{installed_name} installé (empreinte SHA-256 vérifiée)."
        )

    def install_tool(self, spec, release):
        label = TOOL_LABELS[spec.name]
        last_update = [0.0]

        def progress(done, total):
            now = time.monotonic()
            if now - last_update[0] < PROGRESS_UI_INTERVAL and done != total:
                return
            last_update[0] = now
            if total and done >= total:
                text = f"{label} : vérification..."
            elif total:
                text = f"{label} : {done // MB}/{total // MB} Mo"
            else:
                text = f"{label} : {done // MB} Mo"
            self.set_tool_status_threadsafe(spec.name, text)

        for attempt in range(2):
            try:
                return install_release(
                    spec,
                    release,
                    self.tool_storage_dir,
                    progress=progress
                )
            except ChecksumMismatch:
                # The rolling "latest" ffmpeg build may be replaced while it
                # is downloaded: one new attempt with the new build.
                if attempt or spec is not FFMPEG:
                    raise
                release = fetch_latest_release(spec)

        return None

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

        if selected_format == "BEST_AUDIO":
            return "audio"

        for item in self.current_formats_list:
            if item["format_id"] == selected_format:
                if item["type"] == "audio only":
                    return "audio"

                return "video"

        return "video"

    def cookie_source_from_main_ui(self):
        browser = self.cookies_browser_var.get()
        browser_id = COOKIE_BROWSER_IDS.get(browser)
        return (
            CookieSource.browser_source(browser_id)
            if browser_id
            else CookieSource.none()
        )

    def build_ytdlp_runtime_options(self, cookie_source=None):
        options = []
        js_runtime = find_js_runtime(self.tool_path("deno"))

        if js_runtime:
            runtime_name, runtime_path = js_runtime
            options.extend([
                "--js-runtimes",
                f"{runtime_name}:{runtime_path}",
            ])

        source = cookie_source or CookieSource.none()

        if source.kind is CookieSourceKind.BROWSER and source.browser:
            options.extend([
                "--cookies-from-browser",
                source.browser,
            ])

        elif source.kind is CookieSourceKind.FILE and source.file_path:
            options.extend([
                "--cookies",
                source.file_path,
            ])

        return options

    def open_authentication_assistant_manually(self):
        info = AuthErrorInfo(
            AuthErrorType.UNKNOWN_AUTH_ERROR,
            0,
            "",
            "",
            self.cookie_source_from_main_ui(),
        )
        self.open_authentication_assistant(info)

    def open_authentication_assistant(self, error_info):
        self.last_auth_error_info = error_info
        remembered_path = self.auth_preferences.get_cookie_file_path()
        if remembered_path and not os.path.isfile(remembered_path):
            self.auth_preferences.forget_cookie_file_path()
            self.append_log("Emplacement mémorisé cookies.txt introuvable : préférence supprimée.")
            remembered_path = None
        dialog = AuthenticationAssistant(
            self.root,
            error_info,
            find_firefox(),
            remembered_path,
            {
                "use_firefox": self.use_firefox_authentication,
                "choose_cookie_file": self.choose_cookie_file_authentication,
                "use_remembered_cookie_file": self.use_remembered_cookie_file,
                "forget_remembered_cookie_file": self.forget_remembered_cookie_file,
                "retry_normally": self.retry_without_authentication,
            },
        )
        dialog.grab_set()

    def authentication_source_log_label(self, source):
        if source.kind is CookieSourceKind.BROWSER:
            return f"navigateur {source.browser}"
        if source.kind is CookieSourceKind.FILE:
            return f"fichier cookies.txt : {source.file_path}"
        return "sans cookies"

    def retry_without_authentication(self):
        self.start_authentication_format_flow(CookieSource.none())

    def use_firefox_authentication(self):
        firefox_path = find_firefox()
        if not firefox_path:
            messagebox.showinfo(
                "Firefox non détecté",
                "Firefox n'a pas été détecté sur cet ordinateur. "
                "Tu peux sélectionner un fichier cookies.txt à la place.",
            )
            return
        self.start_authentication_format_flow(CookieSource.browser_source("firefox"))

    def choose_cookie_file_authentication(self, dialog):
        file_path = filedialog.askopenfilename(
            parent=dialog,
            title="Choisir un fichier cookies.txt",
            filetypes=[
                ("Fichier cookies.txt", "*.txt"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not file_path:
            return

        valid, message = validate_netscape_cookie_file(file_path)
        if not valid:
            messagebox.showerror("Fichier cookies.txt", message, parent=dialog)
            return

        source = self.prepare_youtube_cookie_source(file_path, dialog)
        if not source:
            return
        dialog.destroy()
        self.start_authentication_format_flow(source)

    def use_remembered_cookie_file(self):
        file_path = self.auth_preferences.get_cookie_file_path()
        if not file_path:
            return
        valid, message = validate_netscape_cookie_file(file_path)
        if not valid:
            self.auth_preferences.forget_cookie_file_path()
            messagebox.showwarning(
                "Fichier cookies.txt indisponible",
                message + "\n\nSon emplacement mémorisé a été supprimé.",
            )
            return
        source = self.prepare_youtube_cookie_source(file_path)
        if source:
            self.start_authentication_format_flow(source)

    def forget_remembered_cookie_file(self, dialog):
        self.auth_preferences.forget_cookie_file_path()
        self.append_log("Emplacement du fichier cookies.txt oublié.")
        dialog.destroy()
        messagebox.showinfo(
            "Préférence supprimée",
            "L'application a oublié l'emplacement du fichier cookies.txt. "
            "Aucun fichier n'a été copié ni supprimé.",
        )

    def prepare_youtube_cookie_source(self, original_path, parent=None):
        """Use a short-lived YouTube-only copy, never the broad export itself."""
        try:
            temporary_path, cookie_count = create_youtube_only_cookie_copy(original_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror(
                "Filtrage du fichier cookies.txt",
                str(exc),
                parent=parent,
            )
            return None

        self.temporary_cookie_file_paths.add(temporary_path)
        self.pending_cookie_file_for_preference = original_path
        self.append_log(
            "Copie temporaire cookies.txt limitée à YouTube créée "
            f"({cookie_count} entrée(s), contenu non affiché)."
        )
        return CookieSource.file_source(temporary_path)

    def cleanup_temporary_cookie_source(self, cookie_source):
        if (
            not cookie_source
            or cookie_source.kind is not CookieSourceKind.FILE
            or not cookie_source.file_path
            or cookie_source.file_path not in self.temporary_cookie_file_paths
        ):
            return

        if delete_temporary_cookie_file(cookie_source.file_path):
            self.append_log("Copie temporaire cookies.txt supprimée.")
        else:
            self.append_log("Impossible de supprimer immédiatement la copie temporaire cookies.txt.")
        self.temporary_cookie_file_paths.discard(cookie_source.file_path)

    def cleanup_all_temporary_cookie_sources(self):
        for temporary_path in tuple(self.temporary_cookie_file_paths):
            self.cleanup_temporary_cookie_source(CookieSource.file_source(temporary_path))

    def on_application_close(self):
        self.root.after_cancel(self.tools_worker_after_id)
        if self.current_process is not None:
            # A download left running would keep writing into the folder.
            kill_process_tree(self.current_process)
        self.cleanup_all_temporary_cookie_sources()
        self.root.destroy()

    def start_authentication_format_flow(self, cookie_source):
        self.append_log(
            "Assistant d'authentification : essai avec "
            + self.authentication_source_log_label(cookie_source)
        )
        self.choose_format_flow(
            cookie_source=cookie_source,
            preset=self.pending_preset
        )

    def offer_cookie_file_preference(self, cookie_source):
        if (
            cookie_source.kind is not CookieSourceKind.FILE
            or not cookie_source.file_path
            or cookie_source.file_path not in self.temporary_cookie_file_paths
            or not self.pending_cookie_file_for_preference
        ):
            return

        original_path = self.pending_cookie_file_for_preference
        self.pending_cookie_file_for_preference = None

        delete_original = messagebox.askyesno(
            "Protéger le fichier cookies.txt",
            "L'authentification a fonctionné avec une copie temporaire limitée à YouTube. "
            "Cette copie sera supprimée automatiquement après le téléchargement.\n\n"
            "Veux-tu aussi supprimer maintenant le fichier exporté d'origine ?\n\n"
            "Attention : ce fichier peut contenir des cookies d'autres sites. Cette suppression "
            "est définitive dans l'application, mais ne constitue pas un effacement forensic "
            "garanti sur un SSD.",
        )
        if delete_original:
            try:
                os.remove(original_path)
                if self.auth_preferences.get_cookie_file_path() == original_path:
                    self.auth_preferences.forget_cookie_file_path()
                self.append_log("Fichier cookies.txt original supprimé à la demande de l'utilisateur.")
                messagebox.showinfo(
                    "Fichier source supprimé",
                    "Le fichier cookies.txt original a été supprimé. Seule la copie temporaire "
                    "limitée à YouTube reste utilisée pour ce téléchargement, puis sera supprimée.",
                )
            except OSError as exc:
                messagebox.showwarning(
                    "Suppression impossible",
                    f"Le fichier source n'a pas pu être supprimé.\n\n{exc}",
                )
            return

        remember = messagebox.askyesno(
            "cookies.txt fonctionnel",
            "L'authentification avec ce fichier a fonctionné.\n\n"
            "Veux-tu mémoriser uniquement son emplacement pour le réutiliser plus tard ?\n\n"
            "Le fichier n'est pas copié. Il doit rester à cet emplacement. À chaque utilisation, "
            "le logiciel créera uniquement une copie temporaire limitée à YouTube.",
        )
        if not remember:
            return
        try:
            self.auth_preferences.remember_cookie_file_path(original_path)
            self.append_log("Emplacement du fichier cookies.txt mémorisé (sans copie du fichier).")
        except OSError as exc:
            messagebox.showwarning(
                "Préférence non enregistrée",
                f"Le téléchargement peut continuer, mais l'emplacement n'a pas pu être mémorisé.\n\n{exc}",
            )

    def add_history_entry(self, file_path, conversion_text):
        folder = (
            os.path.dirname(file_path)
            if file_path
            else self.folder_var.get().strip()
        )

        item = {
            "time": time.strftime("%H:%M:%S"),
            "file": file_path or "(fichier non détecté)",
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

            self.log_box.insert("end", text + "\n", ("detail",))
            self.progress_log_line_exists = True

        else:
            start = self.progress_log_start_index
            end = self.log_box.index(f"{start} lineend +1c")

            self.log_box.delete(start, end)
            self.log_box.insert(start, text + "\n", ("detail",))

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

    def set_status(self, text, color="#333333"):
        self.status_label.config(text=text, fg=color)
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
        lower_line = line.lower()

        for pattern in YTDLP_OUTPUT_RES:
            match = pattern.match(stripped)
            if match:
                self.current_download_outputs.append(match.group(1))

        auth_info = AuthErrorDetector.detect(
            1,
            stderr_text=line,
            cookie_source=self.selected_cookie_source,
        )
        if auth_info:
            self.youtube_auth_error_seen = True
            return

        if (
            getattr(self, "youtube_auth_error_seen", False)
            and (lower_line.startswith("error:") or "cookies" in lower_line)
        ):
            return

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

        if "merging formats into" in lower_line:
            self.set_status_threadsafe("Fusion en cours...")
            self.set_progress_threadsafe(
                99.0,
                "fusion",
                "presque fini"
            )

            self.append_log_threadsafe(line, detail=True)

            self.clear_progress_log_line_marker()
            self.last_log_ui_update = now
            return

        if stripped:
            if (
                now - self.last_log_ui_update
            ) >= LOG_UI_INTERVAL:

                self.append_log_threadsafe(line, detail=True)

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
            folder = os.path.normpath(folder)
            self.folder_var.set(folder)
            self.settings.set("download_folder", folder)

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
        self.current_process = process

        collected_lines = []

        try:
            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = raw_line.rstrip("\n").rstrip("\r")

                    collected_lines.append(line)
                    self.handle_live_output_line(line)

            returncode = process.wait()

        finally:
            self.current_process = None

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
            f"Fichier renommé : {target_path}"
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

        returncode = self.run_ffmpeg(cmd, output_file)

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
                f"Format vidéo non supporté : {output_format}"
            )

        cmd = [
            ffmpeg_path,
            "-y",
            "-i", input_file,
        ] + codec_args + [output_file]

        returncode = self.run_ffmpeg(cmd, output_file)

        if returncode != 0:
            raise RuntimeError(
                f"Échec de la conversion {output_format}"
            )

        return output_file

    def is_audio_only_format(
        self,
        selected_format,
        formats_list
    ):
        if selected_format == "BEST_AUDIO":
            return True

        for f in formats_list:
            if f["format_id"] == selected_format:
                return f["type"] == "audio only"

        return False

    def choose_format_flow(self, cookie_source=None, preset=None):
        url = self.url_var.get().strip()
        playlist_mode = self.playlist_mode_var.get()
        source = cookie_source or self.cookie_source_from_main_ui()

        # Starting a different selection makes any previous temporary source
        # unnecessary. It is never reused outside its current auth attempt.
        if source != self.selected_cookie_source:
            self.cleanup_temporary_cookie_source(self.selected_cookie_source)

        if not url:
            messagebox.showerror(
                "Erreur",
                "Colle l'URL de la vidéo."
            )
            return

        if not re.match(r"https?://", url, re.IGNORECASE):
            messagebox.showerror(
                "Erreur",
                "L'URL doit commencer par http:// ou https://."
            )
            return

        self.pending_preset = preset
        self.disable_action_buttons()
        self.selected_download_format = None
        self.selected_download_title = None
        self.selected_download_url = None
        self.selected_playlist_mode = playlist_mode
        self.selected_cookie_source = source
        self.selected_cookies_browser = source.browser or "Aucun"
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
            args=(url, playlist_mode, source),
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

        self.disable_action_buttons()
        self.settings.set("download_folder", folder)
        self.cancel_requested = False
        self.current_download_outputs = []
        self.cancel_btn.config(state="normal")

        self.reset_progress()

        self.set_status(
            "Téléchargement en cours..."
        )

        threading.Thread(
            target=self.download_worker,
            args=(
                self.selected_download_url,
                folder,
                self.selected_download_format,
                self.selected_playlist_mode,
                self.selected_download_title,
                self.selected_cookie_source,
            ),
            daemon=True
        ).start()

    def fetch_formats_worker(self, url, playlist_mode, cookie_source):
        try:
            downloader = find_downloader(self.tool_path("yt-dlp"))

            cmd = downloader + [
                "-J",
                "--yes-playlist" if playlist_mode else "--no-playlist",
            ]
            cmd.extend(
                self.build_ytdlp_runtime_options(cookie_source)
            )
            # "--" ends the options: the URL is never read as one.
            cmd.extend(["--", url])

            returncode, stdout_text, stderr_text = (
                self.run_command_json(cmd)
            )

            if returncode != 0:
                err = (stderr_text + "\n" + stdout_text).strip() or "Erreur inconnue"

                self.root.after(
                    0,
                    lambda: self.on_fetch_error(err, cookie_source, returncode)
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
                    playlist_mode,
                    cookie_source,
                )
            )

        except Exception as e:
            # Python clears `e` at the end of the except block, before the
            # Tk callback runs: the message must be captured now.
            error_text = str(e)
            self.root.after(
                0,
                lambda: self.on_fetch_error(error_text, cookie_source, -1)
            )

    def show_format_dialog(
        self,
        url,
        formats_list,
        title,
        playlist_mode,
        cookie_source,
    ):
        self.current_formats_list = formats_list

        self.enable_choose_format_button()

        self.set_status("Choisis un format.")

        self.append_log(
            f"{len(formats_list)} options détectées."
        )

        self.append_log(
            f"Titre détecté : {title}"
        )

        self.offer_cookie_file_preference(cookie_source)

        ffmpeg_path = find_ffmpeg(self.tool_path("ffmpeg"))

        ffmpeg_msg = (
            f"ffmpeg détecté : {ffmpeg_path}"
            if ffmpeg_path
            else "ffmpeg non détecté."
        )

        preset = PRESETS.get(self.pending_preset)

        if preset:
            # One-click shortcut: no format list to read.
            selected = preset["format"]
            self.audio_conversion_var.set(preset["audio_conversion"])
            self.video_conversion_var.set(preset["video_conversion"])
            self.append_log(f"Raccourci : {preset['label']}.")

        else:
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
            self.cleanup_temporary_cookie_source(cookie_source)
            return

        self.append_log(
            f"Format choisi : {selected}"
        )

        self.selected_download_format = selected
        self.selected_download_title = title
        self.selected_download_url = url
        self.selected_playlist_mode = playlist_mode
        self.selected_cookie_source = cookie_source

        selected_kind = self.get_selected_format_kind(selected)
        self.set_conversion_controls(selected_kind)

        if preset:
            self.start_download_flow()
            return

        self.enable_start_button()

        self.set_status(
            "Format choisi. Vérifie le dossier, puis clique sur « Lancer le téléchargement »."
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
        detected_title,
        cookie_source
    ):
        try:
            downloader = find_downloader(self.tool_path("yt-dlp"))
            ffmpeg_path = find_ffmpeg(self.tool_path("ffmpeg"))

            format_string = {
                "BEST_AUTO": "bv*+ba/b",
                "BEST_AUDIO": "ba/b",
            }.get(selected_format, selected_format)

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
            ]

            if ffmpeg_path:
                cmd.extend([
                    "--ffmpeg-location",
                    ffmpeg_path
                ])

            cmd.extend(
                self.build_ytdlp_runtime_options(cookie_source)
            )

            if selected_format == "BEST_AUTO":
                cmd.extend([
                    "--merge-output-format",
                    "mp4"
                ])

            cmd.extend(["--", url])

            self.set_status_threadsafe(
                "Téléchargement en cours..."
            )

            self.youtube_auth_error_seen = False

            returncode, output_text = (
                self.run_command_live(cmd)
            )

            if self.cancel_requested:
                self.finish_cancelled_download()
                return

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
                                    "Fichier source supprimé : "
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
                        f"Conversion vidéo {selected_video_conversion}..."
                    )

                    self.append_log_threadsafe(
                        f"Conversion vidéo vers "
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
                            f"Conversion terminée : "
                            f"{converted_file}"
                        )

                        if self.delete_video_source_var.get():
                            try:
                                os.remove(main_file)

                                self.append_log_threadsafe(
                                    f"Fichier source supprimé : "
                                    f"{main_file}"
                                )

                            except Exception:
                                pass

                        main_file = converted_file

                    except Exception as e:
                        self.append_log_threadsafe(
                            f"Erreur de conversion vidéo : {e}"
                        )

                elif not ffmpeg_path:
                    self.append_log_threadsafe(
                        "Conversion vidéo ignorée : ffmpeg non détecté."
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
                            f"Conversion terminée : "
                            f"{converted_file}"
                        )

                        if self.delete_video_source_var.get():
                            try:
                                os.remove(source_file)

                                self.append_log_threadsafe(
                                    f"Fichier source supprimé : "
                                    f"{source_file}"
                                )

                            except Exception:
                                pass

                    except Exception as e:
                        self.append_log_threadsafe(
                            f"Erreur de conversion vidéo : {e}"
                        )

            if self.cancel_requested:
                # « Annuler » was used during a conversion.
                self.finish_cancelled_download()
                return

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
                    lambda: self.on_download_error(err, cookie_source, returncode)
                )

        except Exception as e:
            error_text = str(e)
            self.root.after(
                0,
                lambda: self.on_download_error(error_text, cookie_source, -1)
            )

    def handle_authentication_error(self, error_text, cookie_source, returncode):
        info = AuthErrorDetector.detect(
            returncode,
            stderr_text=error_text,
            cookie_source=cookie_source,
        )
        if not info:
            return False

        self.set_status("Authentification nécessaire.")
        self.append_log(
            "Authentification nécessaire : "
            f"{info.error_type.value} ({self.authentication_source_log_label(cookie_source)})."
        )
        self.open_authentication_assistant(info)
        return True

    def on_fetch_error(self, error_text, cookie_source=None, returncode=-1):
        self.enable_choose_format_button()
        self.start_btn.config(state="disabled")

        source = cookie_source or self.selected_cookie_source
        self.cleanup_temporary_cookie_source(source)
        if self.handle_authentication_error(error_text, source, returncode):
            return

        self.set_status(
            "Échec de lecture des formats."
        )

        self.append_log(sanitize_technical_text(error_text))

        messagebox.showerror(
            "Erreur",
            f"Impossible de récupérer les formats.\n\n"
                f"{sanitize_technical_text(error_text)}"
        )

    def on_download_error(self, error_text, cookie_source=None, returncode=-1):
        self.cancel_btn.config(state="disabled")
        self.enable_start_button()
        self.enable_choose_format_button()

        source = cookie_source or self.selected_cookie_source
        self.cleanup_temporary_cookie_source(source)
        if self.handle_authentication_error(error_text, source, returncode):
            return

        self.set_status(
            "Échec du téléchargement."
        )

        self.append_log(sanitize_technical_text(error_text))

        messagebox.showerror(
            "Erreur",
            f"Le téléchargement a échoué.\n\n"
                f"{sanitize_technical_text(error_text)}"
        )

    def on_success(self, folder, main_file):
        self.cleanup_temporary_cookie_source(self.selected_cookie_source)
        self.cancel_btn.config(state="disabled")
        self.enable_start_button()
        self.enable_choose_format_button()

        self.clear_progress_log_line_marker()

        if main_file:
            self.set_status(
                f"Téléchargement terminé : {os.path.basename(main_file)}",
                SUCCESS_COLOR
            )
            self.append_log(f"Téléchargement terminé : {main_file}")

        else:
            self.set_status("Téléchargement terminé.", SUCCESS_COLOR)
            self.append_log(
                "Téléchargement terminé. Impossible de détecter "
                "automatiquement le fichier principal."
            )

        self.show_result(main_file, folder)

        if (
            main_file
            and os.path.isfile(main_file)
            and self.create_sha256_var.get()
        ):
            self.set_status(
                "Calcul du SHA-256 en cours..."
            )

            self.append_log(
                "Création du fichier SHA-256 demandée par l'option principale."
            )

            self.disable_action_buttons()

            threading.Thread(
                target=self.hash_worker,
                args=(main_file, folder),
                daemon=True
            ).start()

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
            error_text = str(e)
            self.root.after(
                0,
                lambda: self.on_hash_error(
                    folder,
                    error_text
                )
            )

    def on_hash_success(
        self,
        folder,
        main_file,
        digest,
        hash_txt_path
    ):
        self.enable_start_button()
        self.enable_choose_format_button()

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

        self.set_status(
            "Téléchargement terminé, SHA-256 enregistré : "
            f"{os.path.basename(hash_txt_path)}",
            SUCCESS_COLOR
        )
        self.show_result(main_file, folder)

    def on_hash_error(self, folder, error_text):
        self.enable_start_button()
        self.enable_choose_format_button()

        self.set_status(
            "Erreur pendant le calcul du SHA-256."
        )

        self.append_log(error_text)

        messagebox.showerror(
            "Erreur SHA-256",
            f"Impossible de calculer "
            f"le SHA-256.\n\n{error_text}"
        )

    def start_preset(self, kind):
        folder = self.folder_var.get().strip()

        if not os.path.isdir(folder):
            messagebox.showerror(
                "Erreur",
                "Choisis un dossier de sauvegarde qui existe."
            )
            return

        self.choose_format_flow(preset=kind)

    def on_url_return(self, event):
        if str(self.video_preset_btn["state"]) == "normal":
            self.start_preset("video")
        return "break"

    def auto_paste_clipboard(self, event=None):
        # A link copied in the browser is ready when the window comes back.
        if self.url_var.get().strip():
            return

        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            return

        if text == self.last_auto_pasted or not CLIPBOARD_URL_RE.fullmatch(text):
            return

        self.last_auto_pasted = text
        self.url_var.set(text)
        self.append_log("Lien collé depuis le presse-papiers.")

    def initial_download_folder(self):
        saved = self.settings.get("download_folder")
        if isinstance(saved, str) and os.path.isdir(saved):
            return saved
        return find_windows_downloads_folder() or ""

    def run_ffmpeg(self, cmd, output_file):
        # Tracked like the download: « Annuler » also stops a conversion and
        # removes its unfinished file.
        self.current_download_outputs.append(output_file)
        process = subprocess.Popen(
            cmd,
            **get_live_process_kwargs()
        )
        self.current_process = process

        try:
            if process.stdout is not None:
                for raw_line in process.stdout:
                    line = raw_line.rstrip("\n").rstrip("\r")

                    if line.strip():
                        self.append_log_threadsafe(
                            "[ffmpeg] " + line,
                            detail=True
                        )

            return process.wait()

        finally:
            self.current_process = None

    def cancel_download(self):
        self.cancel_requested = True
        self.cancel_btn.config(state="disabled")
        self.set_status("Annulation en cours...")

        process = self.current_process
        if process is not None:
            kill_process_tree(process)

    def finish_cancelled_download(self):
        # Worker thread: only files written by this download are removed.
        self.remove_partial_outputs()
        self.root.after(0, self.on_download_cancelled)

    def remove_partial_outputs(self):
        for path in dict.fromkeys(self.current_download_outputs):
            for candidate in (path, path + ".part", path + ".ytdl"):
                if not os.path.isfile(candidate):
                    continue
                try:
                    os.remove(candidate)
                except OSError:
                    continue
                self.append_log_threadsafe(
                    f"Fichier incomplet supprimé : {candidate}",
                    detail=True
                )

    def on_download_cancelled(self):
        self.cleanup_temporary_cookie_source(self.selected_cookie_source)
        self.cancel_btn.config(state="disabled")
        self.enable_start_button()
        self.enable_choose_format_button()
        self.reset_progress()
        self.clear_progress_log_line_marker()
        self.set_status("Téléchargement annulé.", CANCEL_COLOR)
        self.append_log("Téléchargement annulé.")

    def show_result(self, main_file, folder):
        self.last_result_file = (
            main_file
            if main_file and os.path.isfile(main_file)
            else None
        )
        self.last_result_folder = folder
        self.open_result_file_btn.config(
            state="normal" if self.last_result_file else "disabled"
        )
        self.result_frame.pack(side="right", before=self.status_label)

    def hide_result(self):
        self.result_frame.pack_forget()

    def open_result_file(self):
        if self.last_result_file:
            open_path(self.last_result_file)

    def open_result_folder(self):
        if self.last_result_folder:
            open_path(self.last_result_folder)

    def mainloop(self):
        self.root.mainloop()


def main():
    root = tk.Tk()
    app = App(root)
    app.mainloop()


if __name__ == "__main__":
    main()
