# CODEX HANDOFF: StreamDL

META:
  language: fr
  project: Stream Video Downloader / StreamDL
  owner: Clemzy
  github: https://github.com/Clemzyy/StreamDL
  github_visibility: public
  git_identity: "Clemzy <troisquarks@proton.me>"
  workspace: "C:\Users\user\OneDrive\Bureau\Applications Python\Téléchargeur vidéo"
  current_source: telechargeur_youtube_v1.96.pyw
  current_app_label: "StreamDL v1.96 (window title; APP_VERSION follows the source number)"
  next_source_version: "1.97"
  executable_policy: "Ne pas compiler de nouvel exe sauf demande explicite. Build: py -3.13 build_exe.py [--full] [--pyinstaller] -> dist\\StreamDL.exe (Nuitka + MSVC Build Tools)"

USER_PREFERENCES:
  - Répondre en français, ton direct et collaboratif.
  - Modifier réellement les fichiers quand la demande est claire.
  - Incrémenter le numéro source de 0.01 à chaque modification: 1.75 -> 1.76.
  - Ne pas écraser les modifications utilisateur non liées.
  - Conserver les icônes sociales fournies dont les noms commencent par social_*.png.
  - Ne pas intégrer de cookies YouTube partagés dans le logiciel ou l'exécutable.
  - Commits avec l'identité Git du propriétaire uniquement, sans Co-authored-by ni attribution à une IA.

REPO_STATE:
  verified_remote_before_1_92: "a4a2539 Read the link on paste and size HLS videos right"
  current_release: "1.95; consulter git log pour l'identifiant du commit de publication"
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
    - telechargeur_youtube_v1.88.pyw: clair par défaut, fenêtre affichée une seule fois
    - telechargeur_youtube_v1.89.pyw: yt-dlp en version dossier, téléchargement depuis le JSON de l'aperçu
    - telechargeur_youtube_v1.90.pyw: retours d'un ami (clic droit, formats, tailles, historique, Opera GX), thème au clic droit
    - telechargeur_youtube_v1.91.pyw: lien analysé dès le collage, taille des vidéos HLS, icônes du mode sombre
    - telechargeur_youtube_v1.92.pyw: résultats yt-dlp explicites, playlists audio converties intégralement et erreurs de conversion signalées
    - telechargeur_youtube_v1.93.pyw: icônes préchargées pour les deux thèmes, remplacement explicite de l'image ttk et logos sans disque clair dans les deux modes
    - telechargeur_youtube_v1.94.pyw: icône PayPal régénérée depuis le SVG officiel et menus contextuels avec texte clair en mode sombre
    - telechargeur_youtube_v1.95.pyw: texte des menus sombres en blanc pur et gras, après comparaison du rendu réel avec la capture utilisateur
    - telechargeur_youtube_v1.96.pyw: menus sombres en blanc fin, commandes indisponibles grises sans effet gravé
  files_expected:
    - telechargeur_youtube_v1.96.pyw
    - auth_support.py
    - test_auth_support.py
    - tools_manager.py
    - test_tools_manager.py
    - test_app_tools_ui.py
    - test_build_exe.py
    - test_app_ergonomics.py
    - test_app_presentation.py
    - test_download_results.py
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
    values: [Aucun, Chrome, Edge, Firefox, Brave, Opera, Opera GX]
    mapping:
      Chrome: chrome
      Edge: edge
      Firefox: firefox
      Brave: brave
      Opera: opera
      Opera GX: "opera:<APPDATA>\\Opera Software\\Opera GX Stable"
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

VERSION_1_88_CHANGE:
  - Light theme by default (DEFAULT_THEME, chosen by the user). StreamDL-sombre.exe, -natif.exe and
    -auto.exe (follows Windows) still select another look.
  - Filming the opening showed an empty 486x538 window for ~0.45 s before the real one, and a light
    title bar over the dark theme: use_dark_title_bar() called update_idletasks() before build_ui,
    which mapped the root early; Tk then recreated the frame window (icon, size), losing the dark
    title bar. App.__init__ now withdraws the root, builds everything, then deiconifies it once
    (only if it was not withdrawn by the caller, so the tests stay hidden). The dark title bar is set
    on <Map> (follow_theme_title_bar) with SetWindowPos(SWP_FRAMECHANGED) to repaint the frame.
  - Tests: Tk roots must not be freed outside the main thread (Tcl_AsyncDelete abort): the test
    cleanup joins worker threads and runs gc.collect(); avoid closures stored on a root.

VERSION_1_89_CHANGE:
  - Where the time went (measured): opening the app 0.5-0.75 s; each yt-dlp.exe start 1.5 s
    (the single-file build unpacks itself at every run); 2 yt-dlp runs per video (-J, download),
    and the download run read the YouTube page and solved the JS challenge again. A Rust rewrite
    was considered and rejected: yt-dlp stays Python whatever the app is written in.
  - yt-dlp folder build: YTDLP.asset_name = "yt-dlp_win.zip" (yt-dlp.exe + _internal\, 143 files,
    39 MB), checked against SHA2-256SUMS like before. Starts in 0.47 s instead of 1.46 s.
    _extract_members keeps sub-folders; every path part must match SAFE_NAME_RE and must not be a
    Windows device name (NUL, CON...). ToolSpec.required_dirs=("_internal",): a copy without it
    (the single yt-dlp.exe installed by 1.84-1.88) is ignored and replaced by the folder build at
    the first launch of 1.89 (~3 s). Copies made by 1.89 still work with older exes.
  - YTDLP_SINGLE_FILE (asset yt-dlp.exe) is kept for build_exe.py --full, which embeds one file.
  - The download reuses the -J JSON of the preview (--load-info-json, temporary file in %TEMP%,
    deleted at once: it may hold request cookies) for a single video (_type == "video"). Playlists
    read their pages again (links expire after a few hours). If the JSON run fails (expired link),
    run_download() logs it and runs again with the URL.
  - Real test, hidden window, 19 s video, MP4 shortcut, click to file ready: 1.88 = 10.4 s,
    1.89 = 4.8 s (6.2 s on the very first run, while the antivirus scans the new files).
  - Limit: the longest member path is 81 characters; a tool folder deeper than ~170 characters
    exceeds Windows' 260-character limit and the yt-dlp install fails (FileNotFoundError). The real
    %LOCALAPPDATA%\StreamDL\tools path is far below that.

VERSION_1_90_CHANGE (feedback from a friend using an older version):
  - Window title "StreamDL v1.90" (was "Téléchargeur Vidéo v1.89 by Clemzy").
  - Right-click in every text field (class bindings TEntry/Entry/Text, bind_edit_menus):
    Couper / Copier / Coller / Tout sélectionner, greyed out when they do not apply (read-only
    journal: copy only). Tests use a fake clipboard: never touch the real one.
  - Right-click anywhere in the main window (root <Button-3>, and at the end of the text-field
    menu): "Passer en mode sombre" / "Passer en mode clair". switch_theme() re-applies sv-ttk,
    recolors the ttk labels that took palette colors (recolor_labels: ttk widgets only, since
    sv-ttk's own background #1c1c1c equals the light palette's text color), the journal, the GitHub
    icon and the title bar, and saves settings["theme"]. Startup order: exe name suffix, then the
    saved theme, then light. Not offered with the classic look (-natif / no sv-ttk).
  - Format dialog rewritten (FormatSelector): "Automatique" (with its size) or "Personnalisé" with
    a Type list (Vidéo avec son / Vidéo uniquement (sans son) / Audio uniquement) and a Format list.
    format_choices(info) builds them from yt-dlp's -J: "Vidéo avec son" = combined formats plus
    video-only ones merged with the best audio ("137+ba/137", saved as MP4); storyboards, DRC
    audio copies and formats with unknown codecs are left out; HLS copies of the same quality
    lose to the direct download. Labels: "1080p · 60 i/s · H.264 · ~245,7 Mo", "129 kb/s · AAC ·
    m4a · ~9,8 Mo". current_formats_list holds these choices ({"format", "kind", "label", "size",
    "ext"}).
  - Sizes in French units (human_size: o, Ko, Mo, Go); estimated_size() uses filesize, then
    filesize_approx, then bitrate x duration. The preview line ends with "~<size>" for the
    automatic choice. The -J call now gets --ffmpeg-location: without it yt-dlp sized a single
    360p file (27 MB) instead of the 2160p + audio merge (743 MB) actually downloaded.
  - History kept between launches in history.json (beside settings.json, 100 entries, newest
    first, damaged file ignored), dates "31/10 13:05", "Vider" button (asks first; files kept).
  - Opera GX: cookies read from %APPDATA%\Opera Software\Opera GX Stable ("opera:<path>").
    Not tested for real: Opera GX is not installed on the dev PC.
  - SHA-256: the code already wrote <video>.sha256.txt in the download folder; it is now written
    beside the video itself. Checked for real (file next to the MP4).
  - Default download folder: already done in 1.85 (Windows Downloads folder).
  - Real test (hidden window): "Vidéo avec son" first choice -> MP4 with h264 + audio tracks,
    .sha256.txt beside it, history.json written. Captures of the dialog and the runtime dark
    switch checked; the dark title bar attribute reads 1 after the switch (PrintWindow of a
    transparent window does not draw it).

VERSION_1_91_CHANGE:
  - Size of "Automatique" was wrong for _MK4k-KfWq8 (30,7 Mo shown, >600 Mo real): yt-dlp picks
    the Premium 1080p over HLS (616), which has no size, and its filesize_approx then counts the
    audio alone. automatic_size() now sums yt-dlp's requested_formats with estimated_size(); an
    HLS format is sized from its announced (peak) bitrate x duration x a factor measured on the
    qualities offered both as HLS and as a direct download of known size, per height
    (hls_size_factors: 0.48 at 1080p for that video, about 0.36-0.48 below; 0.5 when nothing can
    be measured). Result 614,2 Mo. Premium formats are listed apart ("· Premium").
  - The link is read as soon as it is pasted or typed (url_var trace, 0.7 s after the last change):
    the preview shows title, channel, duration and the automatic size without any click.
    fetch_info() shares that yt-dlp -J result with the buttons (same link, playlist mode and
    cookie source, 30 min at most; a second caller waits for the first); failures are never
    reused and the paste analysis stays quiet (the buttons show the errors). Playlists are not
    read on paste (minutes for a long one). Real test: preview with "~614,2 Mo" 6.4 s after the
    paste, then "Vidéo MP4" started the download 0.17 s after the click, with one -J call.
  - Dark theme icons: social_tiktok/youtube/pc32/paypal_dark.png are the light icons without
    their white disc at 20 % opacity (grey on dark), "un-composited" pixel by pixel so the
    logos keep their soft edges; social_github_dark.png is now pure white. The light theme keeps
    the original icons.

RECENT_TEST_VIDEO:
  url: https://www.youtube.com/watch?v=55q-1jpgnGc
  title: "SpaceX Falcon 9 Starlink Launch (Vandenberg) | Falcon 9 Booster Landing"
  observed_formats: "Only m3u8 formats 91-96; format 96 is 1080p around 5.4 Mbit/s."
  implication: "Slow download can be normal for this HLS source; ffmpeg is required."

VERSION_1_92_CHANGE:
  - yt-dlp reports each final media path with --print after_move:STREAMDL_FILE:%(filepath)j;
    --no-simulate, --progress and --no-quiet preserve downloading, progress and the
    destination lines needed to clean up cancelled downloads. Final paths are
    parsed as JSON, deduplicated and confined to the chosen destination. No before/after
    scan of the destination: existing files are detected, unrelated files are left alone.
  - Every item of an audio or video playlist receives the chosen conversion. History
    records each actual result, including original files when a conversion fails.
  - Failed conversions preserve the source, remove the incomplete conversion output
    and produce a visible warning instead of an unconditional green success. The
    warning remains visible after an optional SHA-256 calculation.
  - UI callbacks are guarded during closure and pending Tk callbacks are cancelled;
    yt-dlp and ffmpeg output streams are closed explicitly.
  - Optional sv-ttk typing and the optional PyInstaller import pass Mypy. Image tests
    no longer call Pillow's deprecated getdata API.
  - Checks: py -3.13 -m unittest discover -v (190 tests), ruff check .,
    mypy auth_support.py tools_manager.py build_exe.py telechargeur_youtube_v1.92.pyw.
  - Real-tool integration on local HTTP fixtures: MP4 with SHA-256, a second
    download of the existing MP4 with SHA-256, two playlist items converted
    to MP3, history and progress. Real yt-dlp cancellation also removes its
    partial output while preserving an unrelated file in the same folder.
  - The pre-existing download.ico and download.png edits are preserved locally and
    used by the local build; they are excluded from the corrective source commit.
  - The user explicitly requested the light Nuitka build and push for this release.

VERSION_1_93_CHANGE:
  - Both GitHub PhotoImages (black for light, white for dark) are loaded at
    startup with an explicit Tk master and retained for the entire session.
    switch_theme() reuses them instead of re-reading PNG files. The ttk image
    option is cleared then reassigned after the theme is rebuilt.
  - The existing transparent social_*_dark.png logos are used on both themes
    for TikTok, YouTube, PC32 and PayPal. Their translucent white background
    discs no longer turn grey on a dark background. Original PNGs are preserved.
  - Regression checks inspect the actual button image, GitHub pixel color and
    background transparency for light/dark/light and dark/light/dark sequences,
    including a switch with the PNG files unavailable. No new images are loaded
    and the number of retained PhotoImages remains stable on repeated switches.
  - The user requested the correction after screenshots of the compiled v1.92
    showed stale icons. The light Nuitka EXE was visually checked for both
    light/dark/light and dark/light/dark startup sequences: GitHub changes
    black/white correctly and the other logos have no grey discs. Both test
    sessions exited normally. Full suite: 193 passing tests; Ruff and Mypy clean.

VERSION_1_94_CHANGE:
  - The PayPal PNGs are rendered directly from the official full-color SVG,
    kept at assets/paypal-mark-color.svg with its source and Inkscape command
    in assets/README.md. Both 32x32 RGBA variants are identical. Antialiased
    edges contain blue color and alpha, with no white matte or circular disc.
  - make_context_menu() supplies explicit normal, selected and disabled colors
    to both text-field edit menus and the main-window theme menu. Enabled text
    is #f3f3f3 on the dark theme; newly opened light menus use #1c1c1c.
  - Regression tests cover the PayPal alpha/color edges and both context-menu
    entry points, including switching back to the light theme.
  - Validation: 197 tests pass; Ruff and Mypy clean. The light Nuitka EXE was
    visually checked for the PayPal mark on dark and light backgrounds, and
    light text in both the main-window menu and the text-field edit menu on
    the dark theme. The isolated UI session exited normally.

VERSION_1_95_CHANGE:
  - The user still perceived v1.94 menu lettering as grey. A visual comparison
    confirmed that pure white (#ffffff) with Segoe UI 10 bold gives stronger
    visible contrast than the previous off-white normal lettering.
  - Both dark context menus now use that white/strong font for normal and
    highlighted commands. Light menus retain dark text and normal font weight.
    Unavailable actions retain their disabled color.
  - Tests inspect the resolved font weight as well as normal/active text colors;
    a color option alone must not be presented as proof of the displayed result.
  - Validation: 61 presentation/version/text tests pass; Ruff and Mypy clean;
    light Nuitka build succeeds. Both compiled dark menus were visually checked,
    including Cut and Copy enabled by selecting the isolated destination field.
    The test session exited normally.

VERSION_1_96_CHANGE:
  - The user still saw blurred grey lettering in the dark context menus (screenshot of
    Couper/Copier unavailable): on Windows, Tk draws an entry in the disabled state
    "engraved", with a white copy of the label one pixel lower, even when
    disabledforeground is set. Invisible on a white menu, blurred on a dark one.
  - add_menu_command() draws an unavailable command as a normal entry: grey label
    (the menu's disabledforeground), grey on hover, no highlight (activebackground =
    background) and a command that does nothing. No menu entry uses Tk's disabled state.
  - Dark menus use thin lettering again (Segoe UI 10 normal, pure white), as the user asked:
    the bold of 1.95 did not remove the blur, which came from the disabled entries.
  - Tests check every entry is in the normal state, the grey and hover colors of the
    unavailable ones, that they do nothing, and the normal font weight.
  - Not checked by a capture: showing the real popup menu needs it on the user's screen.

APP_ICON (after 1.95, no source change):
  - The old download.ico had no real transparency: a grey checkerboard was baked into the
    image (alpha never below 220), so shortcuts showed a whitish square around the red
    document, and its small sizes mixed the play triangle, badge and sound wave together.
  - Redrawn: red document with a folded corner (vertical gradient), white play triangle,
    dark download badge and sound wave, with real transparency. download.png is the
    1024 px master.
  - download.ico holds that drawing at 256 px only, chosen by the user. A 10-size version
    (each size drawn on its own: 16-32 px document and play only, 40-64 px plus the badge)
    was tried and rejected: the icon looked smaller by default. Do not replace it without
    asking. Windows shrinks the 256 px image itself for the small sizes.
  - Windows may keep the old icon of existing shortcuts in its cache until they are recreated.

KNOWN_LIMITS:
  - HLS sizes remain estimates; source peak bitrates do not provide an exact file size.
  - Opera GX cookie extraction has not been tested on an installed Opera GX browser.
  - The optional SHA-256 sidecar covers the main file of a playlist.
  - The Windows executable is not digitally signed.

WORKFLOW:
  - Inspect git status before edits.
  - Use apply_patch for source edits.
  - Rename source to next version for every modification.
  - Run py -3.13 -m py_compile on the new source.
  - Do not build an exe unless explicitly requested.
  - Commit intentional source changes and push to origin/main when appropriate.
  - Do not commit ffmpeg.exe or any cookies file without explicit instruction.
