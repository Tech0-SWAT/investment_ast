# sale_result.py

from pathlib import Path
from datetime import date

import sqlite3
import pandas as pd
import streamlit as st

# ─────────────────────────────
# DB パスを決定
# ─────────────────────────────
DB = "../app.db"
db_path = (Path(__file__).resolve().parent / DB).resolve()

# ─────────────────────────────
# 1) DB から DataFrame を取得（security_name を含めるように変更）
# ─────────────────────────────
def load_transactions_with_security_name(db_file: Path) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(db_file)

        # 【変更】transactions テーブルから必要なカラムを取得
        #         transaction_id, security_id, created_at は後で表示しないので
        #         SELECT * のままでも構いませんが、ここでは明示的に必要カラムを指定します。
        df_txn = pd.read_sql_query(
            """
            SELECT
                t.txn_type,
                t.quantity,
                t.price,
                t.txn_date,
                t.security_id
                /* , t.created_at  ← もし created_at があるならここに追加できますが、後で削除します */
            FROM transactions AS t
            """,
            conn
        )

        # securities テーブルから security_id, security_code, security_name を取得
        df_sec = pd.read_sql_query(
            """
            SELECT
                security_id,
                security_code,
                security_name
            FROM securities
            """,
            conn
        )

        conn.close()

        # 【変更】security_id でマージし、「security_code」「security_name」を結合
        df = df_txn.merge(df_sec, on="security_id", how="left")

        # 万が一 security_code / security_name が欠損したら "不明" としておく（任意）
        df["security_code"] = df["security_code"].fillna("不明")
        df["security_name"] = df["security_name"].fillna("不明")

        # 【変更】不要な列を削除する
        #   - transaction_id（SELECT で省いている場合は不要ですが、念のため）
        #   - security_id（ID は使わない）
        #   - created_at（もし存在すれば削る）
        cols_to_drop = []
        if "transaction_id" in df.columns:
            cols_to_drop.append("transaction_id")
        if "security_id" in df.columns:
            cols_to_drop.append("security_id")
        if "created_at" in df.columns:
            cols_to_drop.append("created_at")
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        return df

    except Exception as e:
        st.error(f"DB からの読み込みに失敗しました: {e}")
        return pd.DataFrame()


# ─────────────────────────────
# 画面描画
# ─────────────────────────────
st.set_page_config(page_title="Sale Results", layout="wide")
st.title("📈 Sale Results（売買結果 一覧）")

# データ取得
df = load_transactions_with_security_name(db_path)
if df.empty:
    st.stop()

# ─────────────────────────────
# 2) 基本統計（必要であればここを編集）
# ─────────────────────────────
st.subheader("概要")
col1, col2, col3 = st.columns(3)

# 件数
col1.metric("件数", f"{len(df):,}")

# txn_date から最古・最新の日付を求め、文字列に変換して表示
oldest = pd.to_datetime(df["txn_date"]).min().date()
newest = pd.to_datetime(df["txn_date"]).max().date()
col2.metric("最古の取引日", oldest.strftime("%Y-%m-%d"))
col3.metric("最新の取引日", newest.strftime("%Y-%m-%d"))

# ─────────────────────────────
# 3) フィルタ（期間 & 銘柄コード）
# ─────────────────────────────
st.subheader("フィルタ")
min_d = pd.to_datetime(df["txn_date"]).min()
max_d = pd.to_datetime(df["txn_date"]).max()

start_date = st.date_input(
    "開始日",
    value=min_d.date(),
    min_value=min_d.date(),
    max_value=max_d.date()
)
end_date = st.date_input(
    "終了日",
    value=max_d.date(),
    min_value=max_d.date(),
    max_value=max_d.date()
)

# 「security_code（銘柄コード）」で選べるようにユニーク値を取得
codes = ["すべて"] + sorted(df["security_code"].dropna().unique().tolist())
sel_code = st.selectbox("銘柄コード（security_code）", codes)

# 期間フィルタと銘柄コードフィルタをマスクにまとめる
mask = pd.to_datetime(df["txn_date"]).dt.date.between(start_date, end_date)
if sel_code != "すべて":
    mask &= (df["security_code"] == sel_code)

# フィルタ後のデータを日付降順・銘柄コード昇順でソート
view = df.loc[mask].sort_values(
    by=["txn_date", "security_code"],
    ascending=[False, True]
)

# ─────────────────────────────
# 4) テーブル表示
# ─────────────────────────────
st.subheader("売買結果 一覧")
# DataFrame には以下のような列が含まれている想定です:
#   txn_type / quantity / price / txn_date / security_code / security_name
st.dataframe(view, use_container_width=True)

# ─────────────────────────────
# 5) CSV ダウンロード
# ─────────────────────────────
csv = view.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "CSV でダウンロード",
    data=csv,
    file_name="sale_results.csv",
    mime="text/csv"
)
