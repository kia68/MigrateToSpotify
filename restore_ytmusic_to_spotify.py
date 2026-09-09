import base64
import hashlib
import http.server
import json
import logging
import os
import re
import sys
import urllib.parse
import webbrowser
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, datefmt='%I:%M:%S', format='[%(asctime)s] %(message)s')

CLIENT_ID = '5c098bcc800e45d49e476265bc9b6934'
PORT = 43019
BACKUP_FILE = 'ytmusic_backup.json'

class SpotifyAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/redirect'):
            query = urllib.parse.urlsplit(self.path).query
            params = urllib.parse.parse_qs(query)
            code_list = params.get('code')
            
            if code_list:
                code = code_list[0]
                try:
                    payload = {
                        'client_id': CLIENT_ID,
                        'grant_type': 'authorization_code',
                        'code': code,
                        'redirect_uri': f'http://127.0.0.1:{PORT}/redirect',
                        'code_verifier': self.server.verifier
                    }
                    res = requests.post('https://accounts.spotify.com/api/token', data=payload, verify=False)
                    res.raise_for_status()
                    token_data = res.json()
                    access_token = token_data['access_token']
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body style="font-family: sans-serif; text-align: center; margin-top: 50px;">'
                                    b'<h3>Spotify Login Successful!</h3>'
                                    b'<p>You can close this window and return to the terminal.</p>'
                                    b'</body></html>')
                    raise SpotifyAuthSuccess(access_token)
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f'<html><body><h3>Authentication Failed</h3><p>{e}</p></body></html>'.encode('utf-8'))
                    raise SpotifyAuthError(str(e))
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><body><h3>Authorization code missing</h3></body></html>')
                raise SpotifyAuthError("No authorization code in redirect parameters")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass

class SpotifyAuthSuccess(BaseException):
    def __init__(self, token):
        self.token = token

class SpotifyAuthError(BaseException):
    def __init__(self, message):
        self.message = message

def generate_pkce_pair():
    rand_bytes = os.urandom(32)
    verifier = base64.urlsafe_b64encode(rand_bytes).decode('utf-8').rstrip('=')
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')
    return verifier, challenge

def get_spotify_access_token(scope):
    verifier, challenge = generate_pkce_pair()
    
    url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': scope,
        'redirect_uri': f'http://127.0.0.1:{PORT}/redirect',
        'code_challenge_method': 'S256',
        'code_challenge': challenge
    })
    logging.info("Opening browser for Spotify login...")
    webbrowser.open(url)
    
    try:
        server = http.server.HTTPServer(('127.0.0.1', PORT), SpotifyAuthHandler)
    except OSError:
        logging.error(f"Error: Port {PORT} is already in use. Ensure no other auth process is running.")
        sys.exit(1)
        
    server.verifier = verifier
    try:
        while True:
            server.handle_request()
    except SpotifyAuthSuccess as success:
        return success.token
    except SpotifyAuthError as err:
        logging.error(f"Authentication failed: {err.message}")
        sys.exit(1)

def clean_track_title(title):
    if not title:
        return ""
    # Remove common video title additions like (Official Video), (Audio), etc.
    patterns = [
        r'\s*[\(\[]\s*official\s+(music\s+)?(video|audio|lyric\s+video)?\s*[\]\)]',
        r'\s*[\(\[]\s*(video|audio|lyrics?|visualizer|hd|4k|remastered)\s*[\]\)]',
        r'\s*[\(\[]\s*explicit\s*[\]\)]',
        r'\s*[\(\[]\s*full\s+song\s*[\]\)]',
    ]
    cleaned = title
    for p in patterns:
        cleaned = re.sub(p, '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def search_spotify_track(headers, title, artist=""):
    cleaned_title = clean_track_title(title)
    if not cleaned_title:
        return None

    # First artist if multiple given
    primary_artist = artist.split(',')[0].strip() if artist else ""

    queries = []
    if primary_artist:
        queries.append(f'track:"{cleaned_title}" artist:"{primary_artist}"')
        queries.append(f'{cleaned_title} {primary_artist}')
    queries.append(f'track:"{cleaned_title}"')
    queries.append(f'{cleaned_title}')

    for q in queries:
        try:
            res = requests.get(
                'https://api.spotify.com/v1/search',
                headers=headers,
                params={'q': q, 'type': 'track', 'limit': 1},
                verify=False
            )
            if res.status_code == 200:
                data = res.json()
                items = data.get('tracks', {}).get('items', [])
                if items:
                    return items[0]['uri']
        except Exception:
            continue

    return None

def main():
    if not os.path.exists(BACKUP_FILE):
        logging.error(f"Backup file '{BACKUP_FILE}' not found. Please run backup_ytmusic.py first.")
        sys.exit(1)

    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            playlists = json.load(f)
    except Exception as e:
        logging.error(f"Failed to read backup file '{BACKUP_FILE}': {e}")
        sys.exit(1)

    logging.info(f"Loaded {len(playlists)} playlists from '{BACKUP_FILE}'.")

    token = get_spotify_access_token('playlist-modify-public playlist-modify-private')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    logging.info("Loading Spotify user profile...")
    me = requests.get('https://api.spotify.com/v1/me', headers=headers, verify=False).json()
    user_id = me.get('id')
    if not user_id:
        logging.error("Failed to fetch Spotify user profile ID.")
        sys.exit(1)
    logging.info(f"Connected to Spotify account: {me.get('display_name', 'Unknown User')} ({user_id})")

    for index, pl in enumerate(playlists, start=1):
        name = pl.get('name', 'Untitled Playlist')
        tracks = pl.get('tracks', [])
        logging.info(f"[{index}/{len(playlists)}] Processing YouTube Music playlist: {name} ({len(tracks)} tracks)")

        spotify_uris = []
        not_found_count = 0

        for t in tracks:
            title = t.get('title', '')
            artist = t.get('artist', '')
            uri = search_spotify_track(headers, title, artist)
            if uri:
                spotify_uris.append(uri)
            else:
                not_found_count += 1

        logging.info(f"  -> Matched {len(spotify_uris)}/{len(tracks)} tracks on Spotify. ({not_found_count} not found)")

        # Create Playlist on Spotify
        payload = {
            'name': name,
            'description': pl.get('description', '') or 'Migrated from YouTube Music',
            'public': True,
            'collaborative': False
        }

        try:
            create_res = requests.post(
                f'https://api.spotify.com/v1/users/{user_id}/playlists',
                headers=headers,
                json=payload,
                verify=False
            )
            create_res.raise_for_status()
            new_pl = create_res.json()
            new_pl_id = new_pl['id']

            if spotify_uris:
                for i in range(0, len(spotify_uris), 100):
                    batch = spotify_uris[i:i+100]
                    add_res = requests.post(
                        f'https://api.spotify.com/v1/playlists/{new_pl_id}/tracks',
                        headers=headers,
                        json={'uris': batch},
                        verify=False
                    )
                    add_res.raise_for_status()
                logging.info(f"  -> Successfully added {len(spotify_uris)} tracks to Spotify playlist '{name}'.")
            else:
                logging.warning(f"  -> Created empty Spotify playlist '{name}' (no tracks matched).")

        except Exception as e:
            logging.error(f"Failed to create or populate Spotify playlist '{name}': {e}")

    logging.info("YouTube Music to Spotify migration completed successfully!")

if __name__ == '__main__':
    main()
