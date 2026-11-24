import json
import ipaddress
import socket
from urllib.parse import urljoin, urlparse
from http.server import BaseHTTPRequestHandler

import requests
from bs4 import BeautifulSoup

TIMEOUT = 12
MAX_PAGE_BYTES = 2_500_000
MAX_IMAGES = 80
USER_AGENT = "Mozilla/5.0 (compatible; ImageExtractorPro/1.0)"

def is_public_url(url):
    """Allow only public HTTP(S) hosts; reject local/private IP destinations."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, None)]
        return bool(addresses) and all(addr.is_global for addr in addresses)
    except Exception:
        return False

def fetch_page(url):
    current = url
    for _ in range(5):
        if not is_public_url(current):
            raise ValueError("Only public HTTP/HTTPS URLs are allowed.")
        response = requests.get(
            current,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            allow_redirects=False,
            stream=True,
        )
        if response.is_redirect:
            target = response.headers.get("Location")
            response.close()
            if not target:
                raise ValueError("The site redirected without a destination.")
            current = urljoin(current, target)
            continue
        if response.status_code >= 400:
            code = response.status_code
            response.close()
            raise ValueError(f"The website returned HTTP {code}.")
        content_type = response.headers.get("Content-Type", "").lower()
        chunks, total = [], 0
        for chunk in response.iter_content(65536):
            total += len(chunk)
            if total > MAX_PAGE_BYTES:
                response.close()
                raise ValueError("The webpage is too large to inspect.")
            chunks.append(chunk)
        final_url = response.url
        response.close()
        return final_url, content_type, b"".join(chunks)
    raise ValueError("Too many redirects.")

def extract_images(url):
    final_url, content_type, body = fetch_page(url)
    if content_type.startswith("image/"):
        return [{"url": final_url, "source": "direct image"}]

    soup = BeautifulSoup(body, "html.parser")
    found, seen = [], set()

    def add(raw, source):
        if not raw or len(found) >= MAX_IMAGES:
            return
        candidate = urljoin(final_url, raw.strip())
        if candidate in seen or not is_public_url(candidate):
            return
        seen.add(candidate)
        found.append({"url": candidate, "source": source})

    # Social sharing / preview images first.
    meta_keys = ("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    for key in meta_keys:
        for tag in soup.find_all("meta"):
            prop = (tag.get("property") or tag.get("name") or "").lower()
            if prop == key:
                add(tag.get("content"), key)

    # Standard image elements and responsive image sets.
    for tag in soup.find_all("img"):
        add(tag.get("src"), "img src")
        add(tag.get("data-src"), "lazy image")
        add(tag.get("data-original"), "original image")
        for attr in ("srcset", "data-srcset"):
            srcset = tag.get(attr)
            if srcset:
                for entry in srcset.split(","):
                    candidate = entry.strip().split(" ")[0]
                    add(candidate, attr)
                    if len(found) >= MAX_IMAGES:
                        break
        if len(found) >= MAX_IMAGES:
            break

    # <picture><source srcset=...> and link rel=image_src
    for tag in soup.find_all("source"):
        srcset = tag.get("srcset")
        if srcset:
            for entry in srcset.split(","):
                add(entry.strip().split(" ")[0], "picture source")
                if len(found) >= MAX_IMAGES:
                    break
    for tag in soup.find_all("link"):
        rel = " ".join(tag.get("rel", [])).lower()
        if "image_src" in rel:
            add(tag.get("href"), "image_src")

    return found[:MAX_IMAGES]

class handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json(200, {"ok": True})

    def do_GET(self):
        self.send_json(405, {"error": "Send a POST request with a webpage URL."})

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 12000:
                self.send_json(400, {"error": "Invalid request size."})
                return
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            url = str(payload.get("url", "")).strip()
            if not is_public_url(url):
                self.send_json(400, {"error": "Enter a valid public HTTP/HTTPS URL."})
                return
            images = extract_images(url)
            self.send_json(200, {"ok": True, "images": images})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except requests.RequestException:
            self.send_json(502, {"error": "Could not fetch this page. The website may block automated requests."})
        except Exception:
            self.send_json(500, {"error": "Unexpected error. Check the Vercel function logs."})
