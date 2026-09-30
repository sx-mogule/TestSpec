#!/usr/bin/env python3
"""
将 Markdown 测试用例文件转换为符合 TestSpec SOP / XMind 8 规范的 .xmind 思维导图文件。
严格遵循拓扑结构：
根节点 (项目用例集)
  -> 模块
    -> 子模块
      -> 用例名称（Marker: p0 无标记，p1 使用 priority-1，p2 使用 priority-2）
        -> 前置条件：\n...
        -> 测试数据：\n...
        -> 操作步骤：\n...
          -> 预期结果：\n...
"""

import os
import re
import sys
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

NS = "urn:xmind:xmap:xmlns:content:2.0"
# TestSpec SOP 规范：p0 不标记，p1 使用 1 号 marker，p2 使用 2 号 marker
PRIORITY_MARKERS = {"p1": "priority-1", "p2": "priority-2"}

def _topic_id() -> str:
    return uuid.uuid4().hex

def _create_topic_xml(
    parent: ET.Element,
    title: str,
    *,
    children: Optional[List[Dict]] = None,
    note: Optional[str] = None,
    markers: Optional[List[str]] = None,
) -> ET.Element:
    topic = ET.SubElement(parent, f"{{{NS}}}topic")
    topic.set("id", _topic_id())
    title_elem = ET.SubElement(topic, f"{{{NS}}}title")
    title_elem.text = title or ""

    if markers:
        marker_refs = ET.SubElement(topic, f"{{{NS}}}marker-refs")
        for marker_id in markers:
            marker_ref = ET.SubElement(marker_refs, f"{{{NS}}}marker-ref")
            marker_ref.set("marker-id", marker_id)

    if note:
        notes = ET.SubElement(topic, f"{{{NS}}}notes")
        plain = ET.SubElement(notes, f"{{{NS}}}plain")
        plain.text = note

    if children:
        children_elem = ET.SubElement(topic, f"{{{NS}}}children")
        topics_elem = ET.SubElement(children_elem, f"{{{NS}}}topics")
        topics_elem.set("type", "attached")
        for child in children:
            if isinstance(child, dict) and "title" in child:
                _create_topic_xml(
                    topics_elem,
                    child.get("title", ""),
                    children=child.get("children"),
                    note=child.get("note"),
                    markers=child.get("markers"),
                )
            else:
                _create_topic_xml(topics_elem, str(child) if child else "")

    return topic

def _prettify_xml(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="utf-8", xml_declaration=True)
    xml_str = rough.decode("utf-8")
    if "xmlns=" not in xml_str:
        xml_str = xml_str.replace(
            "<xmap-content",
            '<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0"',
            1,
        )
    return xml_str

def _create_manifest() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
    <file-entry full-path="content.xml" media-type="text/xml"/>
    <file-entry full-path="META-INF/" media-type=""/>
    <file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
    <file-entry full-path="styles.xml" media-type="text/xml"/>
    <file-entry full-path="meta.xml" media-type="text/xml"/>
</manifest>"""

def _create_styles_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xmap-styles xmlns="urn:xmind:xmap:xmlns:style:2.0" version="2.0">
</xmap-styles>"""

def _create_meta_xml() -> bytes:
    t = int(time.time() * 1000)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<meta xmlns="urn:xmind:xmap:xmlns:meta:2.0" version="2.0">
    <Author>
        <Name>Antigravity SDET</Name>
    </Author>
    <Create>{t}</Create>
    <Modified>{t}</Modified>
</meta>""".encode("utf-8")

def _create_content_xml(structure: List[Dict], root_title: str, sheet_title: str) -> bytes:
    ET.register_namespace("", NS)
    xmap_content = ET.Element(f"{{{NS}}}xmap-content")
    xmap_content.set("version", "2.0")

    sheet = ET.SubElement(xmap_content, f"{{{NS}}}sheet")
    sheet.set("id", _topic_id())
    sheet.set("theme", "plain")
    sheet_title_el = ET.SubElement(sheet, f"{{{NS}}}title")
    sheet_title_el.text = sheet_title

    root_topic = ET.SubElement(sheet, f"{{{NS}}}topic")
    root_topic.set("id", _topic_id())
    root_title_el = ET.SubElement(root_topic, f"{{{NS}}}title")
    root_title_el.text = root_title

    root_node = structure[0] if structure else {"title": root_title, "children": []}
    root_children = root_node.get("children") or []
    if root_children:
        children_elem = ET.SubElement(root_topic, f"{{{NS}}}children")
        topics_elem = ET.SubElement(children_elem, f"{{{NS}}}topics")
        topics_elem.set("type", "attached")
        for item in root_children:
            _create_topic_xml(
                topics_elem,
                item.get("title", ""),
                children=item.get("children"),
                note=item.get("note"),
                markers=item.get("markers"),
            )

    return _prettify_xml(xmap_content).encode("utf-8")

def create_xmind_file(structure: List[Dict], output_path: str, root_title: str, sheet_title: str = "测试用例"):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    content_bytes = _create_content_xml(structure, root_title, sheet_title)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("META-INF/manifest.xml", _create_manifest())
        zf.writestr("content.xml", content_bytes)
        zf.writestr("styles.xml", _create_styles_xml())
        zf.writestr("meta.xml", _create_meta_xml())

def parse_markdown_to_xmind_tree(md_path: str) -> List[Dict]:
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    root_title = "HM 添加企微送积分活动（RE-0480）测试用例集"
    modules = []
    current_module = None
    current_submodule = None
    current_case = None

    for line in lines:
        line_s = line.strip()
        if line_s.startswith('## ') and not any(line_s.startswith(x) for x in ['## 目录', '## 1.', '## 7.']):
            mod_title = re.sub(r'^##\s+(\d+\.\s*)?', '', line_s)
            current_module = {"title": mod_title, "children": []}
            modules.append(current_module)
            current_submodule = None
            current_case = None
        elif line_s.startswith('### ') and current_module is not None:
            submod_title = re.sub(r'^###\s+(\d+\.\d+\s*)?', '', line_s)
            current_submodule = {"title": submod_title, "children": []}
            current_module["children"].append(current_submodule)
            current_case = None
        elif line_s.startswith('#### TC_'):
            m = re.match(r'####\s+(TC_[A-Za-z0-9_]+)\s+\[(P\d)\]\s+(.*)', line_s)
            if m:
                tc_id, prio, name = m.groups()
                prio_lower = prio.lower()
                current_case = {
                    "id": tc_id,
                    "priority": prio_lower,
                    "raw_title": f"{tc_id} {name}",
                    "markers": [PRIORITY_MARKERS[prio_lower]] if prio_lower in PRIORITY_MARKERS else [],
                    "preconditions": "",
                    "test_data": "",
                    "steps": "",
                    "expected": "",
                    "current_field": None
                }
                target = current_submodule if current_submodule is not None else current_module
                target["children"].append(current_case)
        elif current_case is not None:
            if line_s.startswith('- **测试方法**：'):
                current_case["current_field"] = "method"
            elif line_s.startswith('- **前置条件**：'):
                current_case["preconditions"] = line_s.replace('- **前置条件**：', '').strip()
                current_case["current_field"] = "preconditions"
            elif line_s.startswith('- **测试数据**：') or line_s.startswith('- **输入数据**：'):
                current_case["test_data"] = re.sub(r'^- \*\*(?:测试|输入)数据\*\*：', '', line_s).strip()
                current_case["current_field"] = "test_data"
            elif line_s.startswith('- **操作步骤**：') or line_s.startswith('- **业务流程**：'):
                current_case["steps"] = re.sub(r'^- \*\*(?:操作步骤|业务流程)\*\*：', '', line_s).strip()
                current_case["current_field"] = "steps"
            elif line_s.startswith('- **预期结果**：') or line_s.startswith('- **预期输出**：'):
                current_case["expected"] = re.sub(r'^- \*\*(?:预期结果|预期输出)\*\*：', '', line_s).strip()
                current_case["current_field"] = "expected"
            elif line_s.startswith('- **优先级**：'):
                current_case["current_field"] = "priority"
            elif current_case["current_field"] and line_s:
                field = current_case["current_field"]
                if field in current_case and field != "priority":
                    if current_case[field]:
                        current_case[field] += "\n" + line_s
                    else:
                        current_case[field] = line_s

    # Build final hierarchy according to standard XMind 8 test case contract
    def build_node(item):
        if "raw_title" in item:
            # Case node
            detail_children = []
            if item["preconditions"]:
                detail_children.append({"title": f"前置条件：\n{item['preconditions']}"})
            if item["test_data"]:
                detail_children.append({"title": f"测试数据：\n{item['test_data']}"})
            if item["steps"]:
                step_children = []
                if item["expected"]:
                    step_children.append({"title": f"预期结果：\n{item['expected']}"})
                detail_children.append({
                    "title": f"操作步骤：\n{item['steps']}",
                    "children": step_children
                })
            elif item["expected"]:
                detail_children.append({"title": f"预期结果：\n{item['expected']}"})

            return {
                "title": item["raw_title"],
                "markers": item["markers"],
                "children": detail_children
            }
        else:
            return {
                "title": item["title"],
                "children": [build_node(c) for c in item.get("children", [])]
            }

    root_children = [build_node(m) for m in modules]
    return [{"title": root_title, "children": root_children}]

if __name__ == "__main__":
    md_file = "/Users/qm/Documents/TestSpec_SOP/testcases/HM_add_wecom_points_testcase.md"
    out_file = "/Users/qm/Documents/TestSpec_SOP/testcases/HM_add_wecom_points_testcase.xmind"
    tree = parse_markdown_to_xmind_tree(md_file)
    create_xmind_file(tree, out_file, root_title="HM 添加企微送积分活动（RE-0480）测试用例集")
    print(f"XMind 生成成功：{out_file}")
