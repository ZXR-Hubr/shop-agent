from app.tools import create_after_sales, get_order, search_faq, search_products


def test_search_products_by_keyword():
    result = search_products("降噪耳机")
    assert result["count"] > 0
    assert any("耳机" in item["name"] for item in result["items"])


def test_search_products_price_filter():
    result = search_products("手机", max_price=2000)
    assert result["count"] > 0
    assert all(item["price"] <= 2000 for item in result["items"])


def test_search_products_no_match():
    result = search_products("投影仪")
    assert result["count"] == 0


def test_get_order_found_and_missing():
    found = get_order("SO20261114002")
    assert found["found"] is True
    assert found["status"] == "运输中"

    missing = get_order("SO00000000")
    assert missing["found"] is False


def test_create_after_sales():
    result = create_after_sales("SO20261112001", "耳机有杂音")
    assert result["success"] is True
    assert result["ticket_id"].startswith("AS")
    assert result["status"] == "待审核"


def test_create_after_sales_with_unknown_order():
    result = create_after_sales("SO00000000", "测试")
    assert result["success"] is False


def test_search_faq():
    result = search_faq("包邮吗")
    assert result["results"]
    top = result["results"][0]
    assert "包邮" in top["title"] + top["content"]
