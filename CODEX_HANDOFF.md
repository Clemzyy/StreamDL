# CODEX HANDOFF: StreamDL

META:
  language: fr
  project: Stream Video Downloader / StreamDL
  owner: Clemzy
  github: https://github.com/Clemzyy/StreamDL
  github_visibility: private
  git_identity: "Clemzy <troisquarks@proton.me>"
  workspace: "C:\Users\Utilisateur\OneDrive\Bureau\Applications Python\Téléchargeur vidéo"
  current_source: telechargeur_youtube_v1.87.pyw
  current_app_label: "Téléchargeur Vidéo v1.87 by Clemzy (APP_VERSION follows the source number)"
  next_source_version: "1.88"
  executable_policy: "Ne pas compiler de nouvel exe sauf demande explicite. Build: py -3.13 build_exe.py [--full] [--pyinstaller] -> dist\\StreamDL.exe (Nuitka + MSVC Build Tools)"

USER_PREFERENCES:
  - Répondre en français, ton direct et collaboratif.
  - Modifier réellement les fichiers quand la demande est claire.
  - Incrémenter le numéro source de 0.01 à chaque modification: 1.75 -> 1.76.
  - Ne pas écraser les modifications utilisateur non liées.
  - Conserver les icônes sociales fournies dont les noms commencent par social_*.png.
  - Ne pas intégrer de cookies YouTube partagés dans le logiciel ou l'exécutable.

REPO_STATE:
  last_pushed_commit: "7d8ca90 Handle YouTube authentication errors"
  branch: main
  remote: https://github.com/Clemzyy/StreamDL.git
  source_history:
    - telechargeur_youtube_v1.72b.pyw: ancienne base
    - telechargeur_youtube_v1.74.pyw: version précédente, renommée en 1.75
    - telechargeur_youtube_v1.75.pyw: version précédente
    - telechargeur_youtube_v1.76.pyw: assistant d'authentification et gestion cookies.txt
    - telechargeur_youtube_v1.77.pyw: guide d'export manuel Chrome cookies.txt
    - telechargeur_youtube_v1.78.pyw: copie temporaire cookies YouTube filtrée et suppression source optionnelle
    - telechargeur_youtube_v1.79.pyw: Deno local pour les défis JavaScript YouTube
    - telechargeur_youtube_v1.80.pyw: option SHA-256 et aide export Chrome guidée
    - telechargeur_youtube_v1.81.pyw: repli automatique vers Téléchargements Windows
    - telechargeur_youtube_v1.82.pyw: mise à jour automatique de yt-dlp, icône GitHub, build portable
    - telechargeur_youtube_v1.83.pyw: messages d'erreur des workers qui ne bloquent plus l'interface
    - telechargeur_youtube_v1.84.pyw: exe léger Nuitka, outils téléchargés au premier lancement
    - telechargeur_youtube_v1.85.pyw: ergonomie (raccourcis MP4/MP3, Annuler, dossier retenu, journal)
    - telechargeur_youtube_v1.86.pyw: présentation Windows 11 (sv-ttk clair/sombre, blocs, aperçu)
    - telechargeur_youtube_v1.87.pyw: thème imposé par le nom de l'exe (copies de test)
  files_expected:
    - telechargeur_youtube_v1.87.pyw
    - auth_support.py
    - test_auth_support.py
    - tools_manager.py
    - test_tools_manager.py
    - test_app_tools_ui.py
    - test_build_exe.py
    - test_app_ergonomics.py
    - test_app_presentation.py
    - social_github_dark.png (light GitHub mark used on the dark theme)
    - build_exe.py
    - social_github.png
    - yt-dlp.exe
    - deno.exe
    - DENO_LICENSE.md
    - social_paypal.png
    - social_pc32.png
    - social_tiktok.png
    - social_youtube.png
    - requirements.txt
    - LICENSE
    - .gitignore
  note: "ffmpeg.exe peut être présent comme fichier local non versionné; vérifier git status avant toute action."

FUNCTIONAL_HISTORY:
  - Correction du téléchargement accidentel de playlists: playlist uniquement si option explicite.
  - Ajout du choix de format avant lancement.
  - Séparation format principal / conversion audio / conversion vidéo.
  - Suppression de l'original après conversion, cases cochées par défaut.
  - Formats audio: MP3, WAV, AAC, FLAC, M4A, OPUS selon la source/UI.
  - Formats vidéo: MP4, AVI, MKV, WEBM.
  - Nettoyage des noms: utiliser le titre détecté, sans date, identifiant ni extension yt-dlp parasite.
  - Bouton Choisir le format compact et interface responsive.
  - Fenêtre agrandie pour afficher le journal et quatre lignes vides.
  - Barre supérieure: titre uniquement dans la barre de fenêtre, icônes sociales à côté.
  - Liens sociaux:
      TikTok: https://www.tiktok.com/@__clemzy__
      YouTube: https://www.youtube.com/@Clemzy
      PC32: https://www.pc32.fr/
      PayPal: https://www.paypal.com/donate/?hosted_button_id=NKCR6KK739WGS

CURRENT_IMPLEMENTATION:
  yt_dlp:
    executable: yt-dlp.exe
    verified_version: 2026.10.26
    location: beside the source for development; not bundled in the light exe
    auto_update: "tools_manager.py; verified copies in %LOCALAPPDATA%\\StreamDL\\tools\\<tool>\\<version>"
  javascript_runtime:
    implementation: find_js_runtime()
    preferred: deno.exe
    local_environment: "Deno beside the source for development; managed copy for the light exe"
    command_option: "--js-runtimes deno:<path>"
  cookies_ui:
    values: [Aucun, Chrome, Edge, Firefox, Brave, Opera]
    mapping:
      Chrome: chrome
      Edge: edge
      Firefox: firefox
      Brave: brave
      Opera: opera
    current_behavior: "--cookies-from-browser <browser>"
  ffmpeg:
    detection: "packaged exe: embedded (--full) then verified managed copy; source run: source folder, managed copy, then PATH (.exe only)"
    managed_source: "github.com/yt-dlp/FFmpeg-Builds, ffmpeg-master-latest-win64-gpl-shared.zip (ffmpeg.exe + DLLs)"
    required_for: "m3u8/HLS, merge separate audio-video streams, conversions"
    missing_was_observed: "A prior download failed because ffmpeg.exe was absent."
    note: "A local ffmpeg.exe later appeared untracked; do not assume it was created by Codex."

KNOWN_COOKIE_FINDINGS:
  - Chrome/Edge/Brave Chromium cookie databases can fail with copy/DPAPI errors on Windows.
  - Edge can still produce the generic message 'Could not copy Chrome cookie database'.
  - Opera is also Chromium-based; it is not fundamentally immune.
  - Firefox worked in the user's test.
  - No robust way exists to embed a shared cookie account securely in a distributed exe.
  - OAuth Google login is not equivalent to browser cookies needed by yt-dlp.
  - Preferred future UX: per-user local cookies.txt import, never committed or bundled.
  - Cookies are credentials; never request or receive the user's cookie contents.

VERSION_1_75_CHANGE:
  - Added is_youtube_authentication_error().
  - Added user-friendly warning when cookies selection is Aucun and YouTube requires login.
  - Raw authentication error lines are suppressed from the live journal after detection.
  - Message recommends Firefox or Opera and explains age/anti-bot/authenticated restrictions.
  - Non-authentication errors remain detailed.
  - Source was renamed from v1.74 to v1.75 and pushed in commit 7d8ca90.

VERSION_1_76_CHANGE:
  - Added auth_support.py to centralize yt-dlp authentication error detection,
    Firefox discovery, Netscape cookies.txt validation, and safe technical output.
  - Added a compact Tkinter authentication assistant, available manually and after
    detected authentication, cookie extraction, or cookie decryption failures.
  - Firefox is the recommended automatic method. Chromium remains available in
    the existing selector but is not promoted by the assistant.
  - Added optional storage of only a cookies.txt path in
    %LOCALAPPDATA%\StreamDL\authentication.json after a successful authentication.
    Cookie contents are never copied, logged, committed, or bundled.
  - Added test_auth_support.py. Run: py -3.13 -m unittest -v test_auth_support.py
  - Added cookies*.txt to .gitignore.

VERSION_1_77_CHANGE:
  - Added a manual last-resort Chrome cookies.txt export path in the authentication assistant.
  - The user must explicitly confirm before the application opens the Chrome Web Store page for
    "Get cookies.txt LOCALLY", the extension cited by the yt-dlp FAQ.
  - The dialog warns that cookies.txt is sensitive, must not be used on a public/shared/professional
    computer, and that Firefox remains the recommended automatic method.
  - No browser cookie is exported, read, copied, logged, or stored by the application; the user
    returns to the existing file picker after exporting a Netscape-format file manually.

VERSION_1_78_CHANGE:
  - A user-selected cookies.txt is now read into a temporary file containing only youtube.com
    and its subdomains; the original export is never modified.
  - The temporary YouTube-only file is removed after success, failure, cancelled format choice,
    a new format selection, or application closure.
  - After successful authentication, the user can explicitly delete the original exported file.
    This is a normal deletion, not a forensic overwrite guarantee on SSDs.
  - The remembered preference continues to store only the original path; each reuse creates a new
    temporary filtered copy.

VERSION_1_79_CHANGE:
  - Bundled official Deno 2.9.5 Windows x64 beside yt-dlp.exe, after SHA-256 verification against
    the checksum published with the official Deno release.
  - find_js_runtime() now prioritizes bundled Deno, then Deno on PATH, then legacy Node support.
  - This enables yt-dlp's current YouTube JavaScript challenge solving without a separate Deno
    installation or PATH modification. Deno MIT license is included in DENO_LICENSE.md.

VERSION_1_80_CHANGE:
  - Replaced the post-download SHA-256 question with an unchecked main-window checkbox that creates
    the sidecar .sha256.txt file automatically when selected.
  - The Chrome export assistant now explicitly instructs users to click "Export All Cookies" in the
    Get cookies.txt LOCALLY extension, then select the downloaded file.
  - Added a button that reads only Chrome's configured download-directory preference and opens that
    folder. It never reads cookies or browser history.

VERSION_1_81_CHANGE:
  - When Chrome has no explicit download.default_directory setting, the Chrome-download button now
    opens Windows' Downloads known folder instead, including a folder redirected by OneDrive.

VERSION_1_82_CHANGE:
  - Added ytdlp_updater.py. At each launch a background thread compares the bundled yt-dlp.exe
    and managed copies with the latest stable release of github.com/yt-dlp/yt-dlp (API, with a
    fallback to the releases/latest redirect when the anonymous API quota is exhausted).
  - A newer yt-dlp.exe is downloaded into its own version folder, checked against the release's
    SHA2-256SUMS, then checked with --version before use. Running downloads keep their copy;
    superseded copies are removed best-effort. No UI blocking: the current copy works meanwhile.
  - Status shown at the top-left of the window; details in the journal.
  - Added the project GitHub icon (social_github.png, Octicons mark) at the far top right.
  - Added build_exe.py: refreshes the project yt-dlp.exe to the latest verified release, then
    builds a single-file windowed dist\StreamDL.exe bundling yt-dlp, ffmpeg, Deno, icons, licenses.
  - Tests: py -3.13 -m unittest -v test_ytdlp_updater.py test_auth_support.py

VERSION_1_83_CHANGE:
  - Fixed a bug present since at least v1.81: fetch_formats_worker, download_worker and
    hash_worker passed `lambda: ...str(e)` to root.after(). Python clears `e` when the except
    block ends, so the callback raised NameError: no error dialog, buttons left disabled.
    The message is now captured in error_text before scheduling the callback.
  - ruff and mypy are clean on the project Python files.

VERSION_1_84_CHANGE:
  - ytdlp_updater.py became tools_manager.py: one engine (ToolSpec) for yt-dlp, Deno and ffmpeg.
    Official GitHub releases only (HTTPS, redirects restricted to github.com/*.githubusercontent.com),
    SHA-256 checked before any execution (SHA2-256SUMS, Deno PowerShell .sha256sum, ffmpeg
    checksums.sha256), safe zip extraction (whitelisted members, flattened names, no symlink,
    size caps), version check after install, installed.json marker written last, disk-space check,
    retries on files locked by antivirus. Storage: %LOCALAPPDATA%\StreamDL\tools\<tool>\<version>.
    The 1.82/1.83 folder %LOCALAPPDATA%\StreamDL\yt-dlp is removed (yt-dlp downloaded again once).
  - App: tools resolved instantly at startup without running them; a worker started 300 ms after
    the window installs missing tools with progress in the top-left label, then checks updates
    (yt-dlp each launch, Deno and ffmpeg every 30 days via tools\state.json). « Choisir le format »
    needs yt-dlp + a JS runtime, « Lancer » also needs ffmpeg; « Réessayer » appears when offline.
  - Packaging benchmark (window visible, this PC): PyInstaller onefile with tools 115 MB ~4.0 s;
    PyInstaller onefile light 12.2 MB ~2.0-2.6 s; PyInstaller onedir light 12.3 MB zipped ~0.3 s;
    Nuitka onefile cached light ~0.52 s (median of 5, final exe 8.7 MB). Nuitka chosen: unpacked once into
    %LOCALAPPDATA%\StreamDL\app\<build id>; older build caches are removed by the app.
    Nuitka resolves {CACHE_DIR} through the Windows known folder: overriding the LOCALAPPDATA
    variable in tests moves the tools, not this cache.
  - QuickJS-ng 0.17 benchmarked against Deno: same formats 9/9 but median 12.5 s vs 5.4 s; Deno kept.
  - build_exe.py: Nuitka by default (needs nuitka[onefile] + MSVC Build Tools; Dependency Walker is
    downloaded once by Nuitka), --full embeds the tools, --pyinstaller fallback.
  - Security (review): a packaged exe never runs a tool dropped beside StreamDL.exe or found on PATH;
    NoDefaultCurrentDirectoryInExePath=1; PATH lookups accept absolute .exe only; the video URL must
    start with http(s):// and is passed after "--"; ffmpeg zip whitelist = ffmpeg/ffprobe.exe and
    av*/sw*/postproc DLLs; GitHub API asset digest cross-checked with the published checksum file.
  - Installs run in a private %LOCALAPPDATA%\StreamDL\tools\<tool>\.installing-* folder renamed into
    place (two windows never collide); superseded copies are removed at the next launch only, since
    a running download may still use them; a failed update is retried at the next launch.
  - Tests: py -3.13 -m unittest test_tools_manager test_app_tools_ui test_auth_support test_build_exe

VERSION_1_85_CHANGE:
  - Texts: accents fixed, informal address (tu) everywhere including the authentication assistant;
    APP_VERSION constant shown in the title (a test checks it matches the source file name).
  - Cookies row: « Aide à l'authentification » was clipped at 650 px; the hint moved to its own line.
  - One-click shortcuts « Vidéo MP4 » (BEST_AUTO) and « Audio MP3 » (BEST_AUDIO = ba/b + MP3
    conversion): the format list is read silently, no dialog; « Format avancé... » keeps the old
    flow. Enter in the URL field starts « Vidéo MP4 »; a link in the clipboard is pasted once when
    the window is activated and the URL field is empty.
  - Download folder prefilled with the Windows Downloads folder
    (auth_support.find_windows_downloads_folder), remembered in
    %LOCALAPPDATA%\StreamDL\settings.json.
  - « Annuler »: taskkill /T on the yt-dlp (or ffmpeg) process tree, then removal of only the files
    yt-dlp reported ([download] Destination, [Merger]) and the conversion output. Closing the
    window also stops a running download.
  - End of download: no dialog and no Explorer window; green status line with « Ouvrir le fichier »
    and « Ouvrir le dossier ». The SHA-256 result is also shown without a dialog (errors keep one).
  - Journal: raw yt-dlp/ffmpeg lines tagged "detail" (Tk elide), shown with « Afficher les détails
    techniques ». History reduced to 3 rows and spacing tightened so the journal keeps ~4 lines.
  - Tests: test_app_ergonomics.py (18 tests, hidden window; the cancel test runs a fake yt-dlp).

VERSION_1_86_CHANGE:
  - Windows 11 look with sv-ttk 2.6 (MIT, 82 KB, added to requirements.txt): light or dark like
    the Windows setting (HKCU ...\Themes\Personalize AppsUseLightTheme), dark title bar through
    DwmSetWindowAttribute(20/19). Without sv-ttk the app starts with the classic light look.
  - apply_theme() calls sv-ttk's configure_colors itself: its <<ThemeChanged>> binding never fires
    for a window not shown yet, which left grey backgrounds (covered by a test).
  - PALETTES (light/dark Fluent colors) for what the theme does not draw: muted text, success,
    warning, journal colors; status colors and the dialogs' explicit colors use them.
  - Main window rebuilt with ttk widgets in three blocks: Vidéo (link, preview, playlist, cookies),
    Format (accent shortcuts, « Format avancé... », conversion options folded by default and
    unfolded after an advanced choice), Destination (folder, SHA-256).
  - Preview « titre · chaîne · durée » (or « Playlist : titre · N vidéos ») from the -J reading.
  - Journal and Historique are tabs at the bottom (tab text counts downloads), so the journal keeps
    about 6 lines at 650x780. App icon set as default icon for every dialog.
  - build_exe.py: --include-package-data=sv_ttk (Nuitka), --collect-data sv_ttk (PyInstaller).
  - Tests: test_app_presentation.py (17 tests).

VERSION_1_87_CHANGE:
  - Theme forced by the exe name: StreamDL-clair.exe (light), StreamDL-sombre.exe (dark),
    StreamDL-natif.exe (classic Windows look, no sv-ttk); any other name follows Windows.
    The copies are identical files, so they share one Nuitka cache folder (no re-unpacking
    when switching). get_launcher_path() gives the started exe; get_app_dir() uses it.
  - To make the test copies: build once, then copy dist\StreamDL.exe to the three names.

RECENT_TEST_VIDEO:
  url: https://www.youtube.com/watch?v=55q-1jpgnGc
  title: "SpaceX Falcon 9 Starlink Launch (Vandenberg) | Falcon 9 Booster Landing"
  observed_formats: "Only m3u8 formats 91-96; format 96 is 1080p around 5.4 Mbit/s."
  implication: "Slow download can be normal for this HLS source; ffmpeg is required."

NEXT_RECOMMENDED_FEATURE:
  version: 1.76
  feature: "Import local cookies.txt"
  expected_ui: "Button/file picker near Cookies YouTube; option Aucun remains default."
  yt_dlp_argument: "--cookies <selected_path>"
  security:
    - Do not copy or upload the file.
    - Do not add cookies*.txt to Git.
    - Add cookies*.txt to .gitignore if implementing the feature.
    - Keep raw cookie contents out of journal and error dialogs.
  error_handling: "If no cookie file is selected, preserve current browser-cookie behavior."

WORKFLOW:
  - Inspect git status before edits.
  - Use apply_patch for source edits.
  - Rename source to next version for every modification.
  - Run py -3.13 -m py_compile on the new source.
  - Do not build an exe unless explicitly requested.
  - Commit intentional source changes and push to origin/main when appropriate.
  - Do not commit ffmpeg.exe or any cookies file without explicit instruction.
