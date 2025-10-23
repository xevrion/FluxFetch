# FluxFetch

**FluxFetch** is a lightweight downloader utility to fetch and manage large file downloads from FitGirl repacks links. It uses `aria2` for fast, multi-connection downloads with a friendly PyQt6 GUI fallback.

---

## Requirements

- Python 3.10+
- Python packages: `requests`, `PyQt6`
- `aria2` (optional but recommended for fast downloads)

Install Python dependencies:

# FluxFetch

**FluxFetch** is a lightweight downloader utility to fetch and manage large file downloads from FitGirl repacks links. It uses `aria2` for fast, multi-connection downloads with a friendly PyQt6 GUI fallback.

---

## Requirements

- Python 3.10+
- Python packages: `requests`, `PyQt6`
- `aria2` (optional but recommended for fast downloads)

## Installation

Install Python dependencies:

```bash
pip install requests PyQt6
```

Install aria2 (Linux/Debian example):

```bash
sudo apt update
sudo apt install aria2
```

## Setup aria2 (RPC mode)

Start aria2 in RPC mode so the script can talk to it:

```bash
aria2c --enable-rpc \
       --rpc-listen-all=false \
       --rpc-allow-origin-all \
       --max-connection-per-server=8 \
       --split=8 \
       --continue=true \
       --rpc-listen-port=6800
```

Leave this terminal open. The GUI will automatically detect and use aria2. If aria2 is not running, the script falls back to the internal downloader.

## Usage

### Extract download links

Use the `extract_links_headless.py` script with the FitGirl paste URL to generate `links.txt`:

```bash
python extract_links_headless.py "https://paste.fitgirl-repacks.site/your_paste_url_here"
```

This will create a `links.txt` file containing all downloadable URLs.

### Open the downloader UI

Run the main GUI:

```bash
python main.py
```

- Click "Open .txt with URLs" and select `links.txt`.
- Choose your download directory.
- Adjust parallel downloads and connections per file if needed.
- Click "Start Download" (aria2 will be used if available).

The GUI will show progress and status, and allows you to stop or cancel downloads.
