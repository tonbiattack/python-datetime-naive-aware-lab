# Pythonの`datetime`で期限判定が`TypeError`になる理由：naive／awareの比較契約を最小再現から理解する

**Python 3.11以上**を対象に、UTC表記の期限を比較するコードで発生した `TypeError: can't compare offset-naive and offset-aware datetimes` を再現し、観測、原因の切り分け、最小修正、回帰テストまでを示します。結論から言えば、`Z` 付き入力を解析して得たUTC awareな期限と、`datetime.now()` が返すnaiveな現在時刻を順序比較したことが原因です。現在時刻も `datetime.now(timezone.utc)` によりUTC awareとして生成すれば、同じ時間軸上で比較できます。[1]

> “A naive object does not contain enough information to unambiguously locate itself relative to other date/time objects.” — Python `datetime` documentation [1]

## 既存題材との差分

既存のPythonデバッグ記事では、FastAPI `TestClient` のlifespan、PATCH時に `False` が消える問題、`asyncio` の `ContextVar` がexecutor境界で伝播しない問題が扱われています。また、日時に近い題材にはJava `LocalDateTime` のJST誤保存、NuxtのUTC/JST表示差異、PHPの可変 `DateTime` があります。

今回の題材はそれらと異なり、**Pythonの比較演算子がnaiveな値とawareな値の混在を拒否する**という型の契約を扱います。入力値は正しくUTCを含み、DBも画面も関係しません。比較する直前の二つの `datetime` の属性を観測することで、問題を一つの関数に絞り込みます。

| 観点 | 今回 | 近いが異なる題材 |
|---|---|---|
| 発火条件 | naiveな `now` とUTC awareな期限の順序比較 | ローカル日時を誤ったタイムゾーンでInstantへ変換 |
| 観測 | `tzinfo`、`utcoffset()`、比較時の例外 | 保存値、HTTP応答、画面表示 |
| 根本原因 | 比較対象の時点表現が不整合 | 入力ローカル日時の意味付けが不整合 |
| 最小修正 | 現在時刻をUTC awareで生成 | 業務タイムゾーンを適用して変換 |

## 期待していた挙動と実際の挙動

期限APIから `2026-08-20T00:00:00Z` を受け取ったとします。これはUTCの時点を明示した値です。2026年8月19日UTCの時点で判定すれば、期限切れではないため `False` が期待値です。

```python
is_expired("2026-08-20T00:00:00Z")  # 期待値: False
```

初期実装は、期限を `datetime.fromisoformat()` で解析し、現在時刻には引数なしの `datetime.now()` を使っていました。

```python
from datetime import datetime


def is_expired(raw_deadline: str) -> bool:
    deadline = datetime.fromisoformat(raw_deadline)
    now = datetime.now()
    return now >= deadline
```

この比較は `False` を返す前に停止します。Pythonの仕様では、naiveとawareな `datetime` の**順序比較**は `TypeError` を送出します。[1]

```text
TypeError: can't compare offset-naive and offset-aware datetimes
```

## 最小再現プロジェクト

再現コードは [`python-datetime-naive-aware-lab`](./) にあります。外部ライブラリを使わず、時刻をクロック関数として注入するため、実時間や実行環境のローカルタイムゾーンに依存しません。

```text
python-datetime-naive-aware-lab/
├── src/
│   └── deadline_guard.py
├── tests/
│   └── test_deadline_guard.py
├── evidence/
│   ├── failing_test_output.txt
│   ├── observation_output.txt
│   └── passing_test_output.txt
├── README.md
└── article_draft.md
```

不具合を含む最初のコミットでは、現在時刻を生成するクロックに引数を渡していません。

```python
from collections.abc import Callable
from datetime import datetime

Clock = Callable[[], datetime]


def parse_deadline(raw_deadline: str) -> datetime:
    return datetime.fromisoformat(raw_deadline)


def is_expired(raw_deadline: str, clock: Clock = datetime.now) -> bool:
    deadline = parse_deadline(raw_deadline)
    now = clock()  # datetime.now() はnaiveなローカル日時を返す
    return now >= deadline
```

失敗する振る舞いテストは、利用者から見た期待だけを表します。テストは内部呼び出し回数を検証せず、未来のUTC期限が期限切れではないことを確認します。

```python
def test_future_utc_deadline_is_not_expired(self) -> None:
    def fixed_clock(zone: tzinfo | None = None) -> datetime:
        return datetime(2026, 8, 19, 0, 0, 0, tzinfo=zone)

    self.assertFalse(
        is_expired("2026-08-20T00:00:00Z", fixed_clock),
    )
```

最初のコミットで次を実行すると失敗します。

```bash
python3 -m unittest discover -s tests -v
```

```text
test_future_utc_deadline_is_not_expired ... ERROR
...
  File "src/deadline_guard.py", line 18, in is_expired
    return now >= deadline
TypeError: can't compare offset-naive and offset-aware datetimes

Ran 1 test
FAILED (errors=1)
```

## 調査：何を観測し、どの仮説を除外したか

まず、例外メッセージだけで「タイムゾーンの設定がおかしい」と決めつけません。期限の解析、現在時刻の生成、期限そのものの過去・未来という三つの仮説を分離します。

| 仮説 | 予測 | 最小実験 | 実際の結果 | 判定 |
|---|---|---|---|---|
| 期限文字列の解析に失敗した | 解析時に例外、またはUTCオフセットが取れない | 解析後の `tzinfo` と `utcoffset()` を出力する | `timezone.utc` と `timedelta(0)` | 棄却 |
| 現在時刻がnaiveである | `tzinfo` と `utcoffset()` がともに `None` | 比較直前の現在時刻を出力する | どちらも `None` | 採用 |
| 期限が過去にある | 比較は成功し、真偽だけ変わる | UTC aware同士で比較する | 比較前に例外 | 棄却 |

観測スクリプトの出力は次のとおりでした。

```text
deadline: value=datetime.datetime(2026, 8, 20, 0, 0, tzinfo=datetime.timezone.utc), tzinfo=datetime.timezone.utc, utcoffset=datetime.timedelta(0)
now: value=datetime.datetime(2026, 8, 19, 0, 0), tzinfo=None, utcoffset=None
is_expired raised: TypeError: can't compare offset-naive and offset-aware datetimes
```

ここで重要なのは、`deadline` の時刻値ではなく性質です。`deadline` は `tzinfo` とUTCオフセットを持つawareな値です。一方、`now` は両方を持たないnaiveな値です。Pythonは、naiveな値がUTC、ローカル時刻、その他のどれを指すかをアプリケーション自身が決めるものとして扱います。[1]

| 値 | `repr()` の要点 | `tzinfo` | `utcoffset()` | 分類 |
|---|---|---|---|---|
| 期限 | `2026-08-20 00:00:00+00:00` | `timezone.utc` | `0` | aware |
| 修正前の現在時刻 | `2026-08-19 00:00:00` | `None` | `None` | naive |

## 原因：比較の前に「同じ時間軸である」ことが保証されていない

`datetime` は、`tzinfo` が `None` ではなく、かつ `utcoffset()` が `None` を返さないときにawareです。その他はnaiveです。[1] awareな値にはUTCとの差分があり、時点として比較できます。しかしnaiveな値には、どのタイムゾーンで解釈すべきかを決める情報がありません。

このため、Pythonはnaiveとawareを順序比較するときに暗黙の推測をしません。ローカルタイムゾーンと仮定しても、実行環境が変われば結果が変わります。UTCと仮定すれば、ローカル時刻を受け取った呼び出し元の意味を壊す可能性があります。例外は不便なだけではなく、比較の前提を設計者へ明示させるための境界です。

`datetime.utcnow()` で置き換えるのも正しい修正ではありません。公式ドキュメントは `utcnow()` がnaiveなUTC日時を返すと説明し、UTCを表す場合は `datetime.now(timezone.utc)` を推奨しています。[1]

## 修正：現在時刻をUTC awareとして生成する

この事例では、期限文字列が `Z` によりUTCを明示しています。したがって、比較側の現在時刻もUTC awareとして生成する変更だけで十分です。現在時刻の取得境界へUTCを渡し、それ以外の振る舞いを変えません。

```diff
-from datetime import datetime
+from datetime import datetime, timezone, tzinfo
 
-Clock = Callable[[], datetime]
+Clock = Callable[[tzinfo | None], datetime]
 
 def is_expired(raw_deadline: str, clock: Clock = datetime.now) -> bool:
     deadline = parse_deadline(raw_deadline)
-    now = clock()
+    now = clock(timezone.utc)
     return now >= deadline
```

本番ではデフォルトのクロックが `datetime.now` なので、実行される式は次と等価です。

```python
now = datetime.now(timezone.utc)
```

テスト用クロックも同じ `timezone.utc` を受け取り、UTC awareな固定時刻を返します。これにより、元の失敗テストはそのまま回帰テストになります。

```python
def fixed_clock(zone: tzinfo | None = None) -> datetime:
    return datetime(2026, 8, 19, 0, 0, 0, tzinfo=zone)
```

### `replace(tzinfo=timezone.utc)` を修正に使わない理由

`replace()` は指定した属性を更新した新しい `datetime` を返します。[1] 既存のnaive値が**すでにUTCを表す**ことが、データ契約や移行記録から確定している場合には、`replace(tzinfo=timezone.utc)` でその意味を明示する選択肢があります。

ただし、未知のnaiveなローカル時刻にUTCを付けても、時刻表示を保ったまま「UTCの別の時点」と解釈し直すだけです。タイムゾーン間で同じ時点を変換したいときは、awareな値に対して `astimezone()` を使います。[1] 今回は新しく生成する現在時刻のタイムゾーンを明示すればよいため、既存値の意味を後付けする `replace()` は使いません。

| 状況 | 行うこと | 行わないこと |
|---|---|---|
| UTC期限と現在時刻を比較したい | `datetime.now(timezone.utc)` を使う | `datetime.now()` のまま比較する |
| 既存naive値がUTCだと契約で保証されている | 必要に応じ `replace(tzinfo=timezone.utc)` で意味を明示する | 不明なローカル時刻をUTC扱いにする |
| UTCから業務タイムゾーンの表示へ変換したい | `aware_dt.astimezone(ZoneInfo("Asia/Tokyo"))` を使う | `replace(tzinfo=...)` を変換として使う |

地域のタイムゾーンを扱う場合、Python 3.9以降の `zoneinfo` はIANAタイムゾーンデータベースをサポートします。[2] ただし本件はUTCの時点比較だけを再現対象とし、夏時間の重複時刻や `fold` は意図的に範囲外としました。

## 回帰テスト

修正後も、最初に失敗した `test_future_utc_deadline_is_not_expired` は残しています。さらに、過去期限が `True` になる対照ケースと、クロックが明示的に `timezone.utc` を受け取ることを確認するテストを追加しました。

| テスト | 検証する契約 | 修正後 |
|---|---|---|
| `test_future_utc_deadline_is_not_expired` | 元の失敗ケース：未来のUTC期限は期限切れでない | 成功 |
| `test_past_utc_deadline_is_expired` | 対照ケース：過去のUTC期限は期限切れ | 成功 |
| `test_clock_receives_utc_timezone` | 現在時刻の生成時にUTCを明示する | 成功 |

```bash
python3 -m unittest discover -s tests -v
```

```text
test_clock_receives_utc_timezone ... ok
test_future_utc_deadline_is_not_expired ... ok
test_past_utc_deadline_is_expired ... ok

Ran 3 tests
OK
```

## Git履歴で再現する

プロジェクトには、再現と修正を分けた二つのローカルコミットがあります。最初のコミットは不具合を含む実装と失敗テスト、二つ目はUTC awareへの最小修正と回帰テストです。

```bash
# 不具合状態を確認する
 git checkout 36496a2
 python3 -m unittest discover -s tests -v

# 修正済みのmainへ戻る
 git checkout main
 python3 -m unittest discover -s tests -v
```

記事執筆時点のローカル履歴は次のとおりです。

```text
328d441 fix: 現在時刻をUTC awareとして比較する
36496a2 test: naiveとawareな日時比較を再現する
```

## まとめ

この不具合の判断規則は三つです。

1. **時点を比較する前に、両方がnaiveか、または両方がawareかを確認する。** 特に `tzinfo` と `utcoffset()` を比較直前で観測すると早い段階で絞り込めます。[1]
2. **UTCを扱うなら、値を生成する境界で `datetime.now(timezone.utc)` を使う。** `datetime.utcnow()` はnaiveな値を返すため、比較可能性を解決しません。[1]
3. **`replace(tzinfo=...)` と時点変換を混同しない。** 値がどの時刻を意味するかが保証される場合だけに属性付与を限定し、表示・地域タイムゾーンへの変換には `astimezone()` と `zoneinfo` を使います。[1] [2]

## 参考資料

[1]: https://docs.python.org/3/library/datetime.html "datetime — Basic date and time types — Python 3"
[2]: https://docs.python.org/3/library/zoneinfo.html "zoneinfo — IANA time zone support — Python 3"
[3]: https://peps.python.org/pep-0615/ "PEP 615 — Support for the IANA Time Zone Database in the Standard Library"
[4]: https://peps.python.org/pep-0495/ "PEP 495 — Local Time Disambiguation"
