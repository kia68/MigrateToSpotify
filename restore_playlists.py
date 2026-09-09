import base64
import hashlib
import os
import http.server
import json
import logging
import sys
import webbrowser
import urllib.parse
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, datefmt='%I:%M:%S', format='[%(asctime)s] %(message)s')

CLIENT_ID = '5c098bcc800e45d49e476265bc9b6934'
PORT = 43019
BACKUP_FILE = 'spotify_backup.json'

class SpotifyAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/redirect'):
            query = urllib.parse.urlsplit(self.path).query
            params = urllib.parse.parse_qs(query)
            code_list = params.get('code')
            
            if code_list:
                code = code_list[0]
                try:
                    # Exchange authorization code for access token via PKCE
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
                                    b'<h3>Login Successful!</h3>'
                                    b'<p>You can close this window now and return to the terminal.</p>'
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
                self.wfile.write(b'<html><body><h3>Authorization code not returned by Spotify</h3></body></html>')
                raise SpotifyAuthError("No authorization code in redirect parameters")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass # Suppress logging HTTP requests to terminal

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

def get_access_token(scope):
    verifier, challenge = generate_pkce_pair()
    
    url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'scope': scope,
        'redirect_uri': f'http://127.0.0.1:{PORT}/redirect',
        'code_challenge_method': 'S256',
        'code_challenge': challenge
    })
    logging.info(f"Opening browser for Spotify login on target (new) account...")
    webbrowser.open(url)
    
    try:
        server = http.server.HTTPServer(('127.0.0.1', PORT), SpotifyAuthHandler)
    except OSError:
        logging.error(f"Error: Port {PORT} is already in use. Another instance of this script may be running.")
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

def main():
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            playlists = json.load(f)
    except FileNotFoundError:
        logging.error(f"Backup file {BACKUP_FILE} not found. Please run backup_playlists.py first.")
        sys.exit(1)

    logging.info(f"Loaded {len(playlists)} playlists from backup.")

    token = get_access_token('playlist-modify-public playlist-modify-private')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    logging.info("Loading target user information...")
    me = requests.get('https://api.spotify.com/v1/me', headers=headers, verify=False).json()
    user_id = me.get('id')
    if not user_id:
        logging.error("Failed to fetch user ID of target account.")
        sys.exit(1)
    logging.info(f"Restoring to user: {me.get('display_name', 'Unknown User')} ({user_id})")

    for index, pl in enumerate(playlists, start=1):
        name = pl.get('name', 'Untitled Playlist')
        tracks = pl.get('tracks', [])
        logging.info(f"[{index}/{len(playlists)}] Recreating playlist: {name} ({len(tracks)} tracks)")

        is_collab = pl.get('collaborative', False)
        is_public = pl.get('public', True) if not is_collab else False

        payload = {
            'name': name,
            'description': pl.get('description', ''),
            'public': is_public,
            'collaborative': is_collab
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

            if tracks:
                for i in range(0, len(tracks), 100):
                    batch = tracks[i:i+100]
                    add_res = requests.post(
                        f'https://api.spotify.com/v1/playlists/{new_pl_id}/tracks',
                        headers=headers,
                        json={'uris': batch},
                        verify=False
                    )
                    add_res.raise_for_status()
                logging.info(f"Successfully added {len(tracks)} tracks to {name}.")
            else:
                logging.info(f"Playlist {name} has no tracks. Created empty playlist.")

        except Exception as e:
            logging.error(f"Failed to recreate playlist {name}: {e}")

    logging.info("Restore process completed successfully!")

if __name__ == '__main__':
    main()
