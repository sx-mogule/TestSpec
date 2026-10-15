import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/generate_xmind.py"
SUBPROCESS_TIMEOUT = int(os.getenv("TEST_SUBPROCESS_TIMEOUT", "60"))


class TestFullDelivery(unittest.TestCase):
    def test_full_set_export_keeps_smoke_case_without_secondary_artifacts(self):
        """冒烟分类作为完整集元数据导出；全量 XMind 包含所有场景。"""
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td) / "artifacts"
            artifacts.mkdir()
            input_path = artifacts / "testcases.json"
            output_path = artifacts / "synthetic-smoke-fullset_cases.xmind"
            payload = {
                "schema_version": 2,
                "_context": {},
                "testcases": [
                    {
                        "id": "SYN_FULL_001",
                        "module": "订单",
                        "submodule": "查询",
                        "test_name": "订单_查询_详情展示商品明细",
                        "preconditions": "1、已准备可查询的订单",
                        "test_data": "订单：已支付订单",
                        "steps": "1、打开订单详情",
                        "expected_result": "1、详情展示商品名称、数量和金额",
                        "priority": "p0",
                        "type": "正向",
                        "regression_tier": "Full",
                        "tp_refs": ["TP_ORDER_QUERY_001"],
                    },
                    {
                        "id": "SYN_FULL_002",
                        "module": "订单",
                        "submodule": "提交",
                        "test_name": "订单_提交_创建后显示待支付订单",
                        "preconditions": "1、商品可购买",
                        "test_data": "商品：有效商品",
                        "steps": "1、提交创建订单",
                        "expected_result": "1、详情显示订单编号和待支付状态",
                        "priority": "p0",
                        "type": "冒烟",
                        "regression_tier": "Smoke",
                        "tp_refs": ["TP_ORDER_SUBMIT_001"],
                    },
                    {
                        "id": "SYN_FULL_003",
                        "module": "订单",
                        "submodule": "取消",
                        "test_name": "订单_取消_关闭待支付订单",
                        "preconditions": "1、已有待支付订单",
                        "test_data": "订单：待支付订单",
                        "steps": "1、取消订单并确认",
                        "expected_result": "1、订单状态变为已关闭",
                        "priority": "p1",
                        "type": "正向",
                        "regression_tier": "Full",
                        "tp_refs": ["TP_ORDER_CANCEL_001"],
                    },
                ],
            }
            input_bytes = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            input_path.write_bytes(input_bytes)

            subprocess.check_call(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--title",
                    "完整测试用例",
                ],
                timeout=SUBPROCESS_TIMEOUT,
            )

            with zipfile.ZipFile(output_path, "r") as zf:
                self.assertIsNone(zf.testzip())
                content = zf.read("content.xml").decode("utf-8")

            for scenario in (
                "详情展示商品明细",
                "创建后显示待支付订单",
                "关闭待支付订单",
            ):
                self.assertIn(f"<title>{scenario}</title>", content)
            self.assertEqual(input_path.read_bytes(), input_bytes)
            self.assertEqual(
                {path.name for path in artifacts.iterdir()},
                {"testcases.json", "synthetic-smoke-fullset_cases.xmind"},
            )



if __name__ == "__main__":
    unittest.main()
