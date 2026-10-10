import re

with open('/Users/qm/Documents/TestSpec_SOP/testcases/HM_add_wecom_points_testcase.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

current_module = None
current_submodule = None
current_case = None
cases_by_structure = []

# Module pattern: ## 2. 模块一：新 UnionID ...
# Submodule pattern: ### 2.1 触发入口...
# Case pattern: #### TC_... [P0] ...

for line in lines:
    line_s = line.strip()
    if line_s.startswith('## ') and not line_s.startswith('## 目录') and not line_s.startswith('## 1.'):
        mod_title = re.sub(r'^##\s+(\d+\.\s*)?', '', line_s)
        current_module = {"title": mod_title, "children": []}
        cases_by_structure.append(current_module)
        current_submodule = None
        current_case = None
    elif line_s.startswith('### ') and current_module is not None:
        submod_title = re.sub(r'^###\s+(\d+\.\d+\s*)?', '', line_s)
        current_submodule = {"title": submod_title, "children": []}
        current_module["children"].append(current_submodule)
        current_case = None
    elif line_s.startswith('#### TC_'):
        m = re.match(r'####\s+(TC_[A-Z]+_\d+)\s+\[(P\d)\]\s+(.*)', line_s)
        if m:
            tc_id, prio, name = m.groups()
            current_case = {
                "id": tc_id,
                "priority": prio.lower(),
                "title": f"[{prio}] {tc_id} {name}",
                "method": "",
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
            current_case["method"] = line_s.replace('- **测试方法**：', '').strip()
            current_case["current_field"] = "method"
        elif line_s.startswith('- **前置条件**：'):
            current_case["preconditions"] = line_s.replace('- **前置条件**：', '').strip()
            current_case["current_field"] = "preconditions"
        elif line_s.startswith('- **输入数据**：'):
            current_case["test_data"] = line_s.replace('- **输入数据**：', '').strip()
            current_case["current_field"] = "test_data"
        elif line_s.startswith('- **业务流程**：'):
            current_case["steps"] = line_s.replace('- **业务流程**：', '').strip()
            current_case["current_field"] = "steps"
        elif line_s.startswith('- **操作步骤**：'):
            current_case["steps"] = line_s.replace('- **操作步骤**：', '').strip()
            current_case["current_field"] = "steps"
        elif line_s.startswith('- **预期输出**：'):
            current_case["expected"] = line_s.replace('- **预期输出**：', '').strip()
            current_case["current_field"] = "expected"
        elif current_case["current_field"] and line_s:
            # Multi-line continuation
            field = current_case["current_field"]
            if current_case[field]:
                current_case[field] += "\n" + line_s
            else:
                current_case[field] = line_s

print(f"Parsed modules: {len(cases_by_structure)}")
for m in cases_by_structure:
    print(f"Module: {m['title']}, submodules: {len(m['children'])}")
    total_cases = 0
    for sub in m['children']:
        if "children" in sub:
            total_cases += len(sub["children"])
        else:
            total_cases += 1
    print(f"  Total cases: {total_cases}")
