import json
import logging
import os
import sys
from ytmusicapi import YTMusic

logging.basicConfig(level=logging.INFO, datefmt='%I:%M:%S', format='[%(asctime)s] %(message)s')

AUTH_FILES = ['browser.json', 'oauth.json', 'headers_auth.json']
BACKUP_FILE = 'ytmusic_backup.json'

def auto_generate_browser_json(filepath='browser.json'):
    logging.info("Attempting automatic login from installed browser cookies...")
    try:
        import browser_cookie3
    except ImportError:
        logging.warning("'browser-cookie3' is not installed.")
        return False

    loaders = [
        ("Chrome", lambda: browser_cookie3.chrome(domain_name='.youtube.com')),
        ("Brave", lambda: browser_cookie3.brave(domain_name='.youtube.com')),
        ("Edge", lambda: browser_cookie3.edge(domain_name='.youtube.com')),
        ("Firefox", lambda: browser_cookie3.firefox(domain_name='.youtube.com')),
        ("Safari", lambda: browser_cookie3.safari(domain_name='.youtube.com')),
        ("All Browsers", lambda: browser_cookie3.load(domain_name='.youtube.com')),
    ]

    for name, loader in loaders:
        try:
            cookies = loader()
            cookie_dict = {c.name: c.value for c in cookies if c.value}
            if '__Secure-3PAPISID' in cookie_dict or 'SAPISID' in cookie_dict:
                logging.info(f"Successfully loaded YouTube session automatically from {name}!")
                cookie_str = '; '.join([f'{k}={v}' for k, v in cookie_dict.items()])
                headers = {
                    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'accept': '*/*',
                    'accept-language': 'en-US,en;q=0.9',
                    'content-type': 'application/json',
                    'cookie': cookie_str,
                    'authorization': 'SAPISIDHASH 123456_dummy',
                    'x-goog-authuser': '0',
                    'origin': 'https://music.youtube.com'
                }
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(headers, f, indent=4)
                return True
        except Exception:
            continue

    return False

def get_ytmusic_client():
    for auth_file in AUTH_FILES:
        if os.path.exists(auth_file):
            try:
                logging.info(f"Using cached authentication file '{auth_file}'...")
                return YTMusic(auth_file)
            except Exception as e:
                logging.warning(f"Could not load '{auth_file}': {e}")
                if os.path.exists(auth_file):
                    os.remove(auth_file)

    if auto_generate_browser_json('browser.json'):
        try:
            return YTMusic('browser.json')
        except Exception as e:
            logging.error(f"Failed to connect using automatic browser session: {e}")

    logging.error("Could not automatically detect a logged-in YouTube Music session in your browser.")
    logging.info("Please make sure you are logged in to https://music.youtube.com in Chrome, Firefox, Safari, or Edge and try again.")
    sys.exit(1)

def extract_track_info(track_item):
    title = track_item.get('title', '').strip()
    
    artists = track_item.get('artists')
    artist_name = ""
    if isinstance(artists, list):
        artist_names = [a.get('name') for a in artists if isinstance(a, dict) and a.get('name')]
        artist_name = ", ".join(artist_names)

    album = track_item.get('album')
    album_name = ""
    if isinstance(album, dict):
        album_name = album.get('name', '')

    return {
        'title': title,
        'artist': artist_name,
        'album': album_name
    }

def main():
    yt = get_ytmusic_client()
    logging.info("Successfully connected to YouTube Music.")

    backup_data = []

    # 1. Fetch Liked Songs
    logging.info("Fetching Liked Songs...")
    try:
        liked = yt.get_liked_songs(limit=500)
        liked_tracks = []
        for t in liked.get('tracks', []):
            info = extract_track_info(t)
            if info['title']:
                liked_tracks.append(info)
        
        if liked_tracks:
            logging.info(f"Found {len(liked_tracks)} Liked Songs.")
            backup_data.append({
                'name': 'Liked Songs (YouTube Music)',
                'description': 'Liked Songs exported from YouTube Music',
                'tracks': liked_tracks
            })
    except Exception as e:
        logging.warning(f"Could not fetch Liked Songs: {e}")

    # 2. Fetch User Library Playlists
    logging.info("Fetching YouTube Music playlists...")
    try:
        playlists_raw = yt.get_library_playlists(limit=100)
        logging.info(f"Found {len(playlists_raw)} playlists in library.")
    except Exception as e:
        logging.error(f"Failed to fetch library playlists: {e}")
        playlists_raw = []

    for index, pl in enumerate(playlists_raw, start=1):
        pl_id = pl.get('playlistId')
        name = pl.get('title', 'Untitled Playlist')
        if not pl_id:
            continue

        logging.info(f"[{index}/{len(playlists_raw)}] Fetching tracks for playlist: {name}")
        try:
            pl_details = yt.get_playlist(pl_id, limit=None)
            tracks_raw = pl_details.get('tracks', [])
            tracks_info = []
            for t in tracks_raw:
                info = extract_track_info(t)
                if info['title']:
                    tracks_info.append(info)

            backup_data.append({
                'name': name,
                'description': pl_details.get('description', ''),
                'tracks': tracks_info
            })
            logging.info(f"  -> Extracted {len(tracks_info)} tracks.")
        except Exception as e:
            logging.error(f"Failed to fetch tracks for playlist '{name}': {e}")

    if not backup_data:
        logging.warning("No playlists or tracks were found to back up.")
        return

    logging.info(f"Saving backup to {BACKUP_FILE}...")
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    logging.info(f"YouTube Music backup completed successfully! Saved to '{BACKUP_FILE}'.")

if __name__ == '__main__':
    main()
