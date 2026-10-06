import json
import runpy
import webbrowser
from pathlib import Path
from urllib.request import urlopen

try:
    with urlopen('http://127.0.0.1:8765/api/config', timeout=2) as response:
        config = json.load(response)
    if config.get('app') != 'youtube-indirici':
        raise ValueError('Port başka bir uygulama tarafından kullanılıyor.')
except Exception:
    runpy.run_path(str(Path(__file__).with_name('server.py')), run_name='__main__')
else:
    webbrowser.open('http://127.0.0.1:8765')
