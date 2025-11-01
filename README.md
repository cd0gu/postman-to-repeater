# Postman2Repeater

**Postman2Repeater** is a Jython-based Burp Suite extension that imports Postman Collection (v2.x) and Environment JSON files, resolves `{{variables}}`, and sends requests directly to Burp's Repeater (one tab per request).

## Features
- Load Postman collection (.json) and optional environment (.json)
- Resolves `{{variable}}` using environment → collection variable precedence
- Supports `raw` and `urlencoded` bodies; best-effort `formdata`
- Sends single or all requests to Repeater
- Uses Burp `helpers.buildHttpMessage` for robust header/body handling

## Files
- `postman2repeater.py` — Burp extension (Jython 2.7). **Copy this file from the canvas** or from the project root if you added it.
- `examples/` — small example collection and environment JSONs
- `docs/INSTALL.md` — installation instructions

## Installation (local)
1. Download Jython standalone (e.g., `jython-standalone-2.7.3.jar`) and note its path.
2. Copy `postman2repeater.py` into a local folder.
3. Open **Burp Suite** → Extender → Options → **Python Environment** → point to the Jython jar.
4. Extender → Extensions → Add → Extension type: **Python** → choose `postman2repeater.py`.
5. Open the new tab **Postman2Repeater** in Burp, load collection & environment, and send requests to Repeater.

## Usage
1. Click **Load Collection...** and pick a Postman collection JSON.
2. (Optional) Click **Load Environment...** and pick a Postman environment JSON.
3. Select a row from the request table and click **Send Selected to Repeater** or click **Send All to Repeater**.

## Tips
- If your collection uses auth (Bearer / API key), add the header in Postman or in the collection-level variables — future versions may auto-apply auth.
- For binary `form-data` with file attachments, behavior is best-effort. Consider using small test values or the manual Repeater tab for highly specific multipart tests.

## Contributing
PRs welcome. If you add features (auth handling, full multipart, throttling), open an issue first describing expected UX.

## License
MIT
