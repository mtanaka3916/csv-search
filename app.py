from flask import Flask, request, redirect
import os
import pandas as pd
import requests
import io
import time

app = Flask(__name__)

CSV_URL = os.getenv("CSV_URL")
ACCESS_KEY = os.getenv("ACCESS_KEY")

COLUMN_MAP = {
    "year": "年",
    "month": "月",
    "day": "日",
    "name1": "名前",
    "name2": "名前2",
    "item": "品名",
    "purchase_amount": "仕入kg",
    "purchase_unit": "仕入単価",
    "purchase_price": "仕入金額",
    "sell_amount": "売上kg",
    "sell_unit": "売上単価",
    "sell_price": "売上金額",
    "category": "カテゴリ"
}

CACHE = {"df": None,"timestamp": 0}
CACHE_TTL = 60 * 60 * 24  # 10分ごとに更新（必要に応じて変更OK）


def load_csv():
    now = time.time()

    if CACHE["df"] is not None and (now - CACHE["timestamp"] < CACHE_TTL):
        return CACHE["df"]

    r = requests.get(CSV_URL)
    df = pd.read_csv(io.StringIO(r.text))

    # 列名を日本語に変換
    #df = df.rename(columns=COLUMN_MAP)

    if set(["year", "month", "day"]).issubset(df.columns):
        df["日付"] = pd.to_datetime(df[["year", "month", "day"]], errors="coerce").dt.strftime("%Y-%m-%d")
        df = df.drop(columns=["year", "month", "day"])

    for col in df.select_dtypes(include=["float", "int"]).columns:
        def format_number(x):
            if pd.isnull(x):
                return ""
            # 小数点以下が 0 の場合は整数化
            if float(x).is_integer():
                return f"{int(x):,}"
            # 小数がある場合はそのまま（必要なら丸めも可能）
            return f"{x:,}"
        df[col] = df[col].apply(format_number)

    df = df.fillna("")
    
    if "日付" in df.columns:
        df = df.sort_values("日付", ascending=False)

    # --- 検索用キャッシュ列を作成 ---
    SEARCH_COLUMNS = ["name1", "name2", "item"] 
    valid_cols = [c for c in SEARCH_COLUMNS if c in df.columns]
    df["_search"] = df[valid_cols].astype(str).agg(" ".join, axis=1).str.lower()

    CACHE["df"] = df
    CACHE["timestamp"] = now

    return df


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        key = request.form.get("key")
        if key == ACCESS_KEY:
            return redirect("/search")
        else:
            return """
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <p>キーが違います。</p>
            <a href="/login">戻る</a>
            """

    return """
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <form method="POST">
        <input type="password" name="key" placeholder="アクセスキーを入力" style="width:100%;padding:10px;font-size:18px;">
        <button type="submit" style="width:100%;padding:10px;font-size:18px;">ログイン</button>
    </form>
    """



@app.route("/search", methods=["GET"])
def index():
    keyword = request.args.get("q", "")
    df = load_csv()

    df = df.rename(columns=COLUMN_MAP)

    if keyword:
        keyword_lower = keyword.lower()
        result = df[df["_search"].str.contains(keyword_lower, na=False)]
    else:
        result = pd.DataFrame()

    # カード型レイアウト生成

    DISPLAY_COLUMNS = ["日付", "名前", "名前2", "品名", "仕入kg", "仕入単価", "仕入金額", "売上kg", "売上単価", "売上金額"]

    cards_html = ""
    for _, row in result.iterrows():
        card = "<div class='card'>"

        # --- 日付を一番上に ---
        if "日付" in row:
            card += f"<div class='row'><strong>日付</strong><br>{row['日付']}</div>"

        # --- その他の項目 ---
        for col in DISPLAY_COLUMNS:
            if col == "日付":
                continue
            if col in row.index:  # ← 存在チェックを追加
                val = row[col] if pd.notnull(row[col]) else ""
                card += f"<div class='row'><strong>{col}</strong><br>{val}</div>"

        card += "</div>"
        cards_html += card



    html = f"""
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {{
            font-family: sans-serif;
            padding: 10px;
            font-size: 16px;
        }}

        input[type="text"] {{
            width: 100%;
            padding: 10px;
            font-size: 18px;
            margin-bottom: 10px;
        }}

        button {{
            width: 100%;
            padding: 10px;
            font-size: 18px;
            background-color: #0078D4;
            color: white;
            border: none;
            border-radius: 5px;
        }}

        .card {{
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 12px;
            background: #fafafa;
        }}

        .row {{
            margin-bottom: 6px;
            word-break: break-word;
        }}

        strong {{
            color: #333;
        }}
    </style>

    <form method="get">
        <input type="hidden" name="key" value="{ACCESS_KEY}">
        <input type="text" name="q" placeholder="検索キーワード" value="{keyword}">
        <button type="submit">検索</button>
    </form>

    {cards_html}
    """

    return html


@app.route("/")
def root():
    return redirect("/login")
