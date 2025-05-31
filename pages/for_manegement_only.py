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
    # 年・半期でソート
    df_latest = df_latest.sort_values(["security_code", "year", "half"])

    # 前期のmarket_priceを取得するために、銘柄・年・半期でシフト
    df_latest["year"] = df_latest["year"].astype(str)
    df_latest["prev_year"] = df_latest["year"].astype(int)
    df_latest["prev_half"] = df_latest["half"]

    # 前期の年・半期を計算
    def get_prev_period(row):
        y = int(row["year"])
        h = row["half"]
        if h == "H2":
            return y, "H1"
        else:
            return y - 1, "H2"
    prev_periods = df_latest.apply(get_prev_period, axis=1)
    df_latest["prev_year_val"] = [y for y, h in prev_periods]
    df_latest["prev_half_val"] = [h for y, h in prev_periods]

    # 型を揃える（prev_year_valをstr型に）
    df_latest["prev_year_val"] = df_latest["prev_year_val"].astype(str)

    # 前期のmarket_priceをマージ
    df_latest = pd.merge(
        df_latest,
        df_latest[["security_code", "year", "half", "market_price"]].rename(
            columns={
                "year": "prev_year_val",
                "half": "prev_half_val",
                "market_price": "prev_market_price"
            }
        ),
        how="left",
        left_on=["security_code", "prev_year_val", "prev_half_val"],
        right_on=["security_code", "prev_year_val", "prev_half_val"]
    )

    # 前期比下落率を計算
    df_latest["price_drop_rate"] = (
        (df_latest["market_price"] - df_latest["prev_market_price"]) / df_latest["prev_market_price"]
    )

    # 30%下落判定
    df_latest["drop_30pct"] = df_latest["price_drop_rate"] <= -0.3
    # 50%下落判定
    df_latest["drop_50pct"] = df_latest["price_drop_rate"] <= -0.5

    # 判定結果を表示
    st.dataframe(
        df_latest[
            [
                "security_code", "security_name", "year", "half",
                "market_price", "prev_market_price", "price_drop_rate",
                "drop_30pct", "drop_50pct"
            ]
        ].sort_values(["security_code", "year", "half"]),
        use_container_width=True
    )

    # --- 30%下落判定結果をdrop_judgementテーブルに保存（ボタンで実行） ---
    import datetime
    conn = get_conn()
    if st.button("30％下落判定結果をDBに保存", key="save_drop_30pct"):
        for _, row in df_latest.iterrows():
            # drop_30pctがTrue/Falseどちらも記録
            code = row["security_code"]
            year = str(row["year"])
            half = row["half"]
            drop_30 = int(row["drop_30pct"])
            judged_at = datetime.datetime.now().isoformat(timespec="seconds")
            # 既存レコードがあればUPDATE、なければINSERT
            cur = conn.execute(
                "SELECT id FROM drop_judgement WHERE security_code=? AND year=? AND half=?",
                (code, year, half)
            )
            res = cur.fetchone()
            if res:
                conn.execute(
                    "UPDATE drop_judgement SET drop_30pct=?, judged_at=? WHERE id=?",
                    (drop_30, judged_at, res[0])
                )
            else:
                conn.execute(
                    "INSERT INTO drop_judgement (security_code, year, half, drop_30pct, judged_at) VALUES (?, ?, ?, ?, ?)",
                    (code, year, half, drop_30, judged_at)
                )
        conn.commit()
        st.success("30％下落判定結果をDBに保存しました。")

    # --- 30%・50%下落銘柄を一つのテーブルで表示 ---
    df_drop = df_latest[(df_latest["drop_30pct"]) | (df_latest["drop_50pct"])].copy()
    def get_reason(row):
        if row["drop_50pct"]:
            return "50％下落"
        elif row["drop_30pct"]:
            return "30％下落"
        else:
            return ""
    df_drop["下落理由"] = df_drop.apply(get_reason, axis=1)
    st.markdown("#### 前期で30％または50％下落した銘柄一覧（理由付き）")
    st.dataframe(
        df_drop[
            [
                "security_code", "security_name", "year", "half",
                "market_price", "prev_market_price", "price_drop_rate", "下落理由"
            ]
        ].sort_values(["security_code", "year", "half"]),
        use_container_width=True
    )

    # --- drop_judgementテーブルの内容を表示 ---
    st.markdown("#### 30%下落判定結果（DB保存）")
    df_judge = pd.read_sql_query("SELECT * FROM drop_judgement", conn)
    st.dataframe(df_judge, use_container_width=True)
