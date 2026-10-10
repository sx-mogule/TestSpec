import json
import io
import unittest
from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "direct_extract_axure.py"
spec = spec_from_file_location("direct_extract_axure", SCRIPT)
extractor = module_from_spec(spec)
spec.loader.exec_module(extractor)


class TestDirectExtractAxureCookie(unittest.TestCase):
    def test_cookie_is_sent_only_to_lanhu_apis(self):
        requests = []

        def fake_http(url, **kwargs):
            requests.append((url, kwargs.get("headers") or {}))
            if url.startswith(extractor.RESOLVE_API):
                return {"data": {"url": "https://lanhuapp.com/web/#/item?pid=p&docId=d"}}
            if url.startswith(extractor.PROJECT_IMAGE_API):
                return {"result": {"versions": [{"json_url": "https://axure-file.lanhuapp.com/doc.json"}]}}
            return {"pages": {}}

        def fake_bytes(url):
            raise AssertionError("no assets should be requested for an empty document")

        with TemporaryDirectory() as directory, \
             patch.object(extractor, "_http_json", side_effect=fake_http), \
             patch.object(extractor, "_http_bytes", side_effect=fake_bytes):
            output = extractor.build_output(
                source_url="https://lanhuapp.com/link/#/invite?sid=s",
                password=None,
                cookie="session=example-only",
                output_dir=directory,
            )
            self.assertEqual(output["coverage"]["pages_listed"], 0)
            self.assertEqual(requests[0][1]["cookie"], "session=example-only")
            self.assertEqual(requests[1][1]["cookie"], "session=example-only")
            self.assertNotIn("session=example-only", Path(output["manifest_path"]).read_text())

    def test_cookie_file_and_environment_override(self):
        with TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "lanhu-mcp-local.env"
            cookie_file.write_text("LANHU_COOKIE='session=from-file; flag=1'\n", encoding="utf-8")
            with patch.object(extractor, "COOKIE_FILE", cookie_file), patch.dict("os.environ", {}, clear=True):
                self.assertEqual(extractor._cookie(), "session=from-file; flag=1")
                with patch.dict("os.environ", {"LANHU_COOKIE": "session=from-env"}):
                    self.assertEqual(extractor._cookie(), "session=from-env")

    def test_all_pages_text_and_images_are_manifested_and_downloaded(self):
        axure = {
            "pages": {
                "overview.html": {
                    "dataJs": {"sign_md5": "page1.js"},
                    "html": {"sign_md5": "page1.html"},
                    "mapping_md5": "map1.json",
                },
                "details.html": {
                    "dataJs": {"sign_md5": "page2.js"},
                    "html": {"sign_md5": "page2.html"},
                    "mapping_md5": "map2.json",
                },
            },
            "sitemap": {"rootNodes": [{"name": "Pages", "children": [{"name": "overview.html"}, {"name": "details.html"}]}]},
        }
        docs = {
            "https://axure-file.lanhuapp.com/doc.json": json.dumps(axure).encode(),
            "https://axure-file.lanhuapp.com/page1.js": json.dumps({"widget": {"text": "第一页文字"}}).encode(),
            "https://axure-file.lanhuapp.com/page1.html": "<html><body>第一页可见文字<div style='display:none'>隐藏候选文字</div><img src='extra.png'><div style=\"background:url(data:image/png;base64,aW1hZ2U=)\"></div><img src='https://external.invalid/x.png'></body></html>".encode(),
            "https://axure-file.lanhuapp.com/map1.json": json.dumps({"images": {
                "images/a.png": {"sign_md5": "a.png"},
                "images/b.png": {"sign_md5": "b.png"},
            }}).encode(),
            "https://axure-file.lanhuapp.com/page2.js": json.dumps({"widget": {"text": "第二页文字"}}).encode(),
            "https://axure-file.lanhuapp.com/page2.html": "<html><body>第二页可见文字</body></html>".encode(),
            "https://axure-file.lanhuapp.com/map2.json": json.dumps({"images": {
                "images/c.png": {"sign_md5": "c.png"},
            }}).encode(),
        }
        for name in ("a.png", "b.png", "c.png", "extra.png"):
            docs[f"https://axure-file.lanhuapp.com/{name}"] = b"image-bytes-" + name.encode()

        with TemporaryDirectory() as directory, \
             patch.object(extractor, "_metadata", return_value={"result": {"versions": [{"json_url": "https://axure-file.lanhuapp.com/doc.json"}]}}), \
             patch.object(extractor, "_http_json", return_value=axure), \
             patch.object(extractor, "_http_bytes", side_effect=lambda url: (docs[url], "application/octet-stream")):
            output = extractor.build_output(
                source_url="https://lanhuapp.com/web/#/item?pid=p&docId=d",
                password=None,
                cookie=None,
                output_dir=directory,
            )
            self.assertEqual(output["coverage"]["pages_in_axure"], 2)
            self.assertTrue(output["coverage"]["all_pages_enumerated"])
            self.assertEqual([page["name"] for page in output["pages"]], ["overview.html", "details.html"])
            self.assertEqual([page["image_count"] for page in output["pages"]], [5, 1])
            self.assertEqual([page["text_count"] for page in output["pages"]], [3, 2])
            self.assertEqual(output["pages"][0]["html_text_status"], "static_text_candidates_extracted_requires_visual_review")
            hidden_candidate = next(item for item in output["pages"][0]["extracted_text"] if item["text"] == "隐藏候选文字")
            self.assertEqual(hidden_candidate["extraction"], "html_text_candidate")
            self.assertEqual(output["coverage"]["images_enumerated"], 6)
            self.assertEqual(output["coverage"]["images_downloaded"], 5)
            self.assertEqual(output["extraction_status"], "incomplete")
            self.assertEqual(output["reading_status"], "pending_visual_review")
            self.assertTrue(all(image["content_interpretation_status"] == "requires_visual_review" for page in output["pages"] for image in page["images"] if image["status"] == "downloaded"))
            for page in output["pages"]:
                self.assertTrue(all(Path(source["local_path"]).is_file() for source in page["sources"]))
                for image in page["images"]:
                    if image["status"] == "downloaded":
                        self.assertTrue(Path(image["local_path"]).is_file())
                    else:
                        self.assertIn("unsupported_or_external_image_reference_not_fetched", image.get("reason", ""))
            persisted = json.loads(Path(output["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(persisted["coverage"]["images_enumerated"], 6)
            inline = next(image for image in output["pages"][0]["images"] if image.get("kind") == "inline_data_image")
            self.assertRegex(inline["logical_path"], r"^inline-data:[a-f0-9]{16}$")
            self.assertNotIn("data:image", Path(output["manifest_path"]).read_text(encoding="utf-8"))

    def test_failed_download_is_marked_incomplete_not_success(self):
        axure = {"pages": {"one.html": {"dataJs": {"sign_md5": "bad.js"}, "html": {"sign_md5": "ok.html"}, "mapping_md5": "map.json"}}}
        docs = {
            "https://axure-file.lanhuapp.com/doc.json": json.dumps(axure).encode(),
            "https://axure-file.lanhuapp.com/ok.html": b"<p>Visible</p>",
            "https://axure-file.lanhuapp.com/map.json": json.dumps({"images": {"missing.png": {"sign_md5": "missing.png"}}}).encode(),
        }

        def fake_bytes(url):
            if url.endswith("bad.js") or url.endswith("missing.png"):
                raise OSError("fixture download failure")
            return docs[url], "application/octet-stream"

        with TemporaryDirectory() as directory, \
             patch.object(extractor, "_metadata", return_value={"result": {"versions": [{"json_url": "https://axure-file.lanhuapp.com/doc.json"}]}}), \
             patch.object(extractor, "_http_json", return_value=axure), \
             patch.object(extractor, "_http_bytes", side_effect=fake_bytes):
            output = extractor.build_output(
                source_url="https://lanhuapp.com/web/#/item?pid=p&docId=d",
                password=None,
                cookie=None,
                output_dir=directory,
            )
        self.assertEqual(output["extraction_status"], "incomplete")
        self.assertEqual(output["coverage"]["unavailable_images"], 1)
        self.assertEqual(output["pages"][0]["failed_image_count"], 1)
        self.assertEqual(output["reading_status"], "pending_visual_review")

    def test_page_source_images_survive_missing_mapping(self):
        axure = {"pages": {"one.html": {"dataJs": {"sign_md5": "one.js"}, "html": {"sign_md5": "one.html"}}}}
        docs = {
            "https://axure-file.lanhuapp.com/one.js": b"var data = {};",
            "https://axure-file.lanhuapp.com/one.html": b"<img src='only-in-html.png'>",
            "https://axure-file.lanhuapp.com/only-in-html.png": b"image-bytes",
        }
        with TemporaryDirectory() as directory, patch.object(
            extractor, "_http_bytes", side_effect=lambda url: (docs[url], "application/octet-stream")
        ):
            pages = extractor._download_all_pages(axure, Path(directory))
            self.assertEqual(pages[0]["mapping_status"], "unavailable")
            self.assertEqual(pages[0]["image_count"], 1)
            self.assertEqual(pages[0]["images"][0]["status"], "downloaded")
            self.assertTrue(Path(pages[0]["images"][0]["local_path"]).is_file())

    def test_image_reference_parser_excludes_regular_links(self):
        source = b"""<a href='https://docs.example/help.html'>help</a>
          <a href='https://docs.example/account'>account</a>
          <img src='https://cdn.example/signed?id=1'>
          <div style=\"background-image:url('/images/bg.webp')\"></div>"""
        refs = extractor._referenced_images(source)
        self.assertNotIn("https://docs.example/help.html", refs)
        self.assertNotIn("https://docs.example/account", refs)
        self.assertIn("https://cdn.example/signed?id=1", refs)
        self.assertIn("/images/bg.webp", refs)

    def test_datajs_text_extraction_is_explicitly_heuristic_and_sitemap_gap_blocks_complete(self):
        found, status = extractor._text_from_datajs(b"var data={widget:{text:'visible'}};")
        self.assertEqual(found, ["visible"])
        self.assertTrue(status.startswith("heuristic_"))
        audit = extractor._sitemap_audit({
            "pages": {"one.html": {}, "two.html": {}},
            "sitemap": {"rootNodes": [{"name": "group", "children": [{"name": "one.html"}, {"name": "orphan.html"}]}]},
        })
        self.assertEqual(audit["status"], "unresolved")
        self.assertEqual(audit["pages_missing_from_sitemap"], ["two.html"])
        self.assertEqual(audit["sitemap_only_or_unmatched_leaf_names"], ["orphan.html"])

    def test_cli_prints_summary_not_full_manifest(self):
        result = {
            "manifest_path": "/tmp/manifest.json",
            "coverage": {"pages_listed": 1, "images_downloaded": 2},
            "extraction_status": "incomplete",
            "reading_status": "pending_visual_review",
            "pages": [{"extracted_text": ["large body"]}],
        }
        capture = io.StringIO()
        with patch.object(extractor.sys, "argv", ["direct_extract_axure.py", "--url", "https://lanhuapp.com/web/#/item?pid=p&docId=d"]), \
             patch.object(extractor, "build_output", return_value=result), redirect_stdout(capture):
            self.assertEqual(extractor.main(), 2)
        printed = json.loads(capture.getvalue())
        self.assertEqual(set(printed), {"manifest_path", "coverage", "extraction_status", "reading_status"})
        self.assertNotIn("pages", printed)

    def test_cli_returns_zero_when_extraction_is_complete_even_if_visual_review_is_pending(self):
        result = {
            "manifest_path": "/tmp/manifest.json",
            "coverage": {"pages_listed": 1},
            "extraction_status": "extraction_complete",
            "reading_status": "pending_visual_review",
        }
        capture = io.StringIO()
        with patch.object(extractor.sys, "argv", ["direct_extract_axure.py", "--url", "https://lanhuapp.com/web/#/item?pid=p&docId=d"]), \
             patch.object(extractor, "build_output", return_value=result), redirect_stdout(capture):
            self.assertEqual(extractor.main(), 0)
        self.assertEqual(json.loads(capture.getvalue())["reading_status"], "pending_visual_review")


if __name__ == "__main__":
    unittest.main()
