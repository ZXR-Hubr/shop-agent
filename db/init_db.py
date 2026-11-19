"""初始化 MySQL 数据库：建库、建表、从 data/*.json 导入示例数据。

可重复执行（幂等）：每次会重建表并重新导入，适合演示环境。
连接参数优先读环境变量 / .env，不把密码写死在代码里。

用法：
    .venv\\Scripts\\python.exe db\\init_db.py
"""
import json
import sys
from pathlib import Path

import pymysql

# 从 db/ 子目录运行时，把项目根目录加入模块搜索路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.mysql_config import mysql_settings


def _load_json(name: str):
    return json.loads((BASE_DIR / "data" / name).read_text(encoding="utf-8"))


def main():
    ms = mysql_settings
    print(f"[连接] {ms.host}:{ms.port} user={ms.user} db={ms.database}")

    # 第一步：不指定库连接，建库
    conn = pymysql.connect(
        host=ms.host, port=ms.port, user=ms.user,
        password=ms.password, charset="utf8mb4", autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{ms.database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            print(f"[建库] {ms.database} OK")
    finally:
        conn.close()

    # 第二步：连到目标库，建表 + 导数据
    conn = pymysql.connect(
        host=ms.host, port=ms.port, user=ms.user,
        password=ms.password, database=ms.database,
        charset="utf8mb4", autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            # 先建表（按外键依赖顺序：商品、订单、知识库，最后售后工单引用订单）
            cur.execute("DROP TABLE IF EXISTS after_sales_tickets")
            cur.execute("DROP TABLE IF EXISTS orders")
            cur.execute("DROP TABLE IF EXISTS products")
            cur.execute("DROP TABLE IF EXISTS kb_articles")

            cur.execute("""
                CREATE TABLE products (
                    product_id  VARCHAR(32)  PRIMARY KEY COMMENT '商品ID',
                    name        VARCHAR(128) NOT NULL COMMENT '商品名称',
                    category    VARCHAR(32)  NOT NULL COMMENT '类目',
                    price       DECIMAL(10,2) NOT NULL COMMENT '价格(元)',
                    stock       INT          NOT NULL DEFAULT 0 COMMENT '库存',
                    tags        VARCHAR(255) NOT NULL DEFAULT '' COMMENT '标签,逗号分隔',
                    description TEXT COMMENT '商品描述'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表'
            """)

            cur.execute("""
                CREATE TABLE orders (
                    order_id     VARCHAR(32)  PRIMARY KEY COMMENT '订单号',
                    product_id   VARCHAR(32)  NOT NULL COMMENT '商品ID',
                    product_name VARCHAR(128) NOT NULL COMMENT '商品名称',
                    status       VARCHAR(32)  NOT NULL COMMENT '订单状态',
                    amount       DECIMAL(10,2) NOT NULL COMMENT '订单金额',
                    logistics    VARCHAR(128) NOT NULL DEFAULT '' COMMENT '物流信息',
                    created_at   VARCHAR(32)  NOT NULL COMMENT '下单时间',
                    address      VARCHAR(255) NOT NULL DEFAULT '' COMMENT '收货地址',
                    receiver     VARCHAR(32)  NOT NULL DEFAULT '' COMMENT '收货人',
                    phone        VARCHAR(32)  NOT NULL DEFAULT '' COMMENT '联系电话(脱敏)',
                    quantity     INT          NOT NULL DEFAULT 1 COMMENT '购买数量',
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表'
            """)

            cur.execute("""
                CREATE TABLE kb_articles (
                    id      VARCHAR(32) PRIMARY KEY COMMENT '知识库ID',
                    title   VARCHAR(128) NOT NULL COMMENT '标题',
                    content TEXT NOT NULL COMMENT '正文',
                    tags    VARCHAR(255) NOT NULL DEFAULT '' COMMENT '标签,逗号分隔'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客服知识库'
            """)

            cur.execute("""
                CREATE TABLE after_sales_tickets (
                    ticket_id    VARCHAR(32) PRIMARY KEY COMMENT '工单号',
                    order_id     VARCHAR(32) NOT NULL COMMENT '订单号',
                    product_name VARCHAR(128) NOT NULL COMMENT '商品名称',
                    reason       VARCHAR(255) NOT NULL DEFAULT '' COMMENT '售后原因',
                    type         VARCHAR(16)  NOT NULL DEFAULT '退货' COMMENT '售后类型:退货/换货/维修',
                    status       VARCHAR(32) NOT NULL DEFAULT '待审核' COMMENT '工单状态',
                    amount       DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '退款/换货金额(元)',
                    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    INDEX idx_order (order_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='售后工单表'
            """)
            print("[建表] 4 张表 OK")

            # 导入商品
            products = _load_json("products.json")
            cur.executemany(
                "INSERT INTO products (product_id,name,category,price,stock,tags,description) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [
                    (p["product_id"], p["name"], p["category"], p["price"], p["stock"],
                     ",".join(p.get("tags", [])), p.get("description", ""))
                    for p in products
                ],
            )
            print(f"[导入] products  {len(products)} 行")

            # 导入订单
            orders = _load_json("orders.json")
            cur.executemany(
                "INSERT INTO orders (order_id,product_id,product_name,status,amount,logistics,created_at,address,receiver,phone,quantity) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [
                    (o["order_id"], o["product_id"], o["product_name"], o["status"],
                     o["amount"], o["logistics"], o["created_at"], o["address"],
                     o.get("receiver", ""), o.get("phone", ""), o.get("quantity", 1))
                    for o in orders
                ],
            )
            print(f"[导入] orders    {len(orders)} 行")

            # 导入知识库
            kb = _load_json("kb.json")
            cur.executemany(
                "INSERT INTO kb_articles (id,title,content,tags) VALUES (%s,%s,%s,%s)",
                [(d["id"], d["title"], d["content"], ",".join(d.get("tags", []))) for d in kb],
            )
            print(f"[导入] kb        {len(kb)} 行")

            # 导入售后工单（退货 / 换货 / 维修）
            after_sales = _load_json("after_sales.json")
            cur.executemany(
                "INSERT INTO after_sales_tickets (ticket_id,order_id,product_name,type,reason,status,amount,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [
                    (a["ticket_id"], a["order_id"], a["product_name"], a.get("type", "退货"),
                     a.get("reason", ""), a.get("status", "待审核"), a.get("amount", 0),
                     a.get("created_at"))
                    for a in after_sales
                ],
            )
            print(f"[导入] after_sales {len(after_sales)} 行")

            # 行数核验
            print("\n[核验] 各表行数：")
            for table in ("products", "orders", "kb_articles", "after_sales_tickets"):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"  {table:20s} {cur.fetchone()[0]}")
            print("\n初始化完成。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
