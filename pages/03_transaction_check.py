# transaction_check.py
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

def load_transactions_with_security_code(db_file: Path) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(db_file)
        df_txn = pd.read_sql_query("SELECT * FROM transactions", conn)
        df_sec = pd.read_sql_query(
            "SELECT security_id, security_code FROM securities",
            conn
        )

        conn.close()

        # ③ security_id でマージし、「security_code」列を結合
        df = df_txn.merge(df_sec, on="security_id", how="left")

        # マージ結果として security_code が欠損するケースがあれば埋める（例: 未登録時は "不明"）
        df["security_code"] = df["security_code"].fillna("不明")

        return df

    except Exception as e:
        st.error(f"DB からの読み込みに失敗しました: {e}")
        return pd.DataFrame()

# ─────────────────────────────
# Streamlit UI
# ─────────────────────────────
st.set_page_config(page_title="取引チェック（開発用）", layout="wide")
st.title("🛠️ 取引トランザクション確認（銘柄コード付き）")

# 3-1. データ取得（結合済みの DataFrame を返す関数を呼ぶ）
df = load_transactions_with_security_code(db_path)
if df.empty:
    st.stop()

# 3-2. 基本統計（txn_date を文字列に変換して st.metric に渡す）
st.subheader("概要")
col1, col2, col3 = st.columns(3)

# 件数
col1.metric("件数", f"{len(df):,}")

# txn_date から最古・最新の日付を求め、文字列に変換して表示
oldest = pd.to_datetime(df["txn_date"]).min().date()
newest = pd.to_datetime(df["txn_date"]).max().date()
col2.metric("最古の取引日", oldest.strftime("%Y-%m-%d"))
col3.metric("最新の取引日", newest.strftime("%Y-%m-%d"))

# 3-3. フィルタ（期間 & 銘柄コード）
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

# フィルタ後のデータを日付降順にソート
view = df.loc[mask].sort_values("txn_date", ascending=False)

# 3-4. テーブル表示
st.subheader("トランザクション一覧")
# DataFrame には以下のような列が含まれている想定です:
#   transaction_id / security_id / txn_type / quantity / price / txn_date / security_code
st.dataframe(view, use_container_width=True)

# 3-5. CSV ダウンロード
csv = view.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "CSV でダウンロード",
    data=csv,
    file_name="transactions_with_security_code.csv",
    mime="text/csv"
)
