# get_prices.py
from pathlib import Path
from datetime import date
import sqlite3

import streamlit as st
import pandas as pd
import yfinance as yf

# ──────────────────────────────────────────
# 0) 設定：DB のパスを決定
# ──────────────────────────────────────────
DB = "../app.db"
db_path = (Path(__file__).resolve().parent / DB).resolve()

# ──────────────────────────────────────────
# 1) SQLite から接続を取得する関数
# ──────────────────────────────────────────
@st.cache_resource
def get_conn():
    """
    DB に接続し、foreign_keys を有効化したコネクションを返す。
    Streamlit セッション中は同じ接続を使いまわす。
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ──────────────────────────────────────────
# 2) 当日の価格データ登録状況を取得する関数
# ──────────────────────────────────────────
def load_today_quotes_ids() -> set[int]:
    """
    今日の日付で price_quotes に登録されている security_id のセットを返す。
    get_conn() を使って内部で接続を取得するため、
    引数に conn を受け取らなくてもよい。
    """
    conn = get_conn()
    today_str = date.today().isoformat()
    query = """
        SELECT security_id
        FROM price_quotes
        WHERE quote_date = ?
    """
    df = pd.read_sql_query(query, conn, params=(today_str,))
    return set(df["security_id"].tolist())

# ──────────────────────────────────────────
# 3) 全銘柄一覧を取得する関数
# ──────────────────────────────────────────
# @st.cache_data(ttl=600, show_spinner="銘柄一覧を読み込み中…")
def load_securities() -> pd.DataFrame:
    """
    securities テーブルから (security_id, security_code, security_name) を読み込んで返す。
    中で get_conn() を呼び出すので引数は不要。
    """
    conn = get_conn()
    query = """
        SELECT security_id, security_code, security_name
        FROM securities
        ORDER BY security_code
    """
    df = pd.read_sql_query(query, conn)
    return df

# ──────────────────────────────────────────
# 4) yfinance で当日終値を取得する関数
# ──────────────────────────────────────────
# @st.cache_data(ttl=900, show_spinner="最新株価を取得中…")
def fetch_price_yfinance(code: str) -> float | None:
    tk = code if "." in code else f"{code}.T"
    try:
        # 直近 5 日で取得してみる
        df = yf.download(
            tk, period="5d", interval="1d",
            progress=False, threads=False, auto_adjust=False
        )
        # データが無ければ None
        if df.empty or df["Close"].dropna().empty:
            return None
        return float(df["Close"].dropna().iloc[-1])
    except Exception:
        return None

# ──────────────────────────────────────────
# 5) Streamlit 画面の構築
# ──────────────────────────────────────────
st.set_page_config(page_title="価格取得 (Get Prices)", layout="wide")
st.title("🔄 最新株価の取得と price_quotes テーブル更新")

# 1) securities テーブルから全銘柄一覧を取得
df_securities = load_securities()

if df_securities.empty:
    st.error("securities テーブルに銘柄が登録されていません。まず銘柄マスターを登録してください。")
    st.stop()

# 2) 今日の price_quotes に登録済みの security_id を取得
today_ids = load_today_quotes_ids()

# 3) サイドバーに「今日の日付」と「テーブルの状態」を表示
today_str = date.today().strftime("%Y-%m-%d")
st.sidebar.markdown(f"**今日の日付:** {today_str}")
st.sidebar.markdown(f"- price_quotes に登録済みの銘柄数: **{len(today_ids)} 件**")

st.markdown("---")

# 4) メイン領域で、銘柄一覧をテーブル表示し、登録有無を示す
st.subheader("銘柄一覧と price_quotes 登録状況")

df_display = df_securities.copy()
df_display["has_price"] = df_display["security_id"].apply(lambda i: "○" if i in today_ids else "×")
df_display = df_display.rename(columns={
    "security_code": "コード",
    "security_name": "銘柄名",
    "has_price": "今日の登録有無"
})
st.dataframe(df_display, use_container_width=True)

st.markdown("---")

# 5) 「登録されていない銘柄」に対して価格取得ボタンを用意
st.subheader("未登録銘柄の価格を取得して price_quotes に追加")

df_not_registered = df_securities[df_securities["security_id"].apply(lambda i: i not in today_ids)]

if df_not_registered.empty:
    st.success("今日未登録の銘柄はありません。すべて登録済みです。")
else:
    st.write(f"未登録銘柄数: {len(df_not_registered)} 件")
    for idx, row in df_not_registered.iterrows():
        sec_id   = row["security_id"]
        code     = row["security_code"]
        name     = row["security_name"]
        button_key = f"fetch_{sec_id}"

        col1, col2, col3 = st.columns([2, 4, 2])
        with col1:
            st.write(f"**{code}** {name}")
        with col2:
            st.write("未登録")
        with col3:
            # 「価格取得」ボタン
            if st.button("価格取得", key=button_key):
                with st.spinner(f"{code} の価格を yfinance から取得中…"):
                    price = fetch_price_yfinance(code)

                if price is None:
                    st.error(f"{code} の株価取得に失敗しました。")
                else:
                    quote_date = date.today().isoformat()
                    conn = get_conn()
                    try:
                        conn.execute(
                            "INSERT INTO price_quotes (quote_date, security_id, close_price) VALUES (?, ?, ?)",
                            (quote_date, sec_id, price)
                        )
                        conn.commit()
                        st.success(f"{code} を price_quotes に追加しました → {price} 円")
                    except sqlite3.IntegrityError:
                        st.warning(f"{code} は既に今日のデータが登録されています。")
                    except Exception as e:
                        st.error(f"登録中にエラーが発生しました: {e}")

                    # 登録後に画面をリロードしてテーブルを更新
                    st.rerun()

st.markdown("---")

# 登録済み銘柄の CSV ダウンロード
st.subheader("今日登録された price_quotes 一覧 (CSV ダウンロード)")

conn = get_conn()
today_quote_df = pd.read_sql_query(
    """
    SELECT
        pq.security_id,
        s.security_code,
        s.security_name,
        pq.close_price
    FROM price_quotes pq
    JOIN securities s ON pq.security_id = s.security_id
    WHERE pq.quote_date = ?
    """,
    conn,
    params=(today_str,)
)

if today_quote_df.empty:
    st.info("今日の price_quotes データはまだありません。")
else:
    # SQL で取得済みなので、そのまま列を指定する
    today_quote_df = today_quote_df[
        ["security_code", "security_name", "close_price"]
    ]
    st.dataframe(today_quote_df, use_container_width=True)

    csv = today_quote_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 今日の price_quotes を CSV ダウンロード",
        data=csv,
        file_name=f"price_quotes_{today_str}.csv",
        mime="text/csv"
    )