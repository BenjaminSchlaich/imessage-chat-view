# Chat View

Chat View is a private, local browser for HTML archives created by
[`imessage-exporter`](https://github.com/ReagentX/imessage-exporter). It provides
an iMessage-style conversation list and full-archive search without modifying
the exported files or uploading messages anywhere.

## Use the macOS app

1. Double-click the `Chat View` executable.
2. Your browser opens the Chat View welcome screen.
3. Click **Choose archive folder…** and select the folder containing the
   exported conversation `.html` files.
4. After confirming the Finder dialog, the chat interface opens in the same
   browser tab.

Keep the Terminal window opened by the executable running while using Chat
View. Press Control-C in that window to stop the local server.

The executable is self-contained; Python and third-party packages are not
required on the Mac where it is used. Because unsigned local executables can be
blocked by Gatekeeper, the first launch may require Control-clicking the file,
choosing **Open**, and confirming the prompt.

## Run from source

Python 3.10 or newer is sufficient; no runtime dependencies are required.

```sh
python3 server.py
```

Then click **Choose archive folder…** in the browser. Use `--port NUMBER` to
select another local port or `--no-open` to prevent automatic browser launch.

## Build the executable

Install PyInstaller into your preferred development environment, then run:

```sh
python3 -m pip install pyinstaller
./build.sh
```

The single-file executable is written to `dist/Chat View`. Builds are specific
to the macOS CPU architecture on which they are created.

## Usage notes

- Search supports multiple words; all words must occur in the same message.
- Command-K focuses search and Escape clears it.
- The search index is rebuilt in memory after selecting an archive.
- The selected archive remains read-only.
- Attachments copied into an archive with the `clone`, `basic`, or `full`
  method are displayed and downloadable from inside the selected archive.
- Images and videos are represented by large placeholders and are loaded only
  when clicked, reducing startup work for media-heavy conversations.
- Linked web previews may contact their original websites when displayed.
- Attachments exported as absolute paths require the original files to remain
  under `~/Library/Messages/Attachments`.

## Privacy

Chat View listens only on `127.0.0.1`, so it is accessible from the local Mac.
Messages and the in-memory search index are not sent to a remote service.
