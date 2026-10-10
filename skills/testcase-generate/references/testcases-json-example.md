# testcases.json 示例

```json
{
  "schema_version": 2,
  "_context": {
    "source_skill": "testcase-generate",
    "source_revision": {
      "version": 2,
      "summary": "补充账号锁定规则",
      "updated_by_skill": "prd-analysis"
    },
    "blocking_open_questions": [],
    "dynamic_followups": [],
    "material_quality": "high",
    "stale_downstream_artifacts": ["review-report.md"],
    "stale_reason": "测试用例已按新口径重生成，评审待更新",
    "next_skill": "testcase-review",
    "canonical_source_policy": "prd-first",
    "evidence_sources": [{"type": "prd", "source_ref": "requirements.md#REQ-001", "authority": "canonical"}],
    "questions": [],
    "origin": {"kind": "testspec-native", "source_change": "synthetic-account-access"},
    "trust": {"status": "provisional", "basis": "prd-first"},
    "design_methods": ["等价类"]
  },
  "testcases": [
    {
      "id": "<需求名称>_202602280001",
      "scenario_key": "LOGIN|CRED|VALID_CREDENTIALS",
      "module": "登录",
      "submodule": "凭据验证",
      "test_name": "登录_凭据验证_正确凭据登录成功",
      "title": "登录_凭据验证_正确凭据登录成功",
      "feature": "登录",
      "name": "正常登录-有效账号密码",
      "type": "正向",
      "regression_tier": "Smoke",
      "tp_refs": ["TP_LOGIN_CRED_001"],
      "preconditions": "1、系统已启动\n2、用户已注册",
      "test_data": "账号：已注册用户；密码：正确密码",
      "steps": "1、打开登录页\n2、输入正确账号密码\n3、点击「登录」按钮",
      "expected_result": "1、登录成功，页面跳转至首页\n2、顶部显示「欢迎回来」提示",
      "priority": "p0",
      "origin": {"kind": "testspec-native", "source_change": "synthetic-account-access"},
      "trust": {"status": "provisional", "basis": "prd-first"}
    }
  ]
}
```

导出 XMind 时，`steps` 中的多条编号步骤保留在一个“操作步骤”节点，`expected_result` 中的多条编号预期保留在其子节点“预期结果”中；不按每个编号另建节点。
