# Chat View

A private, local browser for this `imessage-exporter` HTML archive. It adds an iMessage-like conversation list and full-archive search without modifying the exported files or sending data anywhere.

## Start

Double-click `Start Chat View.command`, or run:

```sh
python3 chat-view/server.py
```

Then open <http://127.0.0.1:8765>. Press Control-C in Terminal to stop it.

Search supports multiple words (all words must occur in the same message). Use Command-K to focus search and Escape to clear it.

## Notes

- The search index is rebuilt in memory on startup; the archive remains read-only.
- Linked web previews may contact their original websites when displayed.
- Attachments exported as absolute paths require the original attachment files to remain at those paths.

## Update the archive

Double-click `Update Archive.command`. It safely exports into a staging directory first, then replaces only the top-level conversation HTML files. The `chat-view` interface is left intact.

If Chat View is running, its search index is refreshed automatically. Otherwise, start it normally after the update. macOS may require Full Disk Access for Terminal so `imessage-exporter` can read `~/Library/Messages/chat.db`.
