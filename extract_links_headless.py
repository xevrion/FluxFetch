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
    urls = re.findall(r'https?://[^\s\'"<>]+', text)
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def load_and_get_plaintext(url: str, timeout_sec: int = 15) -> str:
    opts = Options()
    opts.add_argument("--headless=new")   # headless mode (modern)
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
    try:
        driver.set_page_load_timeout(timeout_sec)
        driver.get(url)
    except Exception as e:
        print("Page load issue:", e)

    deadline = time.time() + timeout_sec
    plaintext_html = ""
    while time.time() < deadline:
        try:
            el = driver.find_element(By.CSS_SELECTOR, "#plaintext")
            txt = el.get_attribute("innerHTML") or el.get_attribute("innerText") or ""
            if txt and txt.strip():
                plaintext_html = txt
                break
        except NoSuchElementException:
            pass
        try:
            ta = driver.find_element(By.CSS_SELECTOR, "textarea#message")
            ta_text = ta.get_attribute("value") or ta.get_attribute("textContent") or ""
            if ta_text and ta_text.strip() and not plaintext_html:
                plaintext_html = ta_text
        except NoSuchElementException:
            pass

        time.sleep(0.5)

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
    soup = BeautifulSoup(txt, "html.parser")
    candidate_text = soup.get_text(separator="\n")
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

    with open("links.txt", "w") as f:
        for u in links:
            f.write(u + "\n")

    print(f"{len(links)} links saved to links.txt")

    for i, u in enumerate(links, 1):
        print(f"{i:02d}. {u}")