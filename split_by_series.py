#!/usr/bin/env python3
"""
既存の1つの raw_catalogs.json を、タイトルに含まれるキーワードを基準にして
raw_catalogs/ フォルダの中の複数ファイルへ自動で振り分ける、移行用の1回きりのスクリプト。

使い方:
    1. 下の RULES を、自分が実際に使っているカタログのタイトルに合わせて書き換える
    2. python3 split_by_series.py raw_catalogs.json raw_catalogs
    3. raw_catalogs/ フォルダの中身を確認する
    4. 問題なければ build_index.py の対象をそのフォルダに切り替える
"""

import json
import sys
from pathlib import Path

# ここを自分のタイトルに合わせて書き換えてください。
# (出力ファイル名, [そのタイトルに含まれていたら一致とみなすキーワードのリスト]) の順で
# 上から順番にチェックし、最初に一致したルールに振り分けられます。
RULES = [
    ("nikkan_vocaloid_ranking", ["日刊ボーカロイドランキング", "日刊VOCALOIDランキング"]),
    ("gekkan_vocaloid_catalog", ["月刊VOCALOIDカタログ", "月刊ボーカロイドカタログ"]),
]

# どのルールにも一致しなかったものはここに入る
FALLBACK = "other"


def classify(title: str) -> str:
    for series_name, keywords in RULES:
        if any(kw in title for kw in keywords):
            return series_name
    return FALLBACK


def main():
    if len(sys.argv) < 3:
        print("使い方: python3 split_by_series.py raw_catalogs.json raw_catalogs")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(src_path.read_text(encoding="utf-8"))

    buckets: dict[str, list] = {}
    for entry in data:
        series_name = classify(entry.get("title", ""))
        buckets.setdefault(series_name, []).append(entry)

    for series_name, entries in buckets.items():
        out_path = out_dir / f"{series_name}.json"
        out_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"{out_path}: {len(entries)} 件")

    if FALLBACK in buckets:
        print(f"\n注意: どのルールにも一致しなかった {len(buckets[FALLBACK])} 件が"
              f" {FALLBACK}.json に入っています。中身を見て、RULESにキーワードを"
              f" 追加するか、手動で正しいファイルに移してください。")


if __name__ == "__main__":
    main()
