# 使用前替换所有占位符。
# 只保留来源材料支持的章节。
# 只有项目已有可选标签约定时，才取消标签注释。

Feature: <以能力为中心的标题>
  作为一名 <角色>
  我希望 <能力>
  从而 <业务价值>

  # Rule: <业务规则名称>

  # 可选元数据：
  # @requirement-<id>
  # @persona-<role>
  # @main
  Scenario: <条件及可观察结果>
    Given <最少必要的业务上下文>
    When <用户或外部操作>
    Then <可观察的业务结果>

  # 可选的替代或拒绝路径：
  # @alt
  Scenario: <有效的替代结果>
    Given <最少必要的业务上下文>
    When <有效的替代操作或条件>
    Then <可观察的替代结果>

  # 可选的无效或阻止路径：
  # @error
  Scenario: <受阻或无效路径>
    Given <最少必要的业务上下文>
    When <无效或受阻的操作>
    Then <可观察的拒绝或失败结果>

  # 可选的大纲：仅当每一行遵循相同规则结构时使用：
  # Scenario Outline: <参数化示例遵循的同一规则>
  #   Given <包含 <parameter> 的最少必要业务上下文>
  #   When <操作>
  #   Then <可观察结果>
  #
  #   Examples:
  #     | parameter |
  #     | value-1   |
  #     | value-2   |
