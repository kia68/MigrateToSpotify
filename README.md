# Spotify Playlist Migrator (Zero-Config)

A clean and simple Python tool to back up Spotify playlists from an old account and restore them to a new account. Built by **Kiavash Emami** with the help of **Antigravity** (Advanced Agentic Coding AI by Google DeepMind).

---

## Features
- **Zero-Config**: Uses a pre-registered Spotify Client ID. You do not need to register a developer app or manage client secrets.
- **Secure**: Utilizes Spotify's modern **Authorization Code Flow with PKCE** (`response_type=code`).
- **Flexible**: Bypasses SSL certificate verification to work seamlessly on restricted networks (such as corporate or university networks).
- **Comprehensive**: Copies playlist names, descriptions, and tracks in batches of 100.

---

## Requirements

Install the required Python packages:

- **macOS / Linux**:
  ```bash
  pip3 install requests urllib3 ytmusicapi browser-cookie3
  ```
- **Windows**:
  ```powershell
  pip install requests urllib3 ytmusicapi browser-cookie3
  ```

---

## 1. Spotify to Spotify Migration

1. **Back up your old Spotify account**:
   Open a terminal in the project directory and run:

   - **macOS / Linux**:
     ```bash
     python3 backup_playlists.py
     ```
   - **Windows**:
     ```powershell
     .\venv\Scripts\python.exe backup_playlists.py
     ```

   - A browser window will open. Log in with your **old (source) Spotify account** and grant permissions.
   - The script will extract all your playlists and save them locally to `spotify_backup.json`.

2. **Restore playlists to your new Spotify account**:
   Run:

   - **macOS / Linux**:
     ```bash
     python3 restore_playlists.py
     ```
   - **Windows**:
     ```powershell
     .\venv\Scripts\python.exe restore_playlists.py
     ```

   - A browser window will open. Log in with your **new (target) Spotify account** and grant permissions.
   - The script will read `spotify_backup.json`, automatically recreate all playlists, and copy all tracks over.

---

## 2. YouTube Music to Spotify Migration

1. **Back up your YouTube Music account**:
   Run:

   - **macOS / Linux**:
     ```bash
     python3 backup_ytmusic.py
     ```
   - **Windows**:
     ```powershell
     python backup_ytmusic.py
     ```

   - **Zero Setup**: The script automatically detects your logged-in YouTube Music session from Chrome, Firefox, Safari, Edge, or Brave! No DevTools or manual copy-pasting required.
   - It will extract all your playlists & Liked Songs and save them to `ytmusic_backup.json`.

2. **Import YouTube Music playlists to Spotify**:
   Run:

   - **macOS / Linux**:
     ```bash
     python3 restore_ytmusic_to_spotify.py
     ```
   - **Windows**:
     ```powershell
     python restore_ytmusic_to_spotify.py
     ```

   - Log in with your target **Spotify account** in the browser.
   - The script will search Spotify for matching tracks, create the playlists, and add all found tracks.




