#!/usr/bin/env python3
"""Download all available Lanhu Axure page sources and image assets.

The script is stdlib-only. Cookies are sent only to the fixed lanhuapp.com API
endpoints; Axure source files and images are fetched from the fixed asset host.
Downloaded images are recorded as requiring visual review, never as understood.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html.parser
import json
import os
import re
import sys
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

RESOLVE_API = "https://lanhuapp.com/api/share/url/resolve"
PROJECT_IMAGE_API = "https://lanhuapp.com/api/project/image"
AXURE_FILE_BASE = "https://axure-file.lanhuapp.com/"
COOKIE_FILE = Path.home() / ".codex/lanhu-mcp-bridge/lanhu-mcp-local.env"
TEXT_KEYS = {"text", "richtext", "label", "title", "description", "placeholder", "alt", "alttext", "value", "content"}
IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp")


def _cookie() -> str | None:
    value = os.getenv("LANHU_COOKIE")
    if value:
        return value.strip()
    try:
        lines = COOKIE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if line.strip().startswith("LANHU_COOKIE="):
            value = line.split("=", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            return value or None
    return None


def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
               data: dict[str, Any] | None = None) -> Any:
    request_headers = dict(headers or {})
    request_headers.setdefault("user-agent", "Mozilla/5.0")
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        request_headers.setdefault("content-type", "application/json")
    request = urllib.request.Request(url, headers=request_headers, data=body, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_bytes(url: str) -> tuple[bytes, str | None]:
    request = urllib.request.Request(url, headers={"user-agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get("content-type")


def _extract_short_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    if not query and parsed.fragment and "?" in parsed.fragment:
        query = urllib.parse.parse_qs(parsed.fragment.split("?", 1)[1])
    values = query.get("sid", [])
    if not values:
        raise ValueError("invite url missing sid")
    return values[0]


def _looks_like_invite(url: str) -> bool:
    return "lanhuapp.com/link/" in url and "sid=" in url


def _resolve_invite(url: str, password: str | None, cookie: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"short_id": _extract_short_id(url)}
    if password:
        payload["password"] = password
    headers = {"cookie": cookie} if cookie else None
    return _http_json(RESOLVE_API, method="POST", headers=headers, data=payload)


def _url_params(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    query_string = parsed.query
    if "?" in (parsed.fragment or ""):
        query_string = parsed.fragment.split("?", 1)[1]
    return {key: values[0] for key, values in urllib.parse.parse_qs(query_string).items() if values}


def _metadata(project_id: str, image_id: str, cookie: str | None) -> dict[str, Any]:
    query = urllib.parse.urlencode({"pid": project_id, "image_id": image_id})
    headers = {"referer": "https://lanhuapp.com/web/"}
    if cookie:
        headers["cookie"] = cookie
    return _http_json(f"{PROJECT_IMAGE_API}?{query}", headers=headers)


def _json_url(metadata: dict[str, Any]) -> str:
    versions = (metadata.get("result") or {}).get("versions") or []
    if not versions or not versions[0].get("json_url"):
        raise ValueError("document metadata missing latest json_url")
    return str(versions[0]["json_url"])


def _page_summary(axure: dict[str, Any]) -> dict[str, Any]:
    pages = axure.get("pages") or {}
    return {"page_count": len(pages), "page_names": list(pages.keys()), "sitemap": axure.get("sitemap") or {}}


class _VisibleTextParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden_depth += 1
        for key, value in attrs:
            if key.lower() in {"alt", "title", "placeholder", "aria-label", "value"} and value:
                text = " ".join(value.split())
                if text:
                    self.parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text and not self.hidden_depth:
            self.parts.append(text)


def _text_from_datajs(data: bytes) -> tuple[list[str], str]:
    """Extract strings from known text fields when dataJs is JSON-shaped."""
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        source = data.decode("utf-8", errors="replace")
        pattern = re.compile(r"(?:text|richText|label|title|description|placeholder|altText|value|content)\s*:\s*('(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")", re.IGNORECASE)
        found_js: list[str] = []
        for match in pattern.finditer(source):
            try:
                value = json.loads(match.group(1))
            except json.JSONDecodeError:
                value = match.group(1)[1:-1]
            value = " ".join(value.split())
            if value:
                found_js.append(value)
        return list(dict.fromkeys(found_js)), "heuristic_js_text_fields_scanned_raw_source_saved"
    found: list[str] = []

    def visit(value: Any, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, str(key).lower())
        elif isinstance(value, list):
            for child in value:
                visit(child, parent_key)
        elif isinstance(value, str) and parent_key.replace("_", "") in TEXT_KEYS:
            cleaned = " ".join(value.split())
            if cleaned:
                found.append(cleaned)

    visit(parsed)
    return list(dict.fromkeys(found)), "heuristic_known_text_fields_extracted_raw_source_saved"


def _safe_name(value: str, fallback: str) -> str:
    name = Path(urllib.parse.unquote(value)).name
    name = re.sub(r"[^\w.()\-\u4e00-\u9fff]+", "_", name).strip("._")
    return name[:120] or fallback


def _referenced_images(data: bytes) -> list[str]:
    """Find explicit image files, data URIs, and image-context references."""
    source = data.decode("utf-8", errors="replace")
    extension = "|".join(IMAGE_EXTENSIONS)
    refs = re.findall(r"data:image/(?:png|jpe?g|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=]+", source, re.IGNORECASE)
    refs.extend(re.findall(rf"https?://[^\s\"'<>),;]+?\.(?:{extension})(?:\?[^\s\"'<>),;]*)?", source, re.IGNORECASE))
    refs.extend(re.findall(rf"(?<![A-Za-z0-9:/.])(?:\.\.?/|/)?[\w\u4e00-\u9fff./%-]+\.(?:{extension})(?:\?[^\s\"'<>),;]*)?", source, re.IGNORECASE))
    # Image context allows extension-less signed endpoints; ordinary hrefs are excluded.
    context_patterns = (
        r"<img\b[^>]*?\bsrc\s*=\s*(['\"])(.*?)\1",
        r"\burl\(\s*(['\"]?)(.*?)\1\s*\)",
        r"\bbackground\s*=\s*(['\"])(.*?)\1",
    )
    for pattern in context_patterns:
        refs.extend(match[1] for match in re.findall(pattern, source, re.IGNORECASE | re.DOTALL))
    return list(dict.fromkeys(ref.strip() for ref in refs if ref.strip()))


def _sitemap_audit(axure: dict[str, Any]) -> dict[str, Any]:
    pages = set((axure.get("pages") or {}).keys())
    sitemap = axure.get("sitemap") or {}
    roots = sitemap.get("rootNodes") if isinstance(sitemap, dict) else None
    matched: set[str] = set()
    unmatched_leaves: list[str] = []

    def walk(nodes: Any) -> None:
        if isinstance(nodes, dict):
            nodes = [nodes]
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            children = node.get("children") or node.get("childNodes") or node.get("nodes") or []
            labels = [node.get(key) for key in ("pageName", "page_name", "name", "title", "text")]
            labels = [str(label) for label in labels if isinstance(label, str) and label]
            matched.update(label for label in labels if label in pages)
            if not children:
                unmatched_leaves.extend(label for label in labels if label not in pages)
            else:
                walk(children)

    walk(roots)
    page_missing_from_sitemap = sorted(pages - matched)
    sitemap_only = sorted(set(unmatched_leaves))
    verifiable = bool(matched) and not page_missing_from_sitemap and not sitemap_only
    return {
        "status": "verified" if verifiable else "unresolved",
        "sitemap_page_names_matched": sorted(matched),
        "pages_missing_from_sitemap": page_missing_from_sitemap,
        "sitemap_only_or_unmatched_leaf_names": sitemap_only,
        "reason": None if verifiable else "sitemap format or names did not permit a complete page-name cross-check",
    }


def _referenced_image_url(reference: str) -> str | None:
    parsed = urllib.parse.urlparse(reference)
    if parsed.scheme:
        if parsed.scheme != "https" or parsed.hostname != "axure-file.lanhuapp.com":
            return None
        return reference
    return _asset_url(reference)


def _write_inline_image(output_dir: Path, relative: str, reference: str) -> dict[str, Any]:
    record: dict[str, Any] = {"kind": "inline_data_image", "status": "unavailable", "local_path": None}
    try:
        header, encoded = reference.split(",", 1)
        content = base64.b64decode(encoded, validate=True)
        match = re.search(r"data:image/([\w+.-]+);base64", header, re.IGNORECASE)
        ext = match.group(1).replace("jpeg", "jpg").replace("svg+xml", "svg") if match else "img"
        path = output_dir / f"{relative}.{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        record.update(status="downloaded", local_path=str(path), byte_count=len(content), content_type=f"image/{ext}")
    except (ValueError, OSError) as exc:
        record["error"] = str(exc)
    return record


def _write_source(output_dir: Path, relative: str, url: str, kind: str) -> dict[str, Any]:
    record: dict[str, Any] = {"kind": kind, "source_url": url, "status": "unavailable", "local_path": None}
    try:
        content, content_type = _http_bytes(url)
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        record.update(status="downloaded", local_path=str(path), byte_count=len(content), content_type=content_type)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        record["error"] = str(exc)
    return record


def _asset_url(sign_md5: Any) -> str | None:
    if not isinstance(sign_md5, str) or not sign_md5.strip():
        return None
    # Asset identifiers are path components from the Axure manifest, not URLs.
    sign = sign_md5.strip().lstrip("/")
    if "://" in sign or ".." in Path(sign).parts:
        return None
    return urllib.parse.urljoin(AXURE_FILE_BASE, urllib.parse.quote(sign, safe="/._-"))


def _download_all_pages(axure: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    pages = axure.get("pages") or {}
    result: list[dict[str, Any]] = []
    for index, (page_name, page) in enumerate(pages.items(), start=1):
        page = page if isinstance(page, dict) else {}
        page_dir = output_dir / "pages" / f"{index:03d}_{_safe_name(str(page_name), 'page')}"
        page_record: dict[str, Any] = {"name": page_name, "status": "processed", "sources": [], "images": [], "extracted_text": []}
        discovered_refs: list[str] = []
        for field in ("dataJs", "html"):
            info = page.get(field)
            sign = info.get("sign_md5") if isinstance(info, dict) else None
            url = _asset_url(sign)
            if not url:
                page_record["sources"].append({"kind": field, "status": "unavailable", "reason": "missing_or_invalid_sign_md5"})
                continue
            suffix = Path(str(sign)).suffix or (".js" if field == "dataJs" else ".html")
            source = _write_source(output_dir, str(page_dir.relative_to(output_dir) / f"{field}{suffix}"), url, field)
            page_record["sources"].append(source)
            if source["status"] != "downloaded":
                continue
            raw = Path(source["local_path"]).read_bytes()
            discovered_refs.extend(_referenced_images(raw))
            if field == "dataJs":
                text_items, extraction_status = _text_from_datajs(raw)
                page_record["extracted_text"].extend({"text": text, "source": source["local_path"], "extraction": "dataJs_known_text_field"} for text in text_items)
                page_record["dataJs_text_status"] = extraction_status
            else:
                parser = _VisibleTextParser()
                try:
                    parser.feed(raw.decode("utf-8", errors="replace"))
                    page_record["extracted_text"].extend({"text": text, "source": source["local_path"], "extraction": "html_text_candidate"} for text in dict.fromkeys(parser.parts))
                    page_record["html_text_status"] = "static_text_candidates_extracted_requires_visual_review"
                except Exception as exc:  # Preserve downloaded HTML and expose parse failures.
                    page_record["html_text_status"] = f"raw_source_saved_parse_error:{exc}"

        mapping_sign = page.get("mapping_md5")
        mapping_url = _asset_url(mapping_sign)
        if not mapping_url:
            page_record["mapping_status"] = "unavailable"
            page_record["mapping_reason"] = "missing_or_invalid_mapping_md5"
        else:
            mapping_record = _write_source(output_dir, str(page_dir.relative_to(output_dir) / "mapping.json"), mapping_url, "mapping")
            page_record["mapping_status"] = mapping_record["status"]
            page_record["mapping_source"] = mapping_record
        if mapping_url and page_record["mapping_status"] == "downloaded":
            try:
                mapping = json.loads(Path(mapping_record["local_path"]).read_text(encoding="utf-8"))
                images = mapping.get("images") or {}
                for image_index, (logical_path, image_info) in enumerate(images.items(), start=1):
                    sign = image_info.get("sign_md5") if isinstance(image_info, dict) else None
                    url = _asset_url(sign)
                    image: dict[str, Any] = {"logical_path": logical_path, "sign_md5": sign, "status": "unavailable", "content_interpretation_status": "requires_visual_review"}
                    if url:
                        filename = _safe_name(str(logical_path), f"image_{image_index}")
                        if not Path(filename).suffix and isinstance(sign, str):
                            filename += Path(sign).suffix
                        image.update(_write_source(output_dir, str(page_dir.relative_to(output_dir) / "images" / f"{image_index:04d}_{filename}"), url, "image"))
                        image["content_interpretation_status"] = "requires_visual_review" if image["status"] == "downloaded" else "not_readable_image_unavailable"
                    else:
                        image["reason"] = "missing_or_invalid_sign_md5"
                        image["content_interpretation_status"] = "not_readable_image_unavailable"
                    page_record["images"].append(image)
                page_record["image_count"] = len(images)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
                page_record["mapping_status"] = "unavailable"
                page_record["mapping_error"] = str(exc)
        known_refs = {str(image.get("logical_path")) for image in page_record["images"]}
        known_refs.update(str(image.get("sign_md5")) for image in page_record["images"])
        ref_start = len(page_record["images"])
        for reference in dict.fromkeys(discovered_refs):
            if reference in known_refs:
                continue
            is_inline = reference.lower().startswith("data:image/")
            image_id = "inline-data:" + hashlib.sha256(reference.encode("utf-8")).hexdigest()[:16] if is_inline else reference
            known_refs.add(image_id)
            image: dict[str, Any] = {
                "logical_path": image_id,
                "source_kind": "literal_page_source_reference",
                "status": "unavailable",
                "content_interpretation_status": "not_readable_image_unavailable",
            }
            url = _referenced_image_url(reference)
            if reference.lower().startswith("data:image/"):
                local = _write_inline_image(output_dir, str(page_dir.relative_to(output_dir) / "images" / f"inline_{len(page_record['images']) + 1:04d}"), reference)
                image.update(local)
                image["content_interpretation_status"] = "requires_visual_review" if image["status"] == "downloaded" else "not_readable_image_unavailable"
            elif url:
                filename = _safe_name(reference.split("?", 1)[0], f"referenced_{len(page_record['images']) + 1}")
                image.update(_write_source(output_dir, str(page_dir.relative_to(output_dir) / "images" / f"ref_{len(page_record['images']) + 1:04d}_{filename}"), url, "image_reference"))
                image["source_kind"] = "literal_page_source_reference"
                image["content_interpretation_status"] = "requires_visual_review" if image["status"] == "downloaded" else "not_readable_image_unavailable"
            else:
                image["reason"] = "unsupported_or_external_image_reference_not_fetched"
            page_record["images"].append(image)
        page_record["literal_image_references_count"] = len(page_record["images"]) - ref_start
        page_record["text_count"] = len(page_record["extracted_text"])
        page_record["image_count"] = len(page_record["images"])
        page_record["downloaded_image_count"] = sum(1 for image in page_record["images"] if image["status"] == "downloaded")
        page_record["failed_image_count"] = page_record["image_count"] - page_record["downloaded_image_count"]
        page_record["downloaded_text_source_count"] = sum(1 for source in page_record["sources"] if source["status"] == "downloaded")
        page_record["unparsed_text_source_count"] = sum(
            1 for status_key in ("dataJs_text_status", "html_text_status")
            if page_record.get(status_key, "").startswith(("heuristic_", "raw_source_saved_json_parse_unavailable", "raw_source_saved_parse_error"))
        )
        page_record["static_capture_limit"] = "Only literal assets referenced by fetched sources are enumerable; dynamic interaction states may expose additional content."
        page_record["text_completeness"] = "heuristic_or_static_extraction; inspect raw dataJs and HTML sources"
        page_record["status"] = "incomplete" if page_record["failed_image_count"] or page_record["unparsed_text_source_count"] or page_record.get("mapping_status") != "downloaded" or any(source["status"] != "downloaded" for source in page_record["sources"]) else "sources_downloaded"
        page_manifest_path = page_dir / "page_record.json"
        page_record["page_manifest_path"] = str(page_manifest_path)
        page_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        page_manifest_path.write_text(json.dumps(page_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result.append(page_record)
    return result


def build_output(*, source_url: str, password: str | None, cookie: str | None,
                 output_dir: str | Path | None = None) -> dict[str, Any]:
    resolved_url = source_url
    resolve_response = None
    if _looks_like_invite(source_url):
        resolve_response = _resolve_invite(source_url, password, cookie)
        resolved_url = (resolve_response.get("data") or {}).get("url") or source_url
    params = _url_params(resolved_url)
    project_id = params.get("pid")
    image_id = params.get("image_id") or params.get("docId")
    if not project_id or not image_id:
        raise ValueError("resolved url missing pid/image_id")
    metadata = _metadata(project_id, image_id, cookie)
    axure = _http_json(_json_url(metadata))
    if output_dir is None:
        output_dir = "lanhu-extract-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    pages = _download_all_pages(axure, output_path)
    sitemap_audit = _sitemap_audit(axure)
    output: dict[str, Any] = {
        "source_url": source_url,
        "resolved_url": resolved_url,
        "resolve_response": resolve_response,
        "document_meta": metadata,
        "axure_summary": _page_summary(axure),
        "pages": pages,
        "sitemap_crosscheck": sitemap_audit,
        "coverage": {
            "pages_listed": len(pages),
            "pages_in_axure": len(axure.get("pages") or {}),
            "all_pages_enumerated": len(pages) == len(axure.get("pages") or {}) and sitemap_audit["status"] == "verified",
            "sitemap_crosscheck_status": sitemap_audit["status"],
            "images_enumerated": sum(len(page["images"]) for page in pages),
            "images_discovered": sum(len(page["images"]) for page in pages),
            "images_downloaded": sum(page["downloaded_image_count"] for page in pages),
            "texts_discovered": sum(page["text_count"] for page in pages),
            "unparsed_text_sources": sum(page["unparsed_text_source_count"] for page in pages),
            "unavailable_page_sources": sum(1 for page in pages for item in page["sources"] if item["status"] != "downloaded"),
            "unavailable_images": sum(1 for page in pages for image in page["images"] if image["status"] != "downloaded"),
            "visual_review_required": sum(1 for page in pages for image in page["images"] if image["status"] == "downloaded"),
        },
        "extraction_status": "incomplete" if any(
            source["status"] != "downloaded"
            for page in pages for source in page["sources"]
        ) or any(image["status"] != "downloaded" for page in pages for image in page["images"]) or any(
            page.get("mapping_status") != "downloaded" for page in pages
        ) or any(page["unparsed_text_source_count"] for page in pages) or sitemap_audit["status"] != "verified" else "extraction_complete",
        "reading_status": "pending_visual_review",
        "reading_status_note": "Extraction does not establish image understanding; each downloaded image must be opened and reviewed, with review results recorded before marking read.",
        "output_dir": str(output_path),
        "manifest_path": str(output_path / "manifest.json"),
        "image_semantics_status": "images are downloaded when available; each still requires visual review",
    }
    (output_path / "manifest.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Download all available Lanhu Axure pages, text sources, and images")
    parser.add_argument("--url", required=True, help="Lanhu invite link or direct document URL")
    parser.add_argument("--password", help="Share password if required")
    parser.add_argument("--cookie", help="Lanhu cookie; defaults to LANHU_COOKIE")
    parser.add_argument("--output-dir", help="Directory for page sources, images, and manifest (default: unique timestamped directory)")
    args = parser.parse_args()
    try:
        result = build_output(source_url=args.url, password=args.password, cookie=args.cookie or _cookie(), output_dir=args.output_dir)
    except (ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({
        "manifest_path": result["manifest_path"],
        "coverage": result["coverage"],
        "extraction_status": result["extraction_status"],
        "reading_status": result["reading_status"],
    }, ensure_ascii=False, indent=2))
    return 2 if result["extraction_status"] != "extraction_complete" else 0


if __name__ == "__main__":
    sys.exit(main())
