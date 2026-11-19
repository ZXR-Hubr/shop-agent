"""MySQL 集成测试：单独运行，需本机 MySQL 已初始化（db/init_db.py）。

由于 conftest 强制 MYSQL_ENABLED=0，这里在导入 app 模块前手动开启，
并直接调 db 层与 tools 验证数据确实来自 MySQL。
"""
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 覆盖 conftest 的设置：本测试要真连 MySQL
os.environ["MYSQL_ENABLED"] = "1"
os.environ["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "127.0.0.1")
os.environ["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD", "123456")


def test_mysql_connect_and_data():
    import app.mysql_config as mc
    importlib.reload(mc)
    from app import db

    assert db.ping(), "MySQL 未连接成功"
    print("[OK] MySQL 连接成功")

    products = db.fetch_all("SELECT * FROM products")
    assert products and len(products) >= 9
    print(f"[OK] products 读到 {len(products)} 行")

    order = db.fetch_one("SELECT * FROM orders WHERE order_id=%s", ("SO20261114002",))
    assert order and order["status"] == "运输中"
    print(f"[OK] 订单状态: {order['status']} / {order['logistics']}")

    kb = db.fetch_all("SELECT * FROM kb_articles")
    assert kb and len(kb) >= 12
    print(f"[OK] kb_articles 读到 {len(kb)} 行")


def test_tools_read_from_mysql():
    import app.mysql_config as mc
    importlib.reload(mc)
    import app.db as db_mod
    importlib.reload(db_mod)
    import app.tools as tools
    importlib.reload(tools)

    # 商品检索应标记为 mysql 来源
    r = tools.search_products(query="手机", max_price=2000)
    assert r.get("source") == "mysql", r
    assert any(x["product_id"] == "P1009" for x in r["items"])
    print(f"[OK] search_products 来自 MySQL，命中 {r['count']} 件")

    # 订单查询应标记为 mysql 来源
    o = tools.get_order("SO20261114002")
    assert o.get("source") == "mysql" and o["status"] == "运输中"
    print("[OK] get_order 来自 MySQL")

    # 创建工单应写入 MySQL
    t = tools.create_after_sales("SO20261112001", "集成测试-耳机杂音")
    assert t["success"] and t.get("storage") == "mysql", t
    print(f"[OK] 售后工单写入 MySQL: {t['ticket_id']}")

    # 回读确认落库
    row = db_mod.fetch_one("SELECT * FROM after_sales_tickets WHERE ticket_id=%s", (t["ticket_id"],))
    assert row and row["reason"] == "集成测试-耳机杂音"
    print("[OK] 工单回读成功，确认落库")

    # 清理测试数据
    db_mod.execute("DELETE FROM after_sales_tickets WHERE ticket_id=%s", (t["ticket_id"],))
    print("[OK] 测试工单已清理")


if __name__ == "__main__":
    test_mysql_connect_and_data()
    test_tools_read_from_mysql()
    print("\nMySQL 集成测试全部通过。")
