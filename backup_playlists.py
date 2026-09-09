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
    logging.info(f"Opening browser for Spotify login on source account...")
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

def fetch_all(url, headers, params=None):
    if params is None:
        params = {}
    params['limit'] = 50
    items = []
    
    while url:
        if not url.startswith('https://api.spotify.com/v1/'):
            url = 'https://api.spotify.com/v1/' + url
            
        response = requests.get(url, headers=headers, params=params if '?' not in url else None, verify=False)
        response.raise_for_status()
        data = response.json()
        items.extend(data['items'])
        url = data.get('next')
        params = {}
    return items

def main():
    token = get_access_token('playlist-read-private playlist-read-collaborative user-library-read')
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    logging.info("Loading user information...")
    me = requests.get('https://api.spotify.com/v1/me', headers=headers, verify=False).json()
    logging.info(f"Logged in as {me.get('display_name', 'Unknown User')} ({me.get('id')})")
    
    logging.info("Fetching playlists...")
    playlists_raw = fetch_all('me/playlists', headers)
    logging.info(f"Found {len(playlists_raw)} playlists.")
    
    backup_data = []
    for index, pl in enumerate(playlists_raw, start=1):
        name = pl.get('name', 'Untitled Playlist')
        logging.info(f"[{index}/{len(playlists_raw)}] Fetching tracks for playlist: {name}")
        
        try:
            tracks_raw = fetch_all(pl['tracks']['href'], headers)
            track_uris = [
                t['track']['uri'] for t in tracks_raw 
                if t.get('track') and t['track'].get('uri')
            ]
            backup_data.append({
                'name': name,
                'description': pl.get('description', ''),
                'public': pl.get('public', True),
                'collaborative': pl.get('collaborative', False),
                'tracks': track_uris
            })
        except Exception as e:
            logging.error(f"Failed to fetch tracks for {name}: {e}")
            
    logging.info(f"Saving backup to {BACKUP_FILE}...")
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2)
        
    logging.info("Backup completed successfully!")

if __name__ == '__main__':
    main()
