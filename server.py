#!/usr/bin/env python3
"""Private, dependency-free browser for an imessage-exporter HTML archive."""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import re
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from html.parser import HTMLParser


APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
BODY_END_RE = re.compile(r'</body\s*>', re.I)
DIV_TAG_RE = re.compile(r'<div\b[^>]*>|</div\s*>', re.I)
MESSAGE_CLASS_RE = re.compile(r'class\s*=\s*["\'][^"\']*\bmessage\b[^"\']*["\']', re.I)


@dataclass
class Message:
    chat: str
    file: str
    index: int
    direction: str
    timestamp: str
    sender: str
    text: str


class ArchiveParser(HTMLParser):
    """Extract searchable text from top-level exported message nodes."""

    def __init__(self, chat: str, filename: str):
        super().__init__(convert_charrefs=True)
        self.chat, self.filename = chat, filename
        self.depth = 0
        self.message_depth = None
        self.parts: list[str] = []
        self.direction = "received"
        self.timestamp = ""
        self.sender = ""
        self.capture_timestamp = self.capture_sender = False
        self.messages: list[Message] = []

    @staticmethod
    def classes(attrs):
        return set(dict(attrs).get("class", "").split())

    def handle_starttag(self, tag, attrs):
        classes = self.classes(attrs)
        if tag == "div":
            self.depth += 1
            if "message" in classes and self.message_depth is None:
                self.message_depth = self.depth
                self.parts, self.timestamp, self.sender = [], "", ""
                self.direction = "received"
            elif self.message_depth is not None:
                if "sent" in classes:
                    self.direction = "sent"
                elif "received" in classes:
                    self.direction = "received"
        if self.message_depth is not None:
            if "timestamp" in classes:
                self.capture_timestamp = True
            if "sender" in classes:
                self.capture_sender = True

    def handle_endtag(self, tag):
        if tag == "span":
            self.capture_timestamp = self.capture_sender = False
        if tag == "div":
            if self.message_depth == self.depth:
                text = re.sub(r"\s+", " ", " ".join(self.parts)).strip()
                self.messages.append(Message(
                    self.chat, self.filename, len(self.messages), self.direction,
                    re.sub(r"\s+", " ", self.timestamp).strip(),
                    re.sub(r"\s+", " ", self.sender).strip(), text,
                ))
                self.message_depth = None
            self.depth -= 1

    def handle_data(self, data):
        if self.message_depth is None:
            return
        value = data.strip()
        if not value:
            return
        self.parts.append(value)
        if self.capture_timestamp:
            self.timestamp += " " + value
        if self.capture_sender:
            self.sender += " " + value


class Index:
    def __init__(self):
        self.lock = threading.Lock()
        self.archive_dir: Path | None = None
        self.ready = False
        self.building = False
        self.chats: list[dict] = []
        self.messages: list[Message] = []
        self.generation = 0

    def select_archive(self, archive_dir: Path):
        with self.lock:
            self.archive_dir = archive_dir
            self.generation += 1
            generation = self.generation
            self.building = True
            self.ready = False
            self.chats = []
            self.messages = []
        threading.Thread(target=self.build, args=(archive_dir, generation), daemon=True).start()

    def build(self, archive_dir: Path, generation: int):
        chats = []
        messages = []
        for path in sorted(archive_dir.glob("*.html"), key=lambda p: p.name.casefold()):
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                parser = ArchiveParser(path.stem, path.name)
                parser.feed(source)
                rows = parser.messages
                messages.extend(rows)
                last = rows[-1] if rows else None
                chats.append({
                    "name": path.stem,
                    "file": path.name,
                    "count": len(rows),
                    "last": last.timestamp if last else "",
                    "preview": last.text[-180:] if last else "No messages",
                })
            except OSError:
                continue
        chats.sort(key=lambda x: date_key(x["last"]), reverse=True)
        with self.lock:
            if generation != self.generation:
                return
            self.chats, self.messages = chats, messages
            self.ready, self.building = True, False

    def rebuild_async(self):
        with self.lock:
            if self.building or self.archive_dir is None:
                return False
            archive_dir = self.archive_dir
            self.generation += 1
            generation = self.generation
            self.building = True
            self.ready = False
        threading.Thread(target=self.build, args=(archive_dir, generation), daemon=True).start()
        return True

    def search(self, query: str, limit=150):
        terms = [t.casefold() for t in query.split() if t]
        if not terms:
            return []
        found = []
        for m in self.messages:
            haystack = f"{m.chat} {m.sender} {m.text}".casefold()
            if all(term in haystack for term in terms):
                excerpt = m.text
                pos = min((haystack.find(t) for t in terms if t in haystack), default=0)
                start = max(0, pos - 75)
                excerpt = excerpt[start:start + 240]
                found.append({
                    "chat": m.chat, "file": m.file, "index": m.index,
                    "timestamp": m.timestamp, "sender": m.sender,
                    "direction": m.direction, "text": excerpt,
                })
                if len(found) >= limit:
                    break
        return found


def date_key(value: str):
    value = value.split("(", 1)[0].strip()
    for fmt in ("%b %d, %Y %I:%M:%S %p", "%b %d, %Y %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return datetime.min


def mark_message(source: str, target: int) -> str:
    """Add an anchor to a top-level message without confusing nested replies."""
    depth = 0
    active_depth = None
    message_index = -1
    pieces = []
    cursor = 0
    for match in DIV_TAG_RE.finditer(source):
        tag = match.group(0)
        replacement = tag
        if tag.lower().startswith("</"):
            if active_depth == depth:
                active_depth = None
            depth -= 1
        else:
            depth += 1
            if active_depth is None and MESSAGE_CLASS_RE.search(tag):
                active_depth = depth
                message_index += 1
                if message_index == target:
                    replacement = re.sub(r'class\s*=\s*(["\'])', r'id="selected-message" class=\1search-hit ', tag, count=1, flags=re.I)
        pieces.extend((source[cursor:match.start()], replacement))
        cursor = match.end()
    pieces.append(source[cursor:])
    return "".join(pieces)


INDEX = Index()
ATTACHMENT_ROOT = (Path.home() / "Library" / "Messages" / "Attachments").resolve()


def choose_archive_folder() -> Path | None:
    """Open the native macOS folder chooser and return the selected folder."""
    script = 'POSIX path of (choose folder with prompt "Choose your iMessage HTML archive")'
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise RuntimeError("The macOS folder picker could not be opened.") from error
    if result.returncode != 0:
        if "User canceled" in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip() or "The folder picker failed.")
    return Path(result.stdout.strip()).expanduser().resolve()


def resolve_archive_file(archive_dir: Path, raw_path: str) -> Path | None:
    """Resolve a relative export path without allowing access outside the archive."""
    parsed = urlparse(html.unescape(raw_path))
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
        return None
    try:
        archive_root = archive_dir.resolve(strict=True)
        path = (archive_root / unquote(parsed.path)).resolve(strict=True)
        path.relative_to(archive_root)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def rewrite_local_attachments(source: str, archive_dir: Path) -> str:
    """Route original and copied attachments through the local web server."""
    attr_re = re.compile(
        r'(?P<attr>src|href)=(?P<quote>["\'])(?P<url>[^"\']+)(?P=quote)', re.I
    )

    def replace(match):
        raw_url = html.unescape(match.group("url"))
        parsed = urlparse(raw_url)
        if parsed.path.startswith("/Users/") and "/Library/Messages/Attachments/" in parsed.path:
            url = "/attachment?path=" + quote(unquote(parsed.path), safe="")
        else:
            path = resolve_archive_file(archive_dir, raw_url)
            if path is None:
                return match.group(0)
            relative = path.relative_to(archive_dir.resolve()).as_posix()
            url = "/archive-file?path=" + quote(relative, safe="")
        if parsed.fragment:
            url += "#" + quote(unquote(parsed.fragment), safe="")
        return f'{match.group("attr")}={match.group("quote")}{url}{match.group("quote")}'

    return attr_re.sub(replace, source)


class Handler(SimpleHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Browsers routinely cancel lazy image/video requests when a chat is
            # changed or media scrolls out of view. That is not a server error.
            pass

    def log_message(self, fmt, *args):
        pass

    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if parsed.path == "/api/state":
            archive = INDEX.archive_dir
            return self.json_response({
                "selected": archive is not None,
                "archive": archive.name if archive else "",
                "ready": INDEX.ready,
            })
        if parsed.path == "/api/chats":
            return self.json_response({"ready": INDEX.ready, "chats": INDEX.chats})
        if parsed.path == "/api/search":
            query = params.get("q", [""])[0][:200]
            return self.json_response({"ready": INDEX.ready, "results": INDEX.search(query) if INDEX.ready else []})
        if parsed.path == "/api/reindex":
            started = INDEX.rebuild_async()
            return self.json_response({"started": started, "ready": INDEX.ready})
        if parsed.path == "/chat":
            return self.serve_chat(params)
        if parsed.path == "/attachment":
            return self.serve_attachment(params)
        if parsed.path == "/archive-file":
            return self.serve_archive_file(params)
        if parsed.path == "/" or parsed.path == "/index.html":
            return self.serve_file(APP_DIR / "index.html", "text/html; charset=utf-8")
        if parsed.path in ("/app.css", "/app.js"):
            path = APP_DIR / parsed.path[1:]
            return self.serve_file(path, mimetypes.guess_type(path)[0] or "text/plain")
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/select-archive":
            return self.send_error(404)
        expected_origin = f"http://{self.headers.get('Host', '')}"
        if self.headers.get("Origin") not in (None, expected_origin):
            return self.json_response({"error": "Invalid request origin."}, status=403)
        try:
            archive = choose_archive_folder()
        except RuntimeError as error:
            return self.json_response({"error": str(error)}, status=500)
        if archive is None:
            return self.json_response({"cancelled": True})
        if not archive.is_dir():
            return self.json_response({"error": "The selected folder is not available."}, status=400)
        html_files = list(archive.glob("*.html"))
        if not html_files:
            return self.json_response({
                "error": "This folder does not contain any top-level HTML conversation files."
            }, status=422)
        INDEX.select_archive(archive)
        return self.json_response({"selected": True, "archive": archive.name})

    def serve_file(self, path: Path, content_type: str):
        try:
            data = path.read_bytes()
        except OSError:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_attachment(self, params):
        raw_path = params.get("path", [""])[0]
        try:
            path = Path(raw_path).resolve(strict=True)
            path.relative_to(ATTACHMENT_ROOT)
        except (OSError, ValueError):
            return self.send_error(404, "Attachment not found")
        if not path.is_file():
            return self.send_error(404, "Attachment not found")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            file = path.open("rb")
            size = path.stat().st_size
        except OSError:
            return self.send_error(404, "Attachment not found")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(path.name)}")
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        try:
            self.copyfile(file, self.wfile)
        finally:
            file.close()

    def serve_archive_file(self, params):
        archive_dir = INDEX.archive_dir
        if archive_dir is None:
            return self.send_error(409, "Choose an archive first")
        path = resolve_archive_file(archive_dir, params.get("path", [""])[0])
        if path is None:
            return self.send_error(404, "Archive file not found")
        return self.serve_downloadable_file(path)

    def serve_downloadable_file(self, path: Path):
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            file = path.open("rb")
            size = path.stat().st_size
        except OSError:
            return self.send_error(404, "File not found")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(path.name)}")
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        try:
            self.copyfile(file, self.wfile)
        finally:
            file.close()

    def serve_chat(self, params):
        archive_dir = INDEX.archive_dir
        if archive_dir is None:
            return self.send_error(409, "Choose an archive first")
        filename = unquote(params.get("file", [""])[0])
        candidate = (archive_dir / filename).resolve()
        if candidate.parent != archive_dir or candidate.suffix.lower() != ".html":
            return self.send_error(400, "Invalid conversation")
        try:
            source = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return self.send_error(404)
        source = rewrite_local_attachments(source, archive_dir)
        selected = params.get("message", [""])[0]
        title = html.escape(candidate.stem)
        injected_css = """
<style id="chat-view-style">
html{height:100%;scroll-behavior:smooth;overflow-y:auto!important}body{min-height:100%;max-width:820px;margin:0 auto;padding:88px 20px 40px!important;background:#fff!important;overflow:visible!important}
.message{margin:7px 0!important}.message .sent,.message .received{padding:9px 14px!important;max-width:72%!important;border-radius:20px!important}
.timestamp{font-size:11px!important;opacity:.62}.sender{font-size:12px!important;font-weight:600}.message .sent:has(.attachment),.message .received:has(.attachment){max-width:88%!important}.attachment img,.attachment video{display:block;width:auto;max-width:100%;max-height:72vh;border-radius:14px;object-fit:contain;cursor:zoom-in}
.search-hit>div{outline:4px solid rgba(255,196,0,.55);outline-offset:3px}
#archive-title{position:fixed;z-index:20;top:0;left:0;right:0;height:64px;background:rgba(248,248,248,.88);backdrop-filter:blur(18px);border-bottom:1px solid #ddd;display:flex;align-items:center;justify-content:center;font:600 15px system-ui;color:#111}
@media(prefers-color-scheme:dark){body{background:#000!important}#archive-title{background:rgba(28,28,30,.88);border-color:#333;color:#fff}}
</style><div id="archive-title">__CHAT_TITLE__</div>
<script>
addEventListener('DOMContentLoaded',()=>document.querySelectorAll('.attachment img').forEach(img=>{
  img.loading='lazy';img.decoding='async';
  if(!img.closest('a')){const a=document.createElement('a');a.href=img.src;a.target='_blank';a.rel='noopener';a.title='Open full-size attachment';img.replaceWith(a);a.appendChild(img)}
}))
</script>
""".replace("__CHAT_TITLE__", title)
        source = re.sub(r"<body([^>]*)>", lambda m: m.group(0) + injected_css, source, count=1, flags=re.I)
        if selected.isdigit():
            source = mark_message(source, int(selected))
            script = "<script>addEventListener('load',()=>document.getElementById('selected-message')?.scrollIntoView({block:'center'}))</script>"
            source = BODY_END_RE.sub(script + "</body>", source, count=1)
        data = source.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", "default-src 'self' data: https: file:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src * data: file:; media-src * data: file:")
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description="Browse an imessage-exporter HTML archive")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Chat View is running at {url}\nPress Control-C to stop.")
    if not args.no_open:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
