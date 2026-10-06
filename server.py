import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DOWNLOADS = ROOT / 'indirilenler'
TOOL = ROOT / '.tools' / 'yt-dlp.exe'
JOBS = {}
LOCK = threading.Lock()
PORT = int(os.environ.get('YT_PORT', '8765'))
ORIGIN = f'http://127.0.0.1:{PORT}'
CREATE_FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
PROCESSES = set()
STOPPING = threading.Event()
SESSIONS = 0
HAD_SESSION = False
LAST_DISCONNECT = time.monotonic()
CLOSE_GRACE = 8


def spawn_process(args, **kwargs):
    with LOCK:
        if STOPPING.is_set():
            raise RuntimeError('Site kapatılıyor.')
        process = subprocess.Popen(args, creationflags=CREATE_FLAGS, **kwargs)
        PROCESSES.add(process)
        return process


def stop_children():
    with LOCK:
        processes = list(PROCESSES)
    for process in processes:
        if process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=CREATE_FLAGS, timeout=10)
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def watch_browser(server):
    started = time.monotonic()
    while not STOPPING.wait(1):
        with LOCK:
            idle = SESSIONS == 0 and (time.monotonic() - LAST_DISCONNECT >= CLOSE_GRACE if HAD_SESSION else time.monotonic() - started >= 90)
            if idle:
                STOPPING.set()
        if idle:
            try:
                stop_children()
            finally:
                server.shutdown()
            return


def normalize_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Geçerli bir YouTube bağlantısı gir.')
    p = urlparse(value.strip())
    host = (p.hostname or '').lower()
    if p.scheme not in ('https', 'http') or host not in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be') or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError('Yalnızca youtube.com ve youtu.be bağlantıları destekleniyor.')
    q = parse_qs(p.query)
    video = p.path.strip('/') if host == 'youtu.be' else q.get('v', [''])[0]
    if p.path.startswith(('/shorts/', '/live/', '/embed/')):
        video = p.path.split('/')[2]
    playlist = q.get('list', [''])[0]
    if video and not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('Video bağlantısı geçersiz.')
    if playlist and not re.fullmatch(r'[A-Za-z0-9_-]{2,200}', playlist):
        raise ValueError('Oynatma listesi bağlantısı geçersiz.')
    if not video and not playlist:
        raise ValueError('Bir video veya oynatma listesi bağlantısı gir.')
    return video, playlist


def urls(video, playlist):
    return (f'https://www.youtube.com/watch?v={video}' if video else None,
            f'https://www.youtube.com/playlist?list={playlist}' if playlist else None)


def base_args():
    args = [str(TOOL), '--ignore-config', '--no-colors', '--no-warnings', '--socket-timeout', '25', '--retries', '2']
    node = shutil.which('node')
    if node:
        args += ['--js-runtimes', f'node:{node}']
    return args


def inspect(value):
    video, playlist = normalize_url(value)
    single, full = urls(video, playlist)
    args = base_args() + ['--dump-single-json', '--skip-download', '--flat-playlist', '--playlist-end', '1']
    args += ['--no-playlist', single] if single else ['--yes-playlist', full]
    process = spawn_process(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    try:
        output, errors = process.communicate(timeout=90)
        if process.returncode:
            raise ValueError(clean_error(errors))
        info = json.loads(output)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    finally:
        with LOCK:
            PROCESSES.discard(process)
    if not single:
        entry = next((x for x in info.get('entries', []) if x), {})
        title = info.get('title') or entry.get('title') or 'Oynatma listesi'
    else:
        title = info.get('title') or 'YouTube videosu'
    return {'title': title, 'channel': info.get('channel') or info.get('uploader') or '', 'has_playlist': bool(playlist), 'has_video': bool(video), 'duration': info.get('duration')}


def clean_error(value):
    value = re.sub(r'\x1b\[[0-9;]*m', '', value or '').strip()
    lines = [x for x in value.splitlines() if 'ERROR:' in x]
    detail = (lines[-1] if lines else value[-700:]).replace('ERROR:', '').strip()
    return detail or 'YouTube içeriğine erişilemedi. Bağlantıyı ve internetini kontrol et.'


def update(job_id, **kwargs):
    with LOCK:
        JOBS[job_id].update(kwargs)


def run_job(job_id, value, mode, scope):
    folder = DOWNLOADS / job_id
    folder.mkdir(parents=True, exist_ok=True)
    video, playlist = normalize_url(value)
    single, full = urls(video, playlist)
    args = base_args() + ['--newline', '--progress', '--windows-filenames', '--no-overwrites', '--no-simulate',
            '--output', str(folder / (('%(playlist_index)03d - ' if scope == 'playlist' else '') + '%(title).150B [%(id)s].%(ext)s')),
            '--progress-template', 'download:PROGRESS|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s',
            '--print', 'before_dl:ITEM|%(playlist_index)s|%(n_entries)s|%(title)s',
            '--print', 'after_move:FILE|%(filepath)s']
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        args += ['--ffmpeg-location', str(Path(ffmpeg).parent)]
    if mode == 'mp3':
        args += ['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '--audio-quality', '320K']
    else:
        args += ['-f', 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', '--merge-output-format', 'mp4', '--recode-video', 'mp4']
    args += ['--yes-playlist', full] if scope == 'playlist' else ['--no-playlist', single]
    errors = []
    try:
        update(job_id, status='downloading', message='İndirme hazırlanıyor…')
        process = spawn_process(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        for raw in process.stdout:
            line = raw.strip()
            if line.startswith('ITEM|'):
                _, index, total, title = line.split('|', 3)
                update(job_id, title=title, item=int(index) if index.isdigit() else 1, total=int(total) if total.isdigit() else None, percent=0, message='İndiriliyor…')
            elif line.startswith('PROGRESS|'):
                parts = line.split('|')
                def number(x):
                    try:
                        return float(x)
                    except (ValueError, TypeError):
                        return 0
                done, exact, estimate, speed, eta = map(number, parts[1:6])
                total = exact or estimate
                update(job_id, percent=min(99, round(done / total * 100, 1)) if total else 0, speed=speed, eta=eta, message='İndiriliyor…')
            elif line.startswith('FILE|'):
                path = Path(line[5:]).resolve()
                if path.is_relative_to(folder.resolve()) and path.suffix.lower() == '.' + mode and path.exists():
                    with LOCK:
                        JOBS[job_id]['files'].append({'name': path.name, 'url': '/files/' + job_id + '/' + path.name})
            elif line.startswith(('[ExtractAudio]', '[Merger]', '[VideoConvertor]')):
                update(job_id, message='Dosya dönüştürülüyor…', percent=99, speed=0, eta=0)
            elif 'ERROR:' in line:
                errors.append(clean_error(line))
        code = process.wait()
        with LOCK:
            count = len(JOBS[job_id]['files'])
        if code or not count:
            update(job_id, status='error', message=errors[-1] if errors else 'İndirme tamamlanamadı.', percent=0)
        else:
            update(job_id, status='completed', message=f'{count} dosya hazır.', percent=100, speed=0, eta=0)
    except Exception as exc:
        update(job_id, status='error', message=str(exc), percent=0)
    finally:
        if 'process' in locals():
            with LOCK:
                PROCESSES.discard(process)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def trusted(self):
        return self.headers.get('Host') == f'127.0.0.1:{PORT}'

    def do_GET(self):
        from urllib.parse import unquote
        if not self.trusted():
            return self.respond({'error': 'Erişim reddedildi.'}, 403)
        path = unquote(urlparse(self.path).path)
        # Browser-only endpoints reject requests from other sites.
        if path.startswith(('/api/', '/files/')) and path != '/api/config':
            if self.headers.get('Sec-Fetch-Site') != 'same-origin':
                return self.respond({'error': 'Erişim reddedildi.'}, 403)
        if path == '/api/session':
            global SESSIONS, HAD_SESSION, LAST_DISCONNECT
            with LOCK:
                if STOPPING.is_set():
                    return self.respond({'error': 'Site kapatılıyor.'}, 503)
                SESSIONS += 1
                HAD_SESSION = True
            try:
                self.connection.settimeout(5)
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'close')
                self.end_headers()
                while not STOPPING.is_set():
                    self.wfile.write(b': connected\n\n')
                    self.wfile.flush()
                    STOPPING.wait(2)
            except (OSError, TimeoutError):
                pass
            finally:
                with LOCK:
                    SESSIONS -= 1
                    LAST_DISCONNECT = time.monotonic()
                self.close_connection = True
            return
        if path == '/api/config':
            return self.respond({'app': 'youtube-indirici', 'ready': TOOL.exists() and bool(shutil.which('ffmpeg')), 'download_folder': 'indirilenler'})
        if path.startswith('/api/jobs/'):
            with LOCK:
                data = dict(JOBS.get(path.rsplit('/', 1)[-1], {}))
            return self.respond(data, 200 if data else 404)
        if path.startswith('/files/'):
            file = (DOWNLOADS / path[7:]).resolve()
            if not file.is_relative_to(DOWNLOADS.resolve()) or file.suffix not in ('.mp3', '.mp4') or not file.is_file():
                return self.respond({'error': 'Dosya bulunamadı.'}, 404)
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg' if file.suffix == '.mp3' else 'video/mp4')
            self.send_header('Content-Length', str(file.stat().st_size))
            self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + __import__('urllib.parse', fromlist=['quote']).quote(file.name))
            self.end_headers()
            try:
                with file.open('rb') as stream:
                    shutil.copyfileobj(stream, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        mapping = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/favicon.svg': 'favicon.svg'}
        if path not in mapping:
            return self.respond({'error': 'Sayfa bulunamadı.'}, 404)
        file = ROOT / 'static' / mapping[path]
        types = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml'}
        body = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', types[file.suffix])
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if (not self.trusted() or self.headers.get('Origin') != ORIGIN
                or self.headers.get('Sec-Fetch-Site') != 'same-origin'
                or self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json'):
            return self.respond({'error': 'Erişim reddedildi.'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                raise ValueError('İstek boyutu geçersiz.')
            data = json.loads(self.rfile.read(size))
            value = data.get('url', '')
            video, playlist = normalize_url(value)
            if self.path == '/api/inspect':
                return self.respond(inspect(value))
            if self.path != '/api/download':
                return self.respond({'error': 'İşlem bulunamadı.'}, 404)
            mode, scope = data.get('format'), data.get('scope')
            if mode not in ('mp3', 'mp4') or scope not in ('single', 'playlist'):
                raise ValueError('Format veya indirme seçimi geçersiz.')
            if scope == 'single' and not video or scope == 'playlist' and not playlist:
                raise ValueError('Bağlantı bu indirme seçimini desteklemiyor.')
            if not TOOL.exists() or not shutil.which('ffmpeg'):
                raise ValueError('İndirme araçları eksik. Önce KURULUM.cmd dosyasını çalıştır.')
            with LOCK:
                if any(j['status'] in ('queued', 'downloading') for j in JOBS.values()):
                    return self.respond({'error': 'Devam eden indirme bittikten sonra tekrar dene.'}, 409)
                job_id = secrets.randbits(128).to_bytes(16, 'big').hex()
                JOBS[job_id] = {'id': job_id, 'status': 'queued', 'percent': 0, 'message': 'Sıraya alındı…', 'files': [], 'item': 1, 'total': None}
            threading.Thread(target=run_job, args=(job_id, value, mode, scope), daemon=True).start()
            return self.respond({'id': job_id}, 202)
        except (ValueError, json.JSONDecodeError) as exc:
            self.respond({'error': str(exc)}, 400)
        except subprocess.TimeoutExpired:
            self.respond({'error': 'YouTube yanıtı gecikti. Yeniden dene.'}, 504)
        except Exception:
            self.respond({'error': 'İşlem yapılamadı. Bağlantını ve kurulumunu kontrol et.'}, 500)


if __name__ == '__main__':
    DOWNLOADS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    threading.Thread(target=watch_browser, args=(server,), daemon=True).start()
    print(f'Site hazır: {ORIGIN}\nİndirilenler: {DOWNLOADS}\nKapatmak için Ctrl+C.')
    if '--no-browser' not in __import__('sys').argv:
        threading.Timer(0.7, lambda: webbrowser.open(ORIGIN)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        STOPPING.set()
        stop_children()
    finally:
        server.server_close()
