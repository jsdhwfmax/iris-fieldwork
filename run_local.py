"""Start the loopback portal with generated development credentials."""
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
settings = root/'.secrets/instance.json'
if not settings.exists():
    raise SystemExit('Run python prepare_local.py first, or configure app/backend.py through environment variables.')
config = json.loads(settings.read_text(encoding='utf-8'))
os.environ.update(IRIS_BASE_URL=config['base_url'], IRIS_USERNAME=config['username'], IRIS_PASSWORD=config['password'])
sys.path.insert(0, str(root/'app'))
from backend import main
main()
