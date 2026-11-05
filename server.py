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
ARIA = ROOT / '.tools' / 'aria2c.exe'
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
    args = [str(TOOL), '--ignore-config', '--encoding', 'utf-8', '--no-colors', '--no-warnings', '--socket-timeout', '25', '--retries', '2']
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


def publish_file(job_id, path, folder, mode):
    path = path.resolve()
    if not path.is_relative_to(folder.resolve()) or path.suffix.lower() != '.' + mode or not path.is_file():
        return
    destination = DOWNLOADS / mode
    destination.mkdir(parents=True, exist_ok=True)
    title = re.sub(r' \[[A-Za-z0-9_-]+\]$', '', path.stem).rstrip(' .') or 'İndirme'
    number = 1
    while True:
        name = title + (f' ({number})' if number > 1 else '') + '.' + mode
        target = destination / name
        try:
            stream = target.open('xb')
            break
        except FileExistsError:
            number += 1
    try:
        with stream, path.open('rb') as source:
            shutil.copyfileobj(source, stream)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    path.unlink()
    with LOCK:
        JOBS[job_id]['files'].append({'name': name, 'url': '/files/' + mode + '/' + name})


def run_job(job_id, value, mode, scope):
    folder = ROOT / '.tools' / 'download-work' / job_id
    folder.mkdir(parents=True, exist_ok=True)
    video, playlist = normalize_url(value)
    single, full = urls(video, playlist)
    args = base_args() + ['--newline', '--progress', '--windows-filenames', '--no-overwrites', '--no-simulate',
            '--concurrent-fragments', '8',
            '--extractor-args', 'youtube:player_client=web_embedded,default',
            '--output', str(folder / '%(title).150B [%(autonumber)06d].%(ext)s'),
            '--progress-template', 'download:PROGRESS|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s',
            '--print', 'before_dl:ITEM|%(playlist_index)s|%(n_entries)s|%(title)j',
            '--print', 'after_move:FILE|%(filepath)j']
    if ARIA.exists():
        args += ['--downloader', str(ARIA)]
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        args += ['--ffmpeg-location', str(Path(ffmpeg).parent)]
    if mode == 'mp3':
        args += ['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '--audio-quality', '320K']
    else:
        args += ['-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio/bestvideo[height<=1080]+bestaudio/best[height<=1080]', '--merge-output-format', 'mp4', '--remux-video', 'mp4']
    args += ['--yes-playlist', full] if scope == 'playlist' else ['--no-playlist', single]
    errors = []
    try:
        update(job_id, status='downloading', message='İndirme hazırlanıyor…')
        process = spawn_process(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        for raw in process.stdout:
            line = raw.strip()
            if line.startswith('ITEM|'):
                _, index, total, title = line.split('|', 3)
                title = json.loads(title)
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
                pct = min(99, round(done / total * 100, 1)) if total else 0
                with LOCK:
                    prev = JOBS[job_id].get('percent', 0)
                update(job_id, percent=max(prev, pct), speed=speed, eta=eta, message='İndiriliyor…')
            elif line.startswith('FILE|'):
                publish_file(job_id, Path(json.loads(line[5:])), folder, mode)
            elif line.startswith(('[ExtractAudio]', '[Merger]', '[VideoConvertor]', '[VideoRemuxer]')):
                update(job_id, message='Dosya dönüştürülüyor…', percent=99, speed=0, eta=0)
            elif 'ERROR:' in line:
                errors.append(clean_error(line))
        code = process.wait()
        # A successful process may omit its final output notification.
        # Only recover complete files from this job, never older downloads.
        if code == 0:
            for path in folder.glob('*.' + mode):
                publish_file(job_id, path, folder, mode)
        with LOCK:
            count = len(JOBS[job_id]['files'])
        if code or not count:
            detail = errors[-1] if errors else 'İndirme tamamlanamadı.'
            if count:
                detail = f'{count} dosya kaydedildi; bazı işlemler tamamlanamadı. ' + detail
            update(job_id, status='error', message=detail, percent=0)
        else:
            update(job_id, status='completed', message=f'{count} dosya hazır.', percent=100, speed=0, eta=0)
    except Exception as exc:
        update(job_id, status='error', message=str(exc), percent=0)
    finally:
        if 'process' in locals():
            with LOCK:
                PROCESSES.discard(process)
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()


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
            return self.respond({'app': 'youtube-indirici', 'ready': TOOL.exists() and bool(shutil.which('ffmpeg')), 'download_folder': 'indirilenler/mp3 (ses) · indirilenler/mp4 (video)'})
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
        self.send_header('Cache-Control', 'no-store')
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


def fast_download():
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from urllib.request import Request, urlopen
    argc = int(os.environ.get('FAST_DL_ARGC', '0'))
    args = [os.environ.get(f'FAST_DL_ARG_{i}', '') for i in range(argc)]
    directory, output, url = '.', '', ''
    headers = {'User-Agent': 'Mozilla/5.0'}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--dir' and i + 1 < len(args):
            directory = args[i + 1]
            i += 2
        elif arg == '--out' and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        elif arg == '--header' and i + 1 < len(args):
            if ':' in args[i + 1]:
                k, v = args[i + 1].split(':', 1)
                headers[k.strip()] = v.strip()
            i += 2
        elif arg == '--' and i + 1 < len(args):
            url = args[i + 1]
            break
        elif arg.startswith(('http://', 'https://')):
            url = arg
            i += 1
        else:
            i += 1
    if not url or not output:
        raise SystemExit(1)
    target = (Path(directory) / output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    q = parse_qs(urlparse(url).query)
    total = int(q['clen'][0]) if 'clen' in q and q['clen'][0].isdigit() else 0
    if not total:
        probe = dict(headers)
        probe['Range'] = 'bytes=0-0'
        with urlopen(Request(url, headers=probe), timeout=15) as resp:
            cr = resp.headers.get('Content-Range', '')
            if '/' in cr and cr.rsplit('/', 1)[-1].isdigit():
                total = int(cr.rsplit('/', 1)[-1])
            elif resp.headers.get('Content-Length', '').isdigit():
                total = int(resp.headers['Content-Length'])
    if not total:
        with urlopen(Request(url, headers=headers), timeout=30) as resp, target.open('wb') as f:
            shutil.copyfileobj(resp, f)
        return
    chunk = 262144 if total < 16 * 1048576 else 1048576
    ranges = [(s, min(s + chunk - 1, total - 1)) for s in range(0, total, chunk)]
    use_query_range = 'googlevideo.com' in url and 'range=' not in url
    started = time.monotonic()
    done = 0
    last_print = 0.0
    file_lock = threading.Lock()
    with target.open('wb') as f:
        f.truncate(total)
        def fetch(rng):
            nonlocal done, last_print
            s, e = rng
            expected = e - s + 1
            for attempt in range(5):
                try:
                    if use_query_range:
                        req = Request(f'{url}&range={s}-{e}', headers=headers)
                    else:
                        h = dict(headers)
                        h['Range'] = f'bytes={s}-{e}'
                        req = Request(url, headers=h)
                    with urlopen(req, timeout=8) as resp:
                        data = resp.read()
                    if len(data) != expected:
                        raise IOError('Eksik parça')
                    with file_lock:
                        f.seek(s)
                        f.write(data)
                        done += len(data)
                        now = time.monotonic()
                        if now - last_print >= 0.1 or done == total:
                            elapsed = max(0.001, now - started)
                            speed = done / elapsed
                            eta = (total - done) / speed if speed > 0 else 0
                            print(f'PROGRESS|{done}|{total}|{total}|{speed:.1f}|{eta:.1f}', flush=True)
                            last_print = now
                    return
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(0.2 * (attempt + 1))
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(fetch, r) for r in ranges]
            for fut in as_completed(futures):
                fut.result()


if __name__ == '__main__':
    if '--fast-dl' in __import__('sys').argv:
        fast_download()
        raise SystemExit(0)
    for mode in ('mp3', 'mp4'):
        (DOWNLOADS / mode).mkdir(parents=True, exist_ok=True)
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
