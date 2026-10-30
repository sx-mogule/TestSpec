Feature: 折扣处理

  Scenario: Gold 顾客获得折扣
    Given 一位 Gold 顾客
    When 顾客购买商品
    Then 系统会应用折扣

  Scenario: 使用折扣结账成功
    Given 一位 Gold 顾客的购物车中有商品
    When 顾客购买受限商品并结账
    Then 系统会处理结果
