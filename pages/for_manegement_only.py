# halfyear_input.py
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
# 2. 既存 securities / positions_halfyear 一覧
# ─────────────────────────────
@st.cache_data(ttl=600)
def load_securities():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT security_id, security_code, security_name FROM securities", conn
    )
    return df

@st.cache_data(ttl=600)
def load_positions_halfyear():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM positions_halfyear", conn)
    return df

# ─────────────────────────────
# 3. 画面レイアウト
# ─────────────────────────────
st.set_page_config(page_title="半年集計マスタ編集", layout="wide")
st.title("🗓️ 半期集計（positions_halfyear）入力")

df_securities = load_securities()
codes = df_securities["security_code"].tolist()

# ─────────────────────────────
# 3-A  登録／上書きフォーム
# ─────────────────────────────
with st.form("halfyear_form", clear_on_submit=False):
    sel_code = st.selectbox("銘柄コード", codes)
    sec_row  = df_securities[df_securities["security_code"] == sel_code].iloc[0]
    security_id   = int(sec_row["security_id"])
    security_name = sec_row["security_name"]

    today_y = date.today().year
    year_in  = st.number_input("対象年 (YYYY)", min_value=2000, max_value=today_y+1,
                               value=today_y, step=1)
    half_in  = st.radio("半期", ("H1", "H2"), horizontal=True)

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
            INSERT INTO positions_halfyear
                (security_id, d365_code, security_code, security_name,
                 year, half, holding_qty, avg_cost, market_price, market_cap)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(security_id, year, half)
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
                half_in,
                qty_in,
                cost_in,
                price_in,
                market_cap,
            )
        )
        conn.commit()
        st.success("登録 / 更新が完了しました ✅")
        load_positions_halfyear.clear()
    except Exception as e:
        st.error(f"登録失敗: {e}")

# ─────────────────────────────
# 3-B  削除 GUI
# ─────────────────────────────
st.markdown("---")
st.subheader("🗑️ 行を削除")

df_ph = load_positions_halfyear()
if df_ph.empty:
    st.info("positions_halfyear にまだデータがありません。")
else:
    # 表示用キーを生成 例: 7203 | 2024 H2
    df_ph["row_key"] = (df_ph["security_code"] + " | " +
                        df_ph["year"] + " " + df_ph["half"])
    del_key = st.selectbox("削除対象を選択", df_ph["row_key"].tolist())

    if st.button("選択した行を削除", key="delete_button"):
        try:
            # 選択キーから行を特定
            target = df_ph[df_ph["row_key"] == del_key].iloc[0]
            conn   = get_conn()
            conn.execute(
                """
                DELETE FROM positions_halfyear
                WHERE security_id = ? AND year = ? AND half = ?
                """,
                (int(target["security_id"]), target["year"], target["half"])
            )
            conn.commit()
            st.success(f"削除しました: {del_key}")
            load_positions_halfyear.clear()  # キャッシュ更新
        except Exception as e:
            st.error(f"削除失敗: {e}")

# ─────────────────────────────
# 4. 一覧表示
# ─────────────────────────────
st.markdown("---")
st.subheader("現在登録されている半期データ")
df_latest = load_positions_halfyear()
if df_latest.empty:
    st.info("まだデータがありません。")
else:
    st.dataframe(
        df_latest.sort_values(["security_code", "year", "half"]),
        use_container_width=True
    )
