# CODEX HANDOFF: StreamDL

META:
  language: fr
  project: Stream Video Downloader / StreamDL
  owner: Clemzy
  github: https://github.com/Clemzyy/StreamDL
  github_visibility: private
  git_identity: "Clemzy <troisquarks@proton.me>"
  workspace: "C:\Users\Utilisateur\OneDrive\Bureau\Applications Python\Téléchargeur vidéo"
  current_source: telechargeur_youtube_v1.75.pyw
  current_app_label: "Téléchargeur Vidéo V7.3 by Clemzy"
  next_source_version: "1.76"
  executable_policy: "Ne pas compiler de nouvel exe sauf demande explicite."

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
    - telechargeur_youtube_v1.75.pyw: version actuelle
  files_expected:
    - telechargeur_youtube_v1.75.pyw
    - yt-dlp.exe
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
    verified_version: 2026.07.04
    location: same directory as source
  javascript_runtime:
    implementation: find_js_runtime()
    preferred: node.exe
    local_environment: "Node v24.18.0 at C:\Program Files\nodejs\node.exe"
    command_option: "--js-runtimes node:<path>"
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
    detection: "find_ffmpeg() searches app dir, base dir, then PATH"
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
