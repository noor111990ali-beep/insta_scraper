import os

from config import BASE_DIR

CHANNELS_FILE = os.environ.get(
    "CHANNELS_FILE", os.path.join(BASE_DIR, "channels.txt")
)


def normalize_handle(raw: str) -> str:
    handle = (raw or "").strip()
    if not handle or handle.startswith("#"):
        return ""
    if "instagram.com/" in handle:
        handle = handle.split("instagram.com/", 1)[1]
    handle = handle.split("?", 1)[0].strip("/").lstrip("@")
    handle = handle.split("/")[0].strip()
    return handle


def load_channels(path: str | None = None) -> list[str]:
    file_path = path or CHANNELS_FILE
    if not os.path.isfile(file_path):
        return []

    handles = []
    seen = set()
    with open(file_path, "r", encoding="utf-8") as handle_file:
        for line in handle_file:
            handle = normalize_handle(line)
            if not handle or handle in seen:
                continue
            seen.add(handle)
            handles.append(handle)
    return handles


def write_channels(handles: list[str], path: str | None = None) -> str:
    file_path = path or CHANNELS_FILE
    lines = [
        "# Put one Instagram channel per line. You can use the username or the profile URL.",
        "# Lines that start with # are ignored.",
        "",
    ]
    for handle in handles:
        normalized = normalize_handle(handle)
        if normalized:
            lines.append(normalized)
    with open(file_path, "w", encoding="utf-8") as handle_file:
        handle_file.write("\n".join(lines).rstrip() + "\n")
    return file_path
