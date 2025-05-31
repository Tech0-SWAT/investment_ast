import sqlite3
import yfinance as yf
from datetime import date
import streamlit as st
from pathlib import Path

# --------------------------------------------------
# 1) DB ファイルのパスを定義
# --------------------------------------------------
DB = "../app.db"
db_path = (Path(__file__).resolve().parent / DB).resolve()

# --------------------------------------------------
# 2) セッションステートの初期化
# --------------------------------------------------
if "stage" not in st.session_state:
    st.session_state.stage = "input"

if "code" not in st.session_state:
    st.session_state.code = ""

# 「fetch() から返ってきた情報」を保存するためのキー
if "info" not in st.session_state:
    st.session_state.info = None

# 取引フォーム用のデフォルト値
if "txn_type" not in st.session_state:
    st.session_state.txn_type = "BUY"
if "qty" not in st.session_state:
    st.session_state.qty = 100.0
if "price" not in st.session_state:
    st.session_state.price = 0.0

# 取引日だけをセッションステートで管理する
if "txn_date" not in st.session_state:
    st.session_state.txn_date = date.today()

# --------------------------------------------------
# 3) コールバック関数群
# --------------------------------------------------
# def fetch_callback():
#     st.session_state.stage = "info"

def fetch_callback():
    """
    - ボタンが押されたときに銘柄情報を取得し、session_state.latest_info に保存します
    - その後にステージを "info" に切り替え
    """
    code = st.session_state.code
    if not code:
        return

    # yfinance から情報を取得し、セッションステートに格納する（１回だけ実行）
    info = fetch(code)                             # ← 変更：fetch() をここで呼ぶ
    st.session_state.latest_info = info            # ← 変更：取得結果を保存

    # 銘柄名が取れなかったらステージを戻す
    if not info or not info.get("security_name"):
        st.error("yfinance で取得できませんでした")
        st.session_state.latest_info = None         # ← 追加：念のためクリア
        st.session_state.stage = "input"
    else:
        st.session_state.stage = "info"             # ← 変更：ステージを遷移


def register_callback():
    st.session_state.stage = "registered"

def reset_callback():
    # ステージとコードを初期化
    st.session_state.stage = "input"
    st.session_state.code = ""
    # フォーム入力値を初期化
    st.session_state.txn_type = "BUY"
    st.session_state.qty      = 100.0
    st.session_state.price    = 0.0
    st.session_state.txn_date = date.today()
    st.session_state.latest_info = None            # ← 追加

# ★ 新規：コードを安全にセットする専用関数
def set_code_callback(selected_code: str):
    st.session_state.code = selected_code
    # 必要があれば、選択した瞬間にステージだけ変えたい場合もここで対応できます（任意）
    # 例: st.session_state.stage = "info"

# --------------------------------------------------
# 4) DB 接続を返す関数（キャッシュ付き。外で明示的に close() する）
# --------------------------------------------------
@st.cache_resource(show_spinner=False)
def conn():
    c = sqlite3.connect(db_path, check_same_thread=False)
    c.execute("PRAGMA foreign_keys = ON;")
    return c

# --------------------------------------------------
# 5) yfinance から銘柄情報を取得（キャッシュ付き）
# --------------------------------------------------
# キャッシュ用。必要ならコメントアウトを外す。
# @st.cache_data(ttl=600)

def fetch(code: str):
    q = f"{code}.T" if not code.endswith(".T") else code
    t = yf.Ticker(q).info
    return {
        "security_code": code,
        "d365_code": code,
        "security_name": t.get("shortName", ""),
        "market_price": t.get("currentPrice", None)
    }

# --------------------------------------------------
# 6) securities テーブルに存在確認 → ID を返す（なければ INSERT）
# --------------------------------------------------
def ensure_security(cn, row):
    cur = cn.execute(
        "SELECT security_id FROM securities WHERE security_code=?", (row["security_code"],)
    ).fetchone()
    if cur:
        return cur[0]
    cur = cn.execute(
        "INSERT INTO securities (security_code, d365_code, security_name) VALUES (?,?,?)",
        (row["security_code"], row["d365_code"], row["security_name"])
    )
    cn.commit()
    return cur.lastrowid

# --------------------------------------------------
# 7) 過去の銘柄コード一覧を取得（キャッシュ付き）
# --------------------------------------------------
@st.cache_data(ttl=600)
def get_security_codes():
    c = conn()
    try:
        rows = c.execute("SELECT security_code FROM securities").fetchall()
        return [str(r[0]) for r in rows]
    finally:
        # キャッシュされた conn() は close しない
        pass

# --------------------------------------------------
# 8) 画面描画
# --------------------------------------------------
st.header("📝 売買結果 登録")

# 【1】 銘柄コード入力 と「銘柄情報を取得」ボタン
# --------------------------------------------------
st.text_input(
    label="銘柄コード（例 7203）",
    key="code",  
    placeholder="ここにコードを入力",
)

st.button(
    label="銘柄情報を取得",
    on_click=fetch_callback,
    disabled=(st.session_state.code == "")
)

# 【2】 ステージ "info" のとき：yfinance から情報を取ってフォーム表示
# --------------------------------------------------
if st.session_state.stage == "info":
    # info = fetch(st.session_state.code)
    # if not info["security_name"]:
    #     st.error("yfinance で取得できませんでした")
    #     st.session_state.stage = "input"
    #     st.stop()

    info = st.session_state.latest_info           # ← 変更：ここでセッションステートから取る

    # safety check：万が一 info が空だったらステージを戻す
    if not info or not info.get("security_name"):
        st.error("不正な情報です。もう一度銘柄コードを入力してください。")
        st.session_state.stage = "input"
        st.stop()

    # 銘柄名と現在値を表示
    st.success(f"{info['security_name']}   現在値: {info['market_price']} 円")

    # 売買タイプ
    st.radio("売買タイプ", ["BUY", "SEL"], horizontal=True, key="txn_type")

    # 株数
    st.number_input(
        "株数",
        min_value=1.0,
        step=1.0,
        value=st.session_state.qty,
        key="qty",
    )

    # 株価
    st.number_input(
        "株価",
        min_value=0.0,
        step=1.0,
        value=st.session_state.price or float(info["market_price"]),
        key="price",
    )

    # 取引日（DATE）
    st.session_state.txn_date = st.date_input(
        "取引日",
        value=st.session_state.txn_date,
        key="txn_date_input"
    )

    # 「取引を登録する」ボタン
    st.button("取引を登録する", on_click=register_callback)

# 【3】 ステージ "registered" のとき：DB に INSERT ＆ フォームリセット
# --------------------------------------------------
if st.session_state.stage == "registered":
    c = None
    try:
        c = conn()

        # securities テーブルに存在確認 → sid を取得（なければ INSERT）
        # sid = ensure_security(c, fetch(st.session_state.code))
        sid = ensure_security(c, st.session_state.latest_info)

        # 取引日を文字列化（"YYYY-MM-DD"）
        txn_date_str = st.session_state.txn_date.strftime("%Y-%m-%d")

        # INSERT 文を実行（create_at カラムは省略 → DEFAULT CURRENT_TIMESTAMP が自動挿入される）
        c.execute(
            """
            INSERT INTO transactions
                (security_id, txn_type, quantity, price, txn_date)
            VALUES
                (?, ?, ?, ?, ?)
            """,
            (
                sid,
                st.session_state.txn_type,
                st.session_state.qty,
                st.session_state.price,
                txn_date_str,
            )
        )
        c.commit()
        st.success("登録しました ✅")
        # reset_callback()
        st.session_state.stage = "input"


    except Exception as e:
        st.error(f"登録失敗: {e}")

    # 「別の取引を登録する」ボタン
    st.button("別の取引を登録する", on_click=reset_callback)

# # 【4】 区切り線 ＋ 「過去の銘柄コード一覧」を横並びで表示
# # --------------------------------------------------
# st.markdown("---")
# st.write("##### 過去の銘柄コード一覧（クリックすると入力欄に反映されます）")

# codes = get_security_codes()

# if len(codes) > 0 and len(codes) <= 20:
#     # コード数 20 件以下なら一行にすべて横並び
#     cols = st.columns(len(codes))
#     for idx, code_str in enumerate(codes):
#         cols[idx].button(
#             label=code_str,
#             key=f"code_btn_{code_str}",
#             on_click=set_code_callback,
#             args=(code_str,)
#         )

# elif len(codes) > 20:
#     # 20 件を超える場合は「10 列ずつ折り返し」
#     per_row = 10
#     for i in range(0, len(codes), per_row):
#         slice_codes = codes[i : i + per_row]
#         cols = st.columns(len(slice_codes))
#         for idx, code_str in enumerate(slice_codes):
#             cols[idx].button(
#                 label=code_str,
#                 key=f"code_btn_{code_str}",
#                 on_click=set_code_callback,
#                 args=(code_str,)
#             )

# else:
#     st.write("過去の銘柄コードはまだ登録されていません。")
