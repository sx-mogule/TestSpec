@requirement-AUTH-101
Feature: 账户登录
  作为一名已注册用户
  我希望登录账户
  从而访问我的仪表板

  Scenario: 登录成功
    Given 我打开登录页面
    When 我输入有效凭证
    And 我点击提交
    Then 我已登录

  Scenario: 连续多次输入无效密码后账户会被锁定
    Given 一位已注册用户已连续三次输入无效密码
    When 用户再次提交凭证
    Then 用户会看到账户已锁定的提示
