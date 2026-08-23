#!/usr/bin/env python3
"""
raw_catalogs/ フォルダの中にある複数のJSON（カタログの種類ごとに分けたもの）を、
検索ツールが読み込む2つの軽量ファイルに変換するスクリプト。

使い方:
    python3 build_index.py raw_catalogs フォルダ名またはファイル名]

出力:
    catalogs.json     カタログのメタ情報だけの配列 [{id,title,url,date,series}, ...]
    song_index.json   曲ID -> catalogs.json 上のインデックス番号の配列

フォルダ構成の例（カタログの種類ごとにファイルを分ける場合）:
    raw_catalogs/
      nikkan_vocaloid_ranking.json   ← 「日刊〇〇ランキング」ぶん
      gekkan_vocaloid_catalog.json   ← 「月刊〇〇カタログ」ぶん

    フォルダを渡すと、中の *.json を全部読み込んでまとめます。
    ファイル名（拡張子を除いた部分）が自動で "series"（種類）として
    各カタログに付きます。1本のファイルにまとめたい場合は、今まで通り
    ファイルを直接指定しても動きます（この場合 series は付きません）。

各JSONファイルの中身の形式（1カタログ動画 = 1オブジェクト）:
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

1つのファイルの中でJSONの構文エラーがあっても、そのファイルだけスキップして
残りの処理は続行します（エラー内容と行番号を表示します）。
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


def load_catalog_files(src_path: Path):
    """src_path がフォルダなら中の*.jsonを全部、ファイルならそれ単体を読み込む。
    (raw_entry, series_or_None, ファイル名) のタプルを順番に返すジェネレータ。
    壊れたJSONファイルはエラーを表示してスキップし、他のファイルの処理は続ける。
    """
    if src_path.is_dir():
        files = sorted(src_path.glob("*.json"))
        if not files:
            print(f"警告: {src_path} の中に .json ファイルが見つかりませんでした")
    else:
        files = [src_path]

    for file_path in files:
        series = file_path.stem if src_path.is_dir() else None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"エラー: {file_path.name} の構文が壊れています（{e.lineno}行目 {e.colno}列目: {e.msg}）"
                  f" → このファイルはスキップします")
            continue
        except Exception as e:
            print(f"エラー: {file_path.name} を読み込めませんでした（{e}） → このファイルはスキップします")
            continue

        if not isinstance(data, list):
            print(f"警告: {file_path.name} の中身が配列([...])ではありません → このファイルはスキップします")
            continue

        for entry in data:
            yield entry, series, file_path.name


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 build_index.py raw_catalogs [出力先ディレクトリ]")
        print("        raw_catalogs には、フォルダ（種類ごとに分けたJSON群）か")
        print("        単一のJSONファイルのどちらも指定できます")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        src_path if src_path.is_dir() else src_path.parent
    )

    catalogs_out = []
    song_index: dict[str, list] = {}

    skipped_songs = 0
    skipped_catalogs = 0
    files_seen = set()

    for entry, series, filename in load_catalog_files(src_path):
        files_seen.add(filename)
        cat_id = entry.get("id", "")
        title = entry.get("title", "")
        url = entry.get("url", "")
        date = entry.get("date", "")
        # ファイル内で個別に series を指定していればそちらを優先
        entry_series = entry.get("series") or series

        if not (title and url):
            skipped_catalogs += 1
            continue

        idx = len(catalogs_out)
        catalog_record = {
            "id": cat_id,
            "title": title,
            "url": url,
            "date": date,
        }
        if entry_series:
            catalog_record["series"] = entry_series
        catalogs_out.append(catalog_record)

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

    print(f"読み込んだファイル数: {len(files_seen)}")
    print(f"カタログ: {len(catalogs_out)} 件書き出し（スキップ {skipped_catalogs} 件）")
    print(f"楽曲: {len(song_index)} 曲ぶんのインデックスを作成（無効なID {skipped_songs} 件はスキップ）")
    print(f"出力先: {out_dir / 'catalogs.json'}")
    print(f"出力先: {out_dir / 'song_index.json'}")


if __name__ == "__main__":
    main()
