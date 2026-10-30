Feature: 密码重置

  Scenario: 密码重置可以正常工作
    Given 一位已注册用户位于重置页面
    When 用户输入新密码并点击提交
    Then 密码可以正常使用
