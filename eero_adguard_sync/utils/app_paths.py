import os
from types import SimpleNamespace

from appdata import AppDataPaths


if os.getenv("EAG_DATA_DIR"):
    data_dir = os.path.abspath(os.getenv("EAG_DATA_DIR"))
    os.makedirs(data_dir, exist_ok=True)
    app_paths = SimpleNamespace(app_data_path=data_dir)
else:
    app_paths = AppDataPaths()
    if app_paths.require_setup:
        app_paths.setup()
