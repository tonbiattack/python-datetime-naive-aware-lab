# Python `datetime` naive/aware 比較デバッグラボ

`Z` 付きのISO 8601期限を解析するとUTC awareな `datetime` になります。一方、`datetime.now()` を引数なしで使うとnaiveな値になります。本ラボは、この二つを順序比較して `TypeError` になる不具合を、テスト・観測出力・最小修正で追う教材です。

| 項目 | 内容 |
|---|---|
| 対象Python | 3.11以上 |
| 外部依存 | なし |
| テスト基盤 | 標準ライブラリ `unittest` |
| 時刻依存 | なし。テストは固定した値を注入する。 |

## 不具合の再現

プロジェクトのルートで次を実行します。

```bash
python3 -m unittest discover -s tests -v
```

不具合状態では `TypeError: can't compare offset-naive and offset-aware datetimes` により失敗します。比較直前の属性を確認するには、次を実行します。

```bash
python3 evidence/observe_failure.py
```

## 修正後の確認

最小修正を適用したコミットでは、次のコマンドで全テストが成功します。

```bash
python3 -m unittest discover -s tests -v
```

## 参照

`datetime` のaware/naiveの定義、比較規則、UTCの現在時刻を生成する推奨APIは、Python公式ドキュメントを参照してください。[1]

[1]: https://docs.python.org/3/library/datetime.html
