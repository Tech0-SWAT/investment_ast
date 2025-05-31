# # investment_performance.py

# from pathlib import Path
# from datetime import date, datetime

# import sqlite3
# import pandas as pd
# import streamlit as st

# # ─────────────────────────────
# # DB パスを決定
# # ─────────────────────────────
# DB = "app.db"
# db_path = (Path(__file__).resolve().parent / DB).resolve()

# # ─────────────────────────────
# # 1) 今日の日付を取得し、前期（year, half）と当期の開始日を決める関数
# # ─────────────────────────────
# def determine_periods(today: date):
#     year = today.year
#     month = today.month

#     if month <= 6:
#         # 当期は H1 → 前期は 前年 H2
#         prev_year = year - 1
#         prev_half = "H2"
#         current_start = date(year, 1, 1)
#     else:
#         # 当期は H2 → 前期は 同年 H1
#         prev_year = year
#         prev_half = "H1"
#         current_start = date(year, 7, 1)

#     return prev_year, prev_half, current_start, today

# # ─────────────────────────────
# # 2) SQLite から必要な DataFrame を取得する関数
# # ─────────────────────────────
# # @st.cache_data(show_spinner="データ読込中...")
# def load_positions_halfyear(db_file: Path, prev_year: str, prev_half: str) -> pd.DataFrame:
#     """
#     前期の positions_halfyear テーブルを読み込む。
#     テーブルが空でも空の DataFrame を返す想定。
#     """
#     conn = sqlite3.connect(db_file)
#     query = """
#         SELECT
#             security_code,
#             security_name,
#             holding_qty   AS prev_holding_qty,
#             avg_cost      AS prev_avg_cost
#         FROM positions_halfyear
#         WHERE year = ? AND half = ?
#     """
#     df_prev = pd.read_sql_query(query, conn, params=(str(prev_year), prev_half))
#     conn.close()
#     if df_prev.empty:
#         # 空の DataFrame を security_code をインデックスにして返す
#         return pd.DataFrame(columns=["security_name", "prev_holding_qty", "prev_avg_cost"]).set_index("security_code")
#     return df_prev.set_index("security_code")

# @st.cache_data(show_spinner="データ読込中...")
# def load_transactions_period(db_file: Path, start_date: date, end_date: date) -> pd.DataFrame:
#     """
#     当期の取引（transactions）を取得し、security_code, txn_type, quantity, price, txn_date を返す。
#     期間内に取引がない場合は空の DataFrame を返す。
#     """
#     conn = sqlite3.connect(db_file)
#     query = """
#         SELECT
#             t.txn_type,
#             t.quantity,
#             t.price,
#             t.txn_date,
#             s.security_code,
#             s.security_name
#         FROM transactions AS t
#         JOIN securities AS s
#           ON t.security_id = s.security_id
#         WHERE DATE(t.txn_date) BETWEEN DATE(?) AND DATE(?)
#         ORDER BY DATE(t.txn_date) ASC
#     """
#     df_txn = pd.read_sql_query(query, conn, params=(start_date.isoformat(), end_date.isoformat()))
#     conn.close()

#     if df_txn.empty:
#         return pd.DataFrame(columns=["txn_type", "quantity", "price", "txn_date", "security_code", "security_name"])
#     df_txn["txn_date"] = pd.to_datetime(df_txn["txn_date"]).dt.date
#     return df_txn

# # ─────────────────────────────
# # 画面描画
# # ─────────────────────────────
# st.set_page_config(page_title="Investment Performance", layout="wide")
# st.title("📊 投資状況パフォーマンス")

# # 今日の日付を取得
# today = date.today()
# st.write(f"**今日の日付:** {today.strftime('%Y-%m-%d')}")

# # 前期と当期開始日を決定
# prev_year, prev_half, current_start, current_end = determine_periods(today)
# st.write(f"**前期:** {prev_year} 年 {prev_half}")
# st.write(f"**当期開始日:** {current_start.strftime('%Y-%m-%d')} 〜 **本日:** {current_end.strftime('%Y-%m-%d')}")

# # ─────────────────────────────
# # 3) 前期のデータを読み込む
# # ─────────────────────────────
# df_prev = load_positions_halfyear(db_path, prev_year, prev_half)

# if df_prev.empty:
#     st.info("前期のデータが存在しません。前期はすべてゼロ扱いで計算します。")

# # ─────────────────────────────
# # 4) 当期の取引を取得する
# # ─────────────────────────────
# df_txn = load_transactions_period(db_path, current_start, current_end)

# if df_txn.empty:
#     st.info("当期の取引がありません。最新データは前期と同じになります。")

# # ─────────────────────────────
# # 5) 各銘柄ごとに計算する
# # ─────────────────────────────
# results = []

# # 前期に存在した銘柄のリスト
# prev_codes = set(df_prev.index.tolist())
# # 当期に取引がある銘柄のリスト
# current_codes = set(df_txn["security_code"].unique().tolist())
# # 計算対象とする銘柄コードのユニオン
# all_codes = prev_codes.union(current_codes)

# for code in sorted(all_codes):
#     # 銘柄名：前期にあれば df_prev から、それ以外は df_txn から取得
#     if code in df_prev.index:
#         security_name = df_prev.loc[code, "security_name"]
#     else:
#         security_name = df_txn.loc[df_txn["security_code"] == code, "security_name"].iloc[0]

#     # 前期の株数・平均単価・コストベースを取得
#     if code in df_prev.index:
#         prev_qty = df_prev.loc[code, "prev_holding_qty"]
#         prev_avg_cost = df_prev.loc[code, "prev_avg_cost"]
#         prev_cost_basis = prev_qty * prev_avg_cost
#     else:
#         prev_qty = 0.0
#         prev_avg_cost = 0.0
#         prev_cost_basis = 0.0

#     # 当期の取引だけを抽出
#     df_sec_txn = df_txn[df_txn["security_code"] == code].copy()

#     # 当期の初時点をベースに初期コストと株数をセット
#     cost_basis = prev_cost_basis
#     qty = prev_qty

#     # 当期取引を日付昇順でループ
#     for _, row in df_sec_txn.iterrows():
#         txn_type = row["txn_type"]
#         trade_qty = row["quantity"]
#         trade_price = row["price"]

#         if txn_type == "BUY":
#             cost_basis += trade_qty * trade_price
#             qty += trade_qty
#         elif txn_type == "SEL":
#             cost_basis -= trade_qty * trade_price
#             qty -= trade_qty

#     # 当期末（本日時点）の株数・コストベースを元に平均取得単価を計算
#     if qty != 0:
#         latest_avg_cost = cost_basis / qty
#     else:
#         latest_avg_cost = 0.0

#     latest_qty = qty
#     latest_cost_basis = cost_basis  # これを「最新の時価総額」とみなす

#     # 前期と当期末を比較して出力用データを作成
#     if prev_avg_cost != 0:
#         ratio = latest_qty / prev_avg_cost
#     else:
#         ratio = None

#     results.append({
#         "security_code":      code,
#         "security_name":      security_name,
#         "prev_holding_qty":   prev_qty,
#         "prev_avg_cost":      prev_avg_cost,
#         "prev_cost_basis":    prev_cost_basis,
#         "latest_holding_qty": latest_qty,
#         "latest_avg_cost":    latest_avg_cost,
#         "latest_cost_basis":  latest_cost_basis,
#         "ratio_qty_to_cost":  ratio
#     })

# df_result = pd.DataFrame(results)

# # ─────────────────────────────
# # 6) 画面にテーブル表示
# # ─────────────────────────────
# st.subheader("投資成績サマリー")
# st.dataframe(
#     df_result[[
#         "security_code",
#         "security_name",
#         "prev_holding_qty",
#         "prev_avg_cost",
#         "prev_cost_basis",
#         "latest_holding_qty",
#         "latest_avg_cost",
#         "latest_cost_basis",
#         "ratio_qty_to_cost"
#     ]],
#     use_container_width=True
# )

# # ─────────────────────────────
# # 7) CSV ダウンロード
# # ─────────────────────────────
# csv = df_result.to_csv(index=False).encode("utf-8-sig")
# st.download_button(
#     "CSV でダウンロード",
#     data=csv,
#     file_name="investment_performance.csv",
#     mime="text/csv"
# )




# # investment_performance.py
# # ---------------------------------------------
# # 前期と当期末の平均取得単価を比較し、
# # 含み損益も計算して表示・CSV ダウンロードする Streamlit アプリ
# # ---------------------------------------------
# from pathlib import Path
# from datetime import date

# import sqlite3
# import pandas as pd
# import streamlit as st

# # ---------------------------------------------
# # DB パス
# # ---------------------------------------------
# DB = "app.db"
# db_path = (Path(__file__).resolve().parent / DB).resolve()

# # ---------------------------------------------
# # 1) 期区分を求めるユーティリティ
# # ---------------------------------------------
# def determine_periods(today: date):
#     """今日が H1 or H2 かで『前期』を決定し、当期の開始日を返す。"""
#     year = today.year
#     month = today.month

#     if month <= 6:                       # 1〜6 月 → 当期 H1
#         prev_year, prev_half = year - 1, "H2"
#         current_start = date(year, 1, 1)
#     else:                                # 7〜12 月 → 当期 H2
#         prev_year, prev_half = year, "H1"
#         current_start = date(year, 7, 1)

#     return prev_year, prev_half, current_start, today

# # ---------------------------------------------
# # 2) DB 読込関数群
# # ---------------------------------------------
# @st.cache_data(ttl=600, show_spinner="前期データ読込中…")
# def load_positions_halfyear(db_file: Path, prev_year: str, prev_half: str) -> pd.DataFrame:
#     """前期 positions_halfyear を読み込む。空なら空 DF を返す。"""
#     q = """
#         SELECT
#             security_code,
#             security_name,
#             holding_qty   AS prev_holding_qty,
#             avg_cost      AS prev_avg_cost
#         FROM positions_halfyear
#         WHERE year = ? AND half = ?
#     """
#     with sqlite3.connect(db_file) as conn:
#         df = pd.read_sql_query(q, conn, params=(str(prev_year), prev_half))

#     if df.empty:
#         cols = ["security_name", "prev_holding_qty", "prev_avg_cost"]
#         return pd.DataFrame(columns=cols, index=pd.Index([], name="security_code"))
#     return df.set_index("security_code")

# @st.cache_data(ttl=600, show_spinner="当期取引読込中…")
# def load_transactions_period(db_file: Path, start_date: date, end_date: date) -> pd.DataFrame:
#     """当期の取引 transactions を読込む。"""
#     q = """
#         SELECT
#             t.txn_type, t.quantity, t.price, DATE(t.txn_date) AS txn_date,
#             s.security_code, s.security_name
#         FROM transactions AS t
#         JOIN securities AS s ON t.security_id = s.security_id
#         WHERE DATE(t.txn_date) BETWEEN DATE(?) AND DATE(?)
#         ORDER BY DATE(t.txn_date)
#     """
#     with sqlite3.connect(db_file) as conn:
#         df = pd.read_sql_query(q, conn, params=(start_date.isoformat(), end_date.isoformat()))

#     if df.empty:
#         cols = ["txn_type", "quantity", "price", "txn_date", "security_code", "security_name"]
#         return pd.DataFrame(columns=cols)
#     df["txn_date"] = pd.to_datetime(df["txn_date"]).dt.date
#     return df

# @st.cache_data(ttl=600, show_spinner="最新株価読込中…")
# def load_latest_prices(db_file: Path) -> dict:
#     """
#     latest_prices ビューと securities を JOIN し
#     { security_code: market_price } の dict を返す。
#     """
#     q = """
#         SELECT s.security_code, lp.market_price
#         FROM latest_prices lp
#         JOIN securities s ON lp.security_id = s.security_id
#     """
#     with sqlite3.connect(db_file) as conn:
#         df = pd.read_sql_query(q, conn)
#     return dict(zip(df["security_code"], df["market_price"]))

# # ---------------------------------------------
# # 3) 画面レイアウト
# # ---------------------------------------------
# st.set_page_config(page_title="Investment Performance", layout="wide")
# st.title("📊 投資パフォーマンス（前期 vs 当期末）")

# today = date.today()
# st.write(f"**今日:** {today:%Y-%m-%d}")

# prev_year, prev_half, current_start, current_end = determine_periods(today)
# st.write(f"**前期:** {prev_year} {prev_half}　|　**当期:** {current_start:%Y-%m-%d} 〜 {current_end:%Y-%m-%d}")

# # ---------------------------------------------
# # 4) データ読込
# # ---------------------------------------------
# df_prev = load_positions_halfyear(db_path, prev_year, prev_half)
# df_txn  = load_transactions_period(db_path, current_start, current_end)
# price_map = load_latest_prices(db_path)

# if df_prev.empty:
#     st.info("前期 positions_halfyear にデータが無いため、前期はゼロで計算します。")
# if df_txn.empty:
#     st.info("当期はまだ取引がありません。")

# # ---------------------------------------------
# # 5) 指標計算
# # ---------------------------------------------
# prev_codes    = set(df_prev.index)
# current_codes = set(df_txn["security_code"].unique())
# all_codes     = prev_codes.union(current_codes)

# results = []

# for code in sorted(all_codes):
#     # 銘柄名
#     if code in df_prev.index:
#         sec_name = df_prev.loc[code, "security_name"]
#     else:
#         sec_name = df_txn.loc[df_txn["security_code"] == code, "security_name"].iloc[0]

#     # --- 前期末 ---
#     prev_qty       = df_prev.loc[code, "prev_holding_qty"] if code in prev_codes else 0.0
#     prev_avg_cost  = df_prev.loc[code, "prev_avg_cost"]    if code in prev_codes else 0.0
#     prev_cost_basis = prev_qty * prev_avg_cost

#     # --- 当期取引反映 ---
#     df_sec = df_txn[df_txn["security_code"] == code]
#     qty, cost_basis = prev_qty, prev_cost_basis

#     for _, row in df_sec.iterrows():
#         if row["txn_type"] == "BUY":
#             cost_basis += row["quantity"] * row["price"]
#             qty        += row["quantity"]
#         elif row["txn_type"] == "SEL":
#             cost_basis -= row["quantity"] * row["price"]
#             qty        -= row["quantity"]

#     latest_qty      = qty
#     latest_avg_cost = cost_basis / qty if qty != 0 else 0.0

#     # --- 指標 ---
#     pct_change = (
#         (latest_avg_cost - prev_avg_cost) / prev_avg_cost * 100
#         if prev_avg_cost else None
#     )
#     current_price = price_map.get(code)
#     unrealized_pl = (
#         (current_price - latest_avg_cost) * latest_qty
#         if current_price is not None else None
#     )

#     results.append({
#         "security_code":       code,
#         "security_name":       sec_name,
#         "prev_avg_cost":       prev_avg_cost,
#         "latest_avg_cost":     latest_avg_cost,
#         "pct_change_%":        pct_change,
#         "latest_holding_qty":  latest_qty,
#         "current_price":       current_price,
#         "unrealized_PL":       unrealized_pl
#     })

# df_result = pd.DataFrame(results)

# # ---------------------------------------------
# # 6) 画面表示
# # ---------------------------------------------
# st.subheader("投資成績サマリー")
# show_cols = [
#     "security_code", "security_name",
#     "prev_avg_cost", "latest_avg_cost", "pct_change_%",
#     "latest_holding_qty", "current_price", "unrealized_PL"
# ]
# st.dataframe(df_result[show_cols], use_container_width=True)

# # ---------------------------------------------
# # 7) CSV ダウンロード
# # ---------------------------------------------
# csv = df_result.to_csv(index=False).encode("utf-8-sig")
# st.download_button(
#     label="📥 CSV でダウンロード",
#     data=csv,
#     file_name="investment_performance.csv",
#     mime="text/csv"
# )


# investment_performance.py
# ------------------------------------------------------
# 前期と当期末の平均取得単価を比較し、含み損益を算出する Streamlit アプリ
# 最新株価 (current_price) は yfinance API で取得
# ------------------------------------------------------
from pathlib import Path
from datetime import date
import sqlite3
import pandas as pd
import streamlit as st
import yfinance as yf   # ★ 追加

# ------------------------------------------------------
# DB パス
# ------------------------------------------------------
DB = "app.db"
db_path = (Path(__file__).resolve().parent / DB).resolve()

# ------------------------------------------------------
# 1) 期区分ユーティリティ
# ------------------------------------------------------
def determine_periods(today: date):
    year, month = today.year, today.month
    if month <= 6:                                   # 当期 H1
        return year - 1, "H2", date(year, 1, 1), today
    else:                                            # 当期 H2
        return year, "H1", date(year, 7, 1), today

# ------------------------------------------------------
# 2) DB 読込関数
# ------------------------------------------------------
@st.cache_data(ttl=600, show_spinner="前期データ読込中…")
def load_positions_halfyear(db_file: Path, prev_year: str, prev_half: str) -> pd.DataFrame:
    q = """
        SELECT security_code, security_name,
               holding_qty AS prev_holding_qty,
               avg_cost    AS prev_avg_cost
        FROM positions_halfyear
        WHERE year = ? AND half = ?
    """
    with sqlite3.connect(db_file) as conn:
        df = pd.read_sql_query(q, conn, params=(str(prev_year), prev_half))
    if df.empty:
        cols = ["security_name", "prev_holding_qty", "prev_avg_cost"]
        return pd.DataFrame(columns=cols, index=pd.Index([], name="security_code"))
    return df.set_index("security_code")

@st.cache_data(ttl=600, show_spinner="当期取引読込中…")
def load_transactions_period(db_file: Path, start_date: date, end_date: date) -> pd.DataFrame:
    q = """
        SELECT t.txn_type, t.quantity, t.price, DATE(t.txn_date) AS txn_date,
               s.security_code, s.security_name
        FROM transactions t
        JOIN securities s ON t.security_id = s.security_id
        WHERE DATE(t.txn_date) BETWEEN DATE(?) AND DATE(?)
        ORDER BY DATE(t.txn_date)
    """
    with sqlite3.connect(db_file) as conn:
        df = pd.read_sql_query(q, conn, params=(start_date.isoformat(), end_date.isoformat()))
    if df.empty:
        cols = ["txn_type", "quantity", "price", "txn_date", "security_code", "security_name"]
        return pd.DataFrame(columns=cols)
    df["txn_date"] = pd.to_datetime(df["txn_date"]).dt.date
    return df

# ------------------------------------------------------
# 3) 最新株価を API で取得
# ------------------------------------------------------
# @st.cache_data(ttl=900, show_spinner="最新株価取得中…")
def fetch_current_prices(codes: list[str]) -> dict[str, float]:
    """
    Yahoo Finance API から最新終値を取得。
    日本株コード（7203 など）は自動で '.T' を付与して呼び出す。
    戻り値: { '7203': 3075.5, ... }
    """
    if not codes:
        return {}

    # yfinance のティッカー表現に変換
    tickers = []
    code_map = {}  # yf ティッカー → 元コード
    for c in codes:
        yf_code = c if "." in c else f"{c}.T"
        tickers.append(yf_code)
        code_map[yf_code] = c

    # download は複数ティッカーでも一括取得できる
    data = yf.download(
        tickers=" ".join(tickers),
        period="1d", interval="1d",
        auto_adjust=False, progress=False, threads=True
    )

    price_dict = {}
    # download の戻りは MultiIndex（ティッカー, OHLCV）
    if isinstance(data.columns, pd.MultiIndex):
        for yf_code in tickers:
            try:
                price = data[yf_code]["Close"].dropna().iloc[-1]
                price_dict[code_map[yf_code]] = float(price)
            except Exception:
                continue
    else:  # 1 銘柄のみ
        price = data["Close"].dropna().iloc[-1]
        yf_code = tickers[0]
        price_dict[code_map[yf_code]] = float(price)

    return price_dict

# ------------------------------------------------------
# 4) 画面レイアウト
# ------------------------------------------------------
st.set_page_config(page_title="Investment Performance", layout="wide")
st.title("📊 投資パフォーマンス（前期 vs 当期末）")

today = date.today()
st.write(f"**今日:** {today:%Y-%m-%d}")

prev_year, prev_half, current_start, current_end = determine_periods(today)
st.write(f"**前期:** {prev_year} {prev_half}　|　**当期:** {current_start:%Y-%m-%d} 〜 {current_end:%Y-%m-%d}")

# ------------------------------------------------------
# 5) データ取得
# ------------------------------------------------------
df_prev = load_positions_halfyear(db_path, prev_year, prev_half)
df_txn  = load_transactions_period(db_path, current_start, current_end)

prev_codes    = set(df_prev.index)
current_codes = set(df_txn["security_code"].unique())
all_codes     = sorted(prev_codes.union(current_codes))

# ★ API から最新株価を取得
price_map = fetch_current_prices(all_codes)

if df_prev.empty:
    st.info("前期 positions_halfyear にデータが無いため、前期はゼロとして計算します。")
if df_txn.empty:
    st.info("当期はまだ取引がありません。")
if not price_map:
    st.warning("最新株価を取得できませんでした。API レート制限やネットワークを確認してください。")

# ------------------------------------------------------
# 6) 指標計算
# ------------------------------------------------------
results = []

for code in all_codes:
    # 銘柄名
    if code in df_prev.index:
        sec_name = df_prev.loc[code, "security_name"]
    else:
        sec_name = df_txn.loc[df_txn["security_code"] == code, "security_name"].iloc[0]

    # --- 前期 ---
    prev_qty       = df_prev.loc[code, "prev_holding_qty"] if code in prev_codes else 0.0
    prev_avg_cost  = df_prev.loc[code, "prev_avg_cost"]    if code in prev_codes else 0.0
    prev_cost_basis = prev_qty * prev_avg_cost

    # --- 当期取引を反映 ---
    df_sec = df_txn[df_txn["security_code"] == code]
    qty, cost_basis = prev_qty, prev_cost_basis
    for _, row in df_sec.iterrows():
        if row["txn_type"] == "BUY":
            cost_basis += row["quantity"] * row["price"]
            qty        += row["quantity"]
        elif row["txn_type"] == "SEL":
            # 移動平均法で原価を減算
            avg_cost_before = cost_basis / qty if qty else 0
            cost_basis -= row["quantity"] * avg_cost_before
            qty        -= row["quantity"]

    latest_qty      = qty
    latest_avg_cost = cost_basis / qty if qty else 0.0

    # --- 指標 ---
    pct_change = (
        (latest_avg_cost - prev_avg_cost) / prev_avg_cost * 100
        if prev_avg_cost else None
    )
    current_price = price_map.get(code)
    unrealized_pl = (
        (current_price - latest_avg_cost) * latest_qty
        if current_price is not None else None
    )

    results.append({
        "security_code":       code,
        "security_name":       sec_name,
        "prev_avg_cost":       prev_avg_cost,
        "latest_avg_cost":     latest_avg_cost,
        "pct_change_%":        pct_change,
        "latest_holding_qty":  latest_qty,
        "current_price":       current_price,
        "unrealized_PL":       unrealized_pl
    })

df_result = pd.DataFrame(results)

# ------------------------------------------------------
# 7) 表示
# ------------------------------------------------------
st.subheader("投資成績サマリー")
show_cols = [
    "security_code", "security_name",
    "prev_avg_cost", "latest_avg_cost", "pct_change_%",
    "latest_holding_qty", "current_price", "unrealized_PL"
]
st.dataframe(df_result[show_cols], use_container_width=True)

# ------------------------------------------------------
# 8) CSV ダウンロード
# ------------------------------------------------------
csv = df_result.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="📥 CSV でダウンロード",
    data=csv,
    file_name="investment_performance.csv",
    mime="text/csv"
)
