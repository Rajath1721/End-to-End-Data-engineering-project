"""Crawl public PAI product detail pages into timestamped JSONL snapshots.

The crawler discovers PDP URLs from the public sitemap, checks robots.txt,
uses curl for TLS verification via the host certificate store, and stores the
page's Product JSON-LD as raw JSON alongside a few normalized catalog fields.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://www.paiinternational.in"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
USER_AGENT = "RetailLearningProjectBot/0.1 (public catalog crawl)"
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def fetch(url: str) -> bytes:
    """Fetch one public URL with curl, which uses the host's trusted CA store."""
    if not shutil.which("curl"):
        raise RuntimeError("curl is required for HTTPS access on this machine")
    result = subprocess.run(
        ["curl", "--silent", "--show-error", "--fail", "--location",
         "--max-time", "30", "--max-redirs", "5", "--user-agent", USER_AGENT, url],
        check=True, capture_output=True,
    )
    return result.stdout


def robots_rules(text: str) -> tuple[list[tuple[str, bool]], list[str]]:
    """Read wildcard-group Allow/Disallow paths and Sitemap declarations."""
    applies_to_all = False
    rules: list[tuple[str, bool]] = []
    sitemaps: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key_lower = key.lower()
        if key_lower == "user-agent":
            applies_to_all = value == "*"
        elif key_lower == "sitemap":
            sitemaps.append(value)
        elif applies_to_all and key_lower in {"allow", "disallow"} and value:
            rules.append((value, key_lower == "allow"))
    return rules, sitemaps


def permitted(url: str, rules: list[tuple[str, bool]]) -> bool:
    path = urlparse(url).path or "/"
    matching = [(rule, allowed) for rule, allowed in rules if path.startswith(rule)]
    if not matching:
        return True
    # Standard robots behavior: the most specific matching path wins; Allow
    # wins a tie. PAI's current PDP paths are not disallowed.
    matching.sort(key=lambda item: (len(item[0]), item[1]), reverse=True)
    return matching[0][1]


def discover_pdp_urls(sitemap_url: str, limit: int) -> tuple[list[str], list[tuple[str, bool]]]:
    robots_text = fetch(ROBOTS_URL).decode("utf-8", "replace")
    rules, sitemap_urls = robots_rules(robots_text)
    if not permitted(f"{BASE_URL}/product-details/example", rules):
        raise RuntimeError("robots.txt disallows product detail pages; stopping crawl")

    sitemap_candidates = sitemap_urls or [sitemap_url]
    urls: list[str] = []
    seen: set[str] = set()
    while sitemap_candidates:
        current = sitemap_candidates.pop(0)
        root = ET.fromstring(fetch(current))
        for loc in root.findall("s:sitemap/s:loc", SITEMAP_NS):
            if loc.text:
                sitemap_candidates.append(loc.text.strip())
        for loc in root.findall("s:url/s:loc", SITEMAP_NS):
            candidate = (loc.text or "").strip()
            parsed = urlparse(candidate)
            if (parsed.scheme == "https"
                    and parsed.netloc.lower() in {"paiinternational.in", "www.paiinternational.in"}
                    and parsed.path.startswith("/product-details/")
                    and permitted(candidate, rules)
                    and candidate not in seen):
                seen.add(candidate)
                urls.append(candidate)
        # A positive limit can stop once enough PDPs have been found. For full
        # crawl, pass 0; the default is deliberately a small sample.
        if limit > 0 and len(urls) >= limit:
            break
    return urls[:limit] if limit > 0 else urls, rules


def iter_jsonld_objects(value):
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            yield from graph
    elif isinstance(value, list):
        for item in value:
            yield from iter_jsonld_objects(item)


def get_product_and_breadcrumbs(soup: BeautifulSoup) -> tuple[dict, list[dict]]:
    products: list[dict] = []
    breadcrumbs: list[dict] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for obj in iter_jsonld_objects(parsed):
            kinds = obj.get("@type", [])
            if isinstance(kinds, str):
                kinds = [kinds]
            if "Product" in kinds:
                products.append(obj)
            if "BreadcrumbList" in kinds:
                breadcrumbs.append(obj)
    return (products[0] if products else {}), breadcrumbs


def meta_content(soup: BeautifulSoup, *, name: str | None = None,
                 prop: str | None = None) -> str | None:
    selector = {"name": name} if name else {"property": prop}
    node = soup.find("meta", attrs=selector)
    return node.get("content", "").strip() or None if node else None


def category_from_breadcrumbs(breadcrumbs: list[dict], product_name: str | None) -> str | None:
    for breadcrumb in breadcrumbs:
        items = breadcrumb.get("itemListElement", [])
        names = []
        for item in items:
            if isinstance(item, dict):
                name = item.get("name")
                if not name and isinstance(item.get("item"), dict):
                    name = item["item"].get("name")
                if name:
                    names.append(str(name).strip())
        names = [n for n in names if n.lower() not in {"home", (product_name or "").lower()}]
        if names:
            return names[-1]
    return None


def normalize_product(url: str, html: bytes, crawl_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    product, breadcrumbs = get_product_and_breadcrumbs(soup)
    offers = product.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    name = product.get("name")
    if not name:
        name = meta_content(soup, prop="og:title")
    if not name and soup.title:
        name = soup.title.string
    image = product.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    description = product.get("description") or meta_content(soup, prop="og:description") or meta_content(soup, name="description")
    return {
        "crawl_id": crawl_id,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": url,
        "product_name": name,
        "brand": brand,
        "sku": product.get("sku"),
        "category": product.get("category") or category_from_breadcrumbs(breadcrumbs, name),
        "listed_price": offers.get("price"),
        "currency": offers.get("priceCurrency"),
        "availability": offers.get("availability"),
        "image_url": image,
        "description": description,
        "raw_product_jsonld": product or None,
        "raw_breadcrumb_jsonld": breadcrumbs or None,
    }


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(limit: int = 25, delay_seconds: float = 1.0) -> Path:
    if delay_seconds < 0.5:
        raise ValueError("Use at least a 0.5 second delay between PDP requests")
    urls, _ = discover_pdp_urls(SITEMAP_URL, limit)
    crawl_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "data" / "landing" / "pdp" / f"run_{crawl_id}"
    out_dir.mkdir(parents=True, exist_ok=False)
    products: list[dict] = []
    errors: list[dict] = []
    for index, url in enumerate(urls):
        if index:
            time.sleep(delay_seconds)
        try:
            html = fetch(url)
            product = normalize_product(url, html, crawl_id)
            if not product.get("raw_product_jsonld"):
                errors.append({"source_url": url, "error": "no Product JSON-LD found"})
            else:
                products.append(product)
        except Exception as error:  # record a bad page but continue the crawl
            errors.append({"source_url": url, "error": f"{type(error).__name__}: {error}"})

    write_jsonl(out_dir / "products.jsonl", products)
    write_jsonl(out_dir / "errors.jsonl", errors)
    summary = {
        "crawl_id": crawl_id,
        "started_from": SITEMAP_URL,
        "pages_selected": len(urls),
        "products_collected": len(products),
        "errors": len(errors),
        "delay_seconds": delay_seconds,
        "all_products_mode": limit == 0,
        "note": "PDP catalog data only; listed availability is not store-level inventory or sales data.",
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"PDP pages selected: {len(urls)}")
    print(f"Products collected: {len(products)}; pages with errors: {len(errors)}")
    print(f"JSON snapshots: {out_dir / 'products.jsonl'}")
    return out_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl PAI public product detail pages into JSON snapshots")
    parser.add_argument("--limit", type=int, default=25,
                        help="maximum PDPs to crawl (default 25; use 0 for all sitemap PDPs)")
    parser.add_argument("--delay-seconds", type=float, default=1.0,
                        help="minimum pause between PDPs (must be at least 0.5 seconds)")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be 0 or greater")
    run(args.limit, args.delay_seconds)
