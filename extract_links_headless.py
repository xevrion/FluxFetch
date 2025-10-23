"""
Generic Selenium extractor for JS-rendered pages with a #plaintext container.

USE ONLY for content you own or have permission to scrape.
"""

import re
import time
from typing import List
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def extract_links_from_text(text: str) -> List[str]:
    # Simple regex to extract http/https URLs
    urls = re.findall(r'https?://[^\s\'"<>]+', text)
    # de-duplicate while preserving order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def load_and_get_plaintext(url: str, timeout_sec: int = 15) -> str:
    """Load `url` headlessly and return innerText/innerHTML of #plaintext (or textarea#message)."""
    opts = Options()
    opts.add_argument("--headless=new")   # headless mode (modern)
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # optional: make it faster
    opts.add_argument("--disable-gpu")
    # create driver (webdriver-manager handles driver binary)
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
    try:
        driver.set_page_load_timeout(timeout_sec)
        driver.get(url)
    except Exception as e:
        # page load timeouts / network errors
        print("Page load issue:", e)

    # Wait loop: poll for #plaintext to be non-empty, or textarea#message to be non-empty
    deadline = time.time() + timeout_sec
    plaintext_html = ""
    while time.time() < deadline:
        try:
            # try element that the site uses for final rendered content
            el = driver.find_element(By.CSS_SELECTOR, "#plaintext")
            txt = el.get_attribute("innerHTML") or el.get_attribute("innerText") or ""
            if txt and txt.strip():
                plaintext_html = txt
                break
        except NoSuchElementException:
            pass
        # fallback: some pages put content into textarea#message (encrypted payload may still be here)
        try:
            ta = driver.find_element(By.CSS_SELECTOR, "textarea#message")
            ta_text = ta.get_attribute("value") or ta.get_attribute("textContent") or ""
            if ta_text and ta_text.strip() and not plaintext_html:
                # NOTE: this textarea may contain encrypted blob; not plaintext. We return it for debug.
                plaintext_html = ta_text
                # Do not break here — prefer #plaintext if it appears later.
        except NoSuchElementException:
            pass

        time.sleep(0.5)

    # final try: if #plaintext not filled, try reading document.body.innerText
    if not plaintext_html:
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            plaintext_html = body.get_attribute("innerText") or ""
        except Exception:
            plaintext_html = ""

    driver.quit()
    return plaintext_html

def extract_links_from_page(url: str, verbose: bool = True) -> List[str]:
    txt = load_and_get_plaintext(url, timeout_sec=20)
    if verbose:
        print("---- Extracted raw text/html snippet (first 800 chars) ----")
        print(txt[:800].replace("\n", "\\n"))
        print("-----------------------------------------------------------")
    # Parse with BeautifulSoup to get cleaner text if it's HTML
    soup = BeautifulSoup(txt, "html.parser")
    # get condensed text
    candidate_text = soup.get_text(separator="\n")
    # Extract links via regex
    links = extract_links_from_text(candidate_text)
    if verbose:
        print(f"Found {len(links)} links.")
    return links

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extract_links_headless.py <url>")
        sys.exit(1)
    url = sys.argv[1]
    print("NOTE: Run this only on pages you have permission to scrape.")
    links = extract_links_from_page(url)

    # Save links to links.txt
    with open("links.txt", "w") as f:
        for u in links:
            f.write(u + "\n")

    print(f"{len(links)} links saved to links.txt")

    # Optional: print links to terminal
    for i, u in enumerate(links, 1):
        print(f"{i:02d}. {u}")