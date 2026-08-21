#!/usr/bin/env python3
"""
raw_catalogs.json (あなたが集める生データ) を、
検索ツールが読み込む2つの軽量ファイルに変換するスクリプト。

使い方:
    python3 build_index.py raw_catalogs.json

出力:
    catalogs.json     カタログのメタ情報だけの配列 [{id,title,url,date}, ...]
    song_index.json   曲ID -> catalogs.json 上のインデックス番号の配列

raw_catalogs.json の形式（1カタログ動画 = 1オブジェクト）:
[
  {
    "id": "sm44444001",
    "title": "日刊ボーカロイドランキング 8月19日",
    "url": "https://www.nicovideo.jp/watch/sm44444001",
    "date": "2026-08-19",
    "songs": [
      {"id": "sm12345678", "time": 69},
      {"id": "SM23456789", "time": 184},
      "sm34567890"
    ]
  },
  ...
]

songs の各要素は次の2通りの書き方に対応:
  1. {"id": "sm12345678", "time": 69}  ... 開始秒数(time)ありのIDを再生させたい場合
  2. "sm12345678"  ... 開始秒数を付けない、従来通りのプレーンなID/URL文字列

id/URLの部分は大文字小文字混在・?ref=つきURLなどでもOK（自動で正規化されます）。
time は「そのカタログ動画内で、その曲の紹介が始まる秒数」を想定（0開始の整数）。
1秒前にずらす等の調整は取得側で済ませておく前提で、ここではそのまま使います。
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

ID_PATTERN = re.compile(r"(sm|so|nm|ax)\d+", re.IGNORECASE)


def normalize_id(raw: str) -> str | None:
    """URLでもIDでも渡せば正規化された小文字IDを返す。マッチしなければNone。"""
    if not raw:
        return None
    match = ID_PATTERN.search(raw.strip())
    return match.group(0).lower() if match else None


def parse_song_entry(entry) -> tuple[str | None, int | None]:
    """songs配列の1要素を (正規化されたID, time秒 or None) に変換する。
    entry は文字列("sm12345678"等)か、{"id":..., "time":...}の辞書。
    """
    if isinstance(entry, dict):
        raw_id = entry.get("id") or entry.get("url") or ""
        song_id = normalize_id(raw_id)
        time_val = entry.get("time")
        if time_val is not None:
            try:
                time_val = int(time_val)
                if time_val < 0:
                    time_val = None
            except (TypeError, ValueError):
                time_val = None
        return song_id, time_val
    return normalize_id(entry), None


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 build_index.py raw_catalogs.json [出力先ディレクトリ]")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else src_path.parent

    raw = json.loads(src_path.read_text(encoding="utf-8"))

    catalogs_out = []
    song_index: dict[str, list[int]] = {}

    skipped_songs = 0
    skipped_catalogs = 0

    for entry in raw:
        cat_id = entry.get("id", "")
        title = entry.get("title", "")
        url = entry.get("url", "")
        date = entry.get("date", "")

        if not (title and url):
            skipped_catalogs += 1
            continue

        idx = len(catalogs_out)
        catalogs_out.append({
            "id": cat_id,
            "title": title,
            "url": url,
            "date": date,
        })

        seen_in_this_catalog = set()
        for raw_song in entry.get("songs", []):
            song_id, time_val = parse_song_entry(raw_song)
            if not song_id:
                skipped_songs += 1
                continue
            if song_id in seen_in_this_catalog:
                continue  # 同じカタログ内の重複IDは最初の1件だけ採用
            seen_in_this_catalog.add(song_id)
            song_index.setdefault(song_id, []).append([idx, time_val])

    out_dir.mkdir(parents=True, exist_ok=True)

    catalogs_payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "catalogs": catalogs_out,
    }

    (out_dir / "catalogs.json").write_text(
        json.dumps(catalogs_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (out_dir / "song_index.json").write_text(
        json.dumps(song_index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"カタログ: {len(catalogs_out)} 件書き出し（スキップ {skipped_catalogs} 件）")
    print(f"楽曲: {len(song_index)} 曲ぶんのインデックスを作成（無効なID {skipped_songs} 件はスキップ）")
    print(f"出力先: {out_dir / 'catalogs.json'}")
    print(f"出力先: {out_dir / 'song_index.json'}")


if __name__ == "__main__":
    main()
