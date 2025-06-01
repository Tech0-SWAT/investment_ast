# stock_schema_single_user.py
import sqlite3

DB = "app.db"

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON;")

    # ── 銘柄マスター ───────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS securities (
        security_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        security_code  TEXT  UNIQUE NOT NULL,   -- 例: 7203
        d365_code      TEXT  UNIQUE NOT NULL,   -- 同一を保証
        security_name  TEXT  NOT NULL
    );
    """)

    # ── 売買トランザクション（口座 FK なし） ──────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        security_id    INTEGER NOT NULL,
        txn_type       TEXT CHECK (txn_type IN ('BUY','SEL')) NOT NULL,
        quantity       REAL NOT NULL,
        price          REAL NOT NULL,
        txn_date       DATE NOT NULL,
        create_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (security_id) REFERENCES securities(security_id) ON DELETE CASCADE
    );
    """)

    # ── 日次株価 ───────────────────────────────────
    conn.execute("""
    CREATE TABLE IF NOT EXISTS price_quotes (
        quote_date   DATE    NOT NULL,
        security_id  INTEGER NOT NULL,
        close_price  REAL    NOT NULL,
        PRIMARY KEY (quote_date, security_id),
        FOREIGN KEY (security_id) REFERENCES securities(security_id) ON DELETE CASCADE
    );
    """)

    # ── 最新株価ビュー ─────────────────────────────
    conn.execute("""
    CREATE VIEW IF NOT EXISTS latest_prices AS
    SELECT pq.security_id,
           pq.close_price AS market_price
    FROM price_quotes pq
    JOIN (
        SELECT security_id, MAX(quote_date) AS max_date
        FROM price_quotes
        GROUP BY security_id
    ) t ON pq.security_id = t.security_id
        AND pq.quote_date = t.max_date;
    """)

    # ── 保有状況ビュー（画面用）───────────────────────
    conn.execute("""
    CREATE VIEW IF NOT EXISTS v_positions AS
    SELECT
        s.d365_code                                         AS d365_code,
        s.security_code                                     AS security_code,
        s.security_name                                     AS security_name,
        SUM(t.quantity)                                     AS holding_qty,
        CASE WHEN SUM(t.quantity) <> 0
             THEN SUM(t.quantity * t.price) / SUM(t.quantity)
             ELSE 0 END                                    AS avg_cost,
        lp.market_price                                     AS market_price,
        (lp.market_price -
         CASE WHEN SUM(t.quantity) <> 0
              THEN SUM(t.quantity * t.price) / SUM(t.quantity)
              ELSE 0 END) * SUM(t.quantity)                AS valuation_diff
    FROM transactions t
    JOIN securities   s  ON t.security_id  = s.security_id
    LEFT JOIN latest_prices lp ON s.security_id = lp.security_id
    GROUP BY s.d365_code, s.security_code, s.security_name, lp.market_price;
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS positions_halfyear (
        security_id    INTEGER    NOT NULL,
        d365_code      TEXT       NOT NULL,
        security_code  TEXT       NOT NULL,
        security_name  TEXT       NOT NULL,
        year           TEXT       NOT NULL,    -- 例: '2023'
        half           TEXT       NOT NULL,    -- 'H1' or 'H2'
        holding_qty    REAL       NOT NULL,    -- 半期末時点の累積保有株数
        avg_cost       REAL       NOT NULL,    -- 半期末時点の累積平均取得単価
        market_price   REAL       NOT NULL,    -- 半期末時点の直近終値
        market_cap     REAL       NOT NULL,    -- holding_qty * market_price
        PRIMARY KEY (security_id, year, half),
        FOREIGN KEY (security_id) REFERENCES securities(security_id) ON DELETE CASCADE
    );
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS positions_quarter (
        security_id    INTEGER    NOT NULL,
        d365_code      TEXT       NOT NULL,
        security_code  TEXT       NOT NULL,
        security_name  TEXT       NOT NULL,
        year           TEXT       NOT NULL,
        quarter        TEXT       NOT NULL,
        holding_qty    REAL       NOT NULL,
        avg_cost       REAL       NOT NULL,
        market_price   REAL       NOT NULL,
        market_cap     REAL       NOT NULL,
        PRIMARY KEY (security_id, year, quarter),
        FOREIGN KEY (security_id) REFERENCES securities(security_id) ON DELETE CASCADE
    );
    """)

    # --- 30%下落判定結果テーブル ---
    conn.execute("""
    CREATE TABLE IF NOT EXISTS drop_judgement (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        security_code TEXT,
        year          TEXT,
        quarter       TEXT,      -- half → quarter に変更
        drop_30pct    INTEGER,
        judged_at     TEXT
    );
    """)


    conn.commit()
    conn.close()
    print("🎉 スキーマ（1 ユーザー版）構築完了")

if __name__ == "__main__":
    main()
