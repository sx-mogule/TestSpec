# 质量阶梯示例

本文提供五个从很差到优秀的分级示例。每个示例均展示有代表性的输入，以及预期的 Skill 输出风格。

## 1. 很差的评审对象

### 输入

```text
请评审以下场景：

Scenario: 测试登录
  Given 我点击登录框
  And 我输入 bob
  And 我输入 secret
  When 我点击按钮
  Then 它可以正常工作
```

### 预期输出

```text
Mode: review
Oracle used: 仅场景文字
Oracle sufficiency: weak
Confidence: low

Findings:
1. High：此场景是 UI 脚本，不是业务可读的行为描述。
   Evidence：“我点击登录框”“我点击按钮”
   Why it matters：此场景无法作为长期有效的业务文档。
   Fix：使用领域语言，围绕登录行为重写步骤。
2. High：预期结果含糊。
   Evidence：“Then 它可以正常工作”
   Why it matters：结果无法验证。
   Fix：替换为可观察结果，例如成功访问仪表板。
3. Low：标题过于笼统。
   Evidence：“Scenario: 测试登录”
   Why it matters：标题没有说明条件和结果。
   Fix：重新命名，反映用户行为及其结果。
```

## 2. 薄弱的特性草稿

### 输入

```text
请评审以下特性：

Feature: 折扣
  Scenario: 顾客获得折扣并且结账成功
    Given 一位顾客已存在
    When 顾客购买商品
    Then 折扣正确
    And 订单已确认
```

### 预期输出

```text
Mode: review
Oracle used: 仅特性文件文字
Oracle sufficiency: weak
Confidence: low

Findings:
1. High：场景混合了多个行为。
   Evidence：折扣计算和订单确认出现在同一场景。
   Why it matters：混合行为会增加覆盖分析和维护难度。
   Fix：如果折扣计算和结账确认代表不同规则，应拆成两个独立场景。
2. High：预期结果含糊。
   Evidence：“Then 折扣正确”
   Why it matters：场景没有说明“正确”具体指什么。
   Fix：使用具体金额、比率或业务结果。
3. Low：特性标题范围太广。
   Evidence：“Feature: 折扣”
   Why it matters：范围不清楚。
   Fix：根据具体能力或规则集重新命名特性。
```

## 3. 改写请求

### 输入

```text
请改写此场景：

Scenario: Gold 顾客获得折扣
  Given 一位 Gold 顾客
  When 顾客购买商品
  Then 系统应用折扣
```

### 预期输出

```text
Mode: rewrite
Rewrite strategy:
- 保留折扣规则的核心含义。
- 将笼统的名词和结果替换为具体的业务示例。

Rewritten artifact:
Scenario: Gold 会员购买符合条件的商品时获得标准折扣
  Given 一位拥有有效订阅的 Gold 会员
  When 该会员购买符合条件的商品
  Then 结账总额包含 Gold 会员的标准折扣

Open assumptions:
- 未提供确切的折扣比率。
- 未提供受限商品的适用规则。
```

## 4. 混合评审与改写

### 输入

```text
请根据密码重置验收标准评审并改进此特性文件。
```

### 预期输出

```text
Mode: hybrid
Oracle used: 验收标准
Oracle sufficiency: partial
Confidence: medium

Key findings:
1. High：未覆盖过期链接的拒绝路径。
2. High：主场景没有说明重置后可从外部观察的结果。

Rewritten artifact:
Feature: 已注册用户重置密码
  作为一名已注册用户
  我希望重置密码
  从而重新访问我的账户

  Scenario: 已注册用户使用有效的重置链接重置密码
    Given 一位已注册用户已请求重置密码
    When 用户打开有效的重置链接并提交新密码
    Then 密码已更新
    And 用户可以使用新密码登录

  Scenario: 已注册用户无法使用过期的重置链接重置密码
    Given 一位已注册用户已请求重置密码
    And 重置链接已过期
    When 用户打开已过期的重置链接
    Then 用户会看到重置链接已失效的提示

Open assumptions:
- 验收标准未定义再次请求重置链接是否会使此前的链接失效。
```

## 5. 良好的评审对象

### 输入

```text
请从 BDD 质量和覆盖角度评审此特性：

@requirement-PWD-101
Feature: 密码重置
  作为一名已注册用户
  我希望重置密码
  从而重新访问我的账户

  @main
  Scenario: 已注册用户使用有效的重置链接重置密码
    Given 一位已注册用户已请求重置密码
    When 用户打开有效的重置链接并提交新密码
    Then 密码已更新
    And 用户可以使用新密码登录

  @error
  Scenario: 已注册用户无法使用过期的重置链接重置密码
    Given 一位已注册用户已请求重置密码
    And 重置链接已过期
    When 用户打开已过期的重置链接
    Then 用户会看到重置链接已失效的提示
```

### 预期输出

```text
Mode: review
Oracle used: 特性文件文字和需求标签
Oracle sufficiency: partial
Confidence: medium

Findings:
- No material defects identified（未发现实质性缺陷）。

Traceability and coverage:
- 主路径和过期链接拒绝路径都清晰易懂，且符合业务表述。
- 只有来源需求明确时才应增加其他替代路径行为。

Top recommendations:
- 扩展特性前，先确认重新发送链接行为是否属于范围。
```
