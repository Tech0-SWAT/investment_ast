# quarterly_input.py
from pathlib import Path
from datetime import date
import sqlite3

import streamlit as st
import pandas as pd

# ─────────────────────────────
# 1. DB 接続ユーティリティ
# ─────────────────────────────
DB = "../app.db"
db_path = (Path(__file__).resolve().parent / DB).resolve()

@st.cache_resource
def get_conn():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ─────────────────────────────
# 2. 既存 securities / positions_quarter 一覧
# ─────────────────────────────
# @st.cache_data(ttl=600)
def load_securities():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT security_id, security_code, security_name FROM securities", conn
    )
    return df

# @st.cache_data(ttl=600)
def load_positions_quarter():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM positions_quarter", conn)
    return df

# ─────────────────────────────
# 3. 画面レイアウト
# ─────────────────────────────
st.set_page_config(page_title="四半期集計マスタ編集", layout="wide")
st.title("🗓️ 四半期集計（positions_quarter）入力")

df_securities = load_securities()
codes = df_securities["security_code"].tolist()

# ─────────────────────────────
# 3-A  登録／上書きフォーム
# ─────────────────────────────
with st.form("quarter_form", clear_on_submit=False):
    sel_code = st.selectbox("銘柄コード", codes)
    sec_row  = df_securities[df_securities["security_code"] == sel_code].iloc[0]
    security_id   = int(sec_row["security_id"])
    security_name = sec_row["security_name"]

    today_y = date.today().year
    year_in  = st.number_input("対象年 (YYYY)", min_value=2000, max_value=today_y+1,
                               value=today_y, step=1)
    quarter_in = st.selectbox("四半期", ("Q1", "Q2", "Q3", "Q4"))

    qty_in   = st.number_input("保有株数 (holding_qty)",  min_value=0.0, step=100.0)
    cost_in  = st.number_input("平均取得単価 (avg_cost)", min_value=0.0, step=1.0)
    price_in = st.number_input("期末株価 (market_price)", min_value=0.0, step=1.0)

    submitted = st.form_submit_button("登録 / 上書き")

if submitted:
    conn = get_conn()
    market_cap = qty_in * price_in

    try:
        conn.execute(
            """
            INSERT INTO positions_quarter
                (security_id, d365_code, security_code, security_name,
                 year, quarter, holding_qty, avg_cost, market_price, market_cap)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(security_id, year, quarter)
            DO UPDATE SET
                holding_qty  = excluded.holding_qty,
                avg_cost     = excluded.avg_cost,
                market_price = excluded.market_price,
                market_cap   = excluded.market_cap;
            """,
            (
                security_id,
                sel_code,          # d365_code を security_code と同一運用
                sel_code,
                security_name,
                str(year_in),
                quarter_in,        # Q1〜Q4 を格納
                qty_in,
                cost_in,
                price_in,
                market_cap,
            )
        )
        conn.commit()
        st.success("登録 / 更新が完了しました ✅")
        # load_positions_quarter.clear()
    except Exception as e:
        st.error(f"登録失敗: {e}")

# ─────────────────────────────
# 3-B  削除 GUI
# ─────────────────────────────
st.markdown("---")
st.subheader("🗑️ 行を削除")

df_pq = load_positions_quarter()
if df_pq.empty:
    st.info("positions_quarter（四半期データ）にまだデータがありません。")
else:
    # 表示用キーを生成 例: 7203 | 2024 Q3
    df_pq["row_key"] = (df_pq["security_code"] + " | " +
                        df_pq["year"] + " " + df_pq["quarter"])
    del_key = st.selectbox("削除対象を選択", df_pq["row_key"].tolist())

    if st.button("選択した行を削除", key="delete_button"):
        try:
            # 選択キーから行を特定
            target = df_pq[df_pq["row_key"] == del_key].iloc[0]
            conn   = get_conn()
            conn.execute(
                """
                DELETE FROM positions_quarter
                WHERE security_id = ? AND year = ? AND quarter = ?
                """,
                (int(target["security_id"]), target["year"], target["quarter"])
            )
            conn.commit()
            st.success(f"削除しました: {del_key}")
            # load_positions_quarter.clear()  # キャッシュ更新
        except Exception as e:
            st.error(f"削除失敗: {e}")






# ─────────────────────────────
# 4. 一覧表示
# ─────────────────────────────
st.markdown("---")
st.subheader("現在登録されている四半期データ")
df_latest = load_positions_quarter()
if df_latest.empty:
    st.info("まだデータがありません。")
else:
    # 年・四半期でソート
    df_latest = df_latest.sort_values(["security_code", "year", "quarter"])
    df_latest["year"] = df_latest["year"].astype(str)

    # ─────────────────────────────
    # (A) 前期の年・四半期を計算
    # ─────────────────────────────
    def get_prev_quarter(row):
        y = int(row["year"])
        q = row["quarter"]
        if q == "Q1":
            return y - 1, "Q4"
        elif q == "Q2":
            return y, "Q1"
        elif q == "Q3":
            return y, "Q2"
        else:  # Q4
            return y, "Q3"

    prev_periods = df_latest.apply(get_prev_quarter, axis=1)
    df_latest["prev_year_val"] = [y for y, _ in prev_periods]
    df_latest["prev_quarter_val"] = [q for _, q in prev_periods]
    df_latest["prev_year_val"] = df_latest["prev_year_val"].astype(str)

    # ─────────────────────────────
    # (B) 前期の market_price をマージして price_drop_rate を計算
    # ─────────────────────────────
    temp = df_latest[["security_code", "year", "quarter", "market_price"]].rename(
        columns={
            "year": "prev_year_val",
            "quarter": "prev_quarter_val",
            "market_price": "prev_market_price"
        }
    )
    df_latest = pd.merge(
        df_latest,
        temp,
        how="left",
        left_on=["security_code", "prev_year_val", "prev_quarter_val"],
        right_on=["security_code", "prev_year_val", "prev_quarter_val"]
    )
    df_latest["price_drop_rate"] = (
        (df_latest["market_price"] - df_latest["prev_market_price"])
        / df_latest["prev_market_price"]
    )

    # ─────────────────────────────
    # (C) 今期の drop_30pct / drop_50pct を計算
    # ─────────────────────────────
    df_latest["drop_30pct"] = df_latest["price_drop_rate"] <= -0.3
    df_latest["drop_50pct"] = df_latest["price_drop_rate"] <= -0.5

    # ─────────────────────────────
    # (D) 【ここから追加】前期の drop_30pct をマージ
    # ─────────────────────────────
    prev_flags = df_latest[["security_code", "year", "quarter", "drop_30pct"]].rename(
        columns={
            "year": "prev_year_val",
            "quarter": "prev_quarter_val",
            "drop_30pct": "prev_drop_30pct"
        }
    )
    df_latest = pd.merge(
        df_latest,
        prev_flags,
        how="left",
        left_on=["security_code", "prev_year_val", "prev_quarter_val"],
        right_on=["security_code", "prev_year_val", "prev_quarter_val"]
    )


    # ─────────────────────────────
    # (E) 判定結果を表示
    # ─────────────────────────────
    st.dataframe(
        df_latest[
            [
                "security_code", "security_name",
                "year", "quarter",
                "market_price", "prev_market_price",
                "price_drop_rate", "drop_30pct", "drop_50pct"
            ]
        ].sort_values(["security_code", "year", "quarter"]),
        use_container_width=True
    )

    conn = get_conn()

    # ─────────────────────────────
    # (E-2) 30％下落判定結果をDBに保存するボタン
    # ─────────────────────────────
    if st.button("30％下落判定結果をDBに保存", key="save_drop_30pct"):
        import datetime
        for _, row in df_latest.iterrows():
            code = row["security_code"]
            year = str(row["year"])
            quarter = row["quarter"]
            drop_30 = int(row["drop_30pct"])
            judged_at = datetime.datetime.now().isoformat(timespec="seconds")
            # 既存レコードがあればUPDATE、なければINSERT
            cur = conn.execute(
                "SELECT id FROM drop_judgement WHERE security_code=? AND year=? AND quarter=?",
                (code, year, quarter)
            )
            res = cur.fetchone()
            if res:
                conn.execute(
                    "UPDATE drop_judgement SET drop_30pct=?, judged_at=? WHERE id=?",
                    (drop_30, judged_at, res[0])
                )
            else:
                conn.execute(
                    "INSERT INTO drop_judgement (security_code, year, quarter, drop_30pct, judged_at) VALUES (?, ?, ?, ?, ?)",
                    (code, year, quarter, drop_30, judged_at)
                )
        conn.commit()
        st.success("30％下落判定結果をDBに保存しました。")



    # ─────────────────────────────
    # (F) 30%・50%下落または連続下落銘柄を表示（理由付き）
    # ─────────────────────────────
    # 「前期で30％連続下落」または「50％下落」のみを対象とするフィルタ
    df_drop = df_latest[
        (df_latest["drop_50pct"]) |
        ((df_latest["drop_30pct"]) & (df_latest["prev_drop_30pct"] == True))
    ].copy()

    def get_reason(row):
        # 50%下落が最優先
        if row["drop_50pct"]:
            return "50％下落"
        # 30%連続下落の場合
        if row["drop_30pct"] and row.get("prev_drop_30pct", False):
            return "連続下落"
        return ""

    df_drop["下落理由"] = df_drop.apply(get_reason, axis=1)

    st.markdown("#### 前期で30％連続下落または50％下落した銘柄一覧（理由付き）")
    st.dataframe(
        df_drop[
            [
                "security_code", "security_name",
                "year", "quarter",
                "market_price", "prev_market_price",
                "price_drop_rate", "下落理由"
            ]
        ].sort_values(["security_code", "year", "quarter"]),
        use_container_width=True
    )


    # ─────────────────────────────
    # (G) drop_judgementテーブルの内容を表示
    # ─────────────────────────────
    st.markdown("#### 30%下落判定結果（DB保存）")
    df_judge = pd.read_sql_query("SELECT * FROM drop_judgement", conn)
    st.dataframe(df_judge, use_container_width=True)