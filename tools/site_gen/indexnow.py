"""Tell IndexNow search engines (Yandex, Bing) which site pages changed.

Run AFTER the site is uploaded:

    py -X utf8 tools/site_gen/indexnow.py                 # every URL from sitemap.xml
    py -X utf8 tools/site_gen/indexnow.py reestr.html blog.html
    py -X utf8 tools/site_gen/indexnow.py --dry-run

The key is the name of the 32-hex ``<key>.txt`` file in the site root; that file
must already be uploaded, otherwise the engines reject the request.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE_DIR = Path(r"D:\Project\public_html")
HOST = "normaot.ru"
ENDPOINTS = ("https://yandex.com/indexnow", "https://api.indexnow.org/indexnow")


def find_key() -> str:
    keys = [p.stem for p in SITE_DIR.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem)]
    if len(keys) != 1:
        raise SystemExit("Expected exactly one <32-hex>.txt key file in %s, found %d" % (SITE_DIR, len(keys)))
    return keys[0]


def sitemap_urls() -> list:
    text = (SITE_DIR / "sitemap.xml").read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", text)


def main(argv: list) -> int:
    dry = "--dry-run" in argv
    pages = [a for a in argv if not a.startswith("--")]
    urls = ["https://%s/%s" % (HOST, p.lstrip("/")) for p in pages] if pages else sitemap_urls()
    key = find_key()
    payload = json.dumps({
        "host": HOST,
        "key": key,
        "keyLocation": "https://%s/%s.txt" % (HOST, key),
        "urlList": urls,
    }).encode("utf-8")
    print("%d URL(s), key file %s.txt" % (len(urls), key))
    if dry:
        print("\n".join(urls))
        return 0
    failed = 0
    for endpoint in ENDPOINTS:
        req = urllib.request.Request(
            endpoint, data=payload, headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print("%s -> HTTP %s" % (endpoint, resp.status))
        except urllib.error.HTTPError as e:
            failed += 1
            print("%s -> HTTP %s %s" % (endpoint, e.code, e.reason))
        except OSError as e:
            failed += 1
            print("%s -> %s" % (endpoint, type(e).__name__))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
