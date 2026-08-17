import os
import platform
import configparser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = (
    os.environ["USERPROFILE"]
    if platform.system() == "Windows"
    else os.environ.get("HOME", os.path.expanduser("~"))
)

IMAGE_DIR = os.environ.get("IMAGE_DIR", os.path.join(BASE_DIR, "downloads", "images"))
VIDEO_DIR = os.environ.get("VIDEO_DIR", os.path.join(BASE_DIR, "downloads", "videos"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _config_paths():
    paths = []
    env_path = os.environ.get("DHS622_CONFIG")
    if env_path:
        paths.append(env_path)
    paths.append(os.path.join(BASE_DIR, "dhs622_config.cfg"))
    paths.append(os.path.join(HOME_DIR, "dhs622_config.cfg"))
    return paths


def _read_cfg():
    parser = configparser.ConfigParser()
    for path in _config_paths():
        if os.path.isfile(path):
            parser.read(path)
            return parser, path
    return parser, None


_cfg, CONFIG_PATH = _read_cfg()


def _get(section, key, env_name):
    value = os.environ.get(env_name)
    if value:
        return value
    if _cfg.has_option(section, key):
        return _cfg.get(section, key)
    return None


insta_username = _get("instagram", "username", "INSTAGRAM_USERNAME")
insta_password = _get("instagram", "password", "INSTAGRAM_PASSWORD")


def require_instagram_credentials():
    if insta_username and insta_password:
        return
    searched = ", ".join(_config_paths())
    raise SystemExit(
        "Missing Instagram credentials.\n"
        "Copy dhs622_config.cfg.example to dhs622_config.cfg (or ~/dhs622_config.cfg) "
        "and fill in username/password, or set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD.\n"
        f"Looked in: {searched}"
    )
