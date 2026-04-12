# 日本の税関データ月次バッチ

日本の税関公開データから対象年月の輸入統計を取得し、`master_codes` シートで管理する 9 桁 HS コード・国コードの組み合わせに一致するレコードを Google スプレッドシートへ保存する Python バッチです。

GitHub Actions で毎月自動実行することを前提にしています。

## 対象スプレッドシート

- スプレッドシートID: `1c6zGLbCIfsL0UKVilqN7d0hsjsKEKlEbRrgcBaqIELM`
- 読み込みシート: `master_codes`
- 書き込みシート: `raw_trade`
- 書き込みシート: `calc_unit_price`

## ディレクトリ構成

```text
.
├─ .github/workflows/update_trade.yml
├─ requirements.txt
├─ README.md
└─ src
   ├─ config.py
   ├─ customs_fetcher.py
   ├─ logging_utils.py
   ├─ main.py
   ├─ sheets_client.py
   └─ transformers.py
```

## セットアップ

### 1. Python 環境を用意する

Python 3.11 を使用します。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell の場合:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Google サービスアカウントを準備する

1. Google Cloud で Google Sheets API を有効化します。
2. サービスアカウントを作成し、JSON キーを発行します。
3. 対象スプレッドシートをそのサービスアカウントのメールアドレスに共有します。

### 3. 環境変数を設定する

必須の環境変数は以下です。

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `SPREADSHEET_ID`

ローカル実行例:

```powershell
$env:GOOGLE_SERVICE_ACCOUNT_JSON = Get-Content .\service-account.json -Raw
$env:SPREADSHEET_ID = "1c6zGLbCIfsL0UKVilqN7d0hsjsKEKlEbRrgcBaqIELM"
python src/main.py --dry-run
```

## 実行方法

前月分を取得:

```bash
python src/main.py
```

対象年月を指定:

```bash
python src/main.py --year-month 2026-03
```

シート更新なしで確認:

```bash
python src/main.py --year-month 2026-03 --dry-run
```

## `master_codes` シート定義

`enabled = 1` の行のみ処理対象です。列名は多少揺れても吸収しますが、意味としては以下を想定しています。

| 列名 | 説明 |
| --- | --- |
| `hs_code` | 9桁の統計品目番号 |
| `item_name` | 品目名 |
| `category` | 任意のカテゴリ |
| `priority` | 任意の優先度 |
| `unit_name` | 計算用単位。`円/KG` `円/MT` `円/KL` を想定 |
| `country_name` | 表示用の国名 |
| `country_code` | 原則 ISO Alpha-2 を想定。例: `SA` |
| `enabled` | `1` なら取得対象 |

サンプル:

```csv
hs_code,item_name,category,priority,unit_name,country_name,country_code,enabled
271012181,ナフサ,エネルギー,1,円/KL,サウジアラビア,SA,1
270900900,原油,エネルギー,1,円/KL,サウジアラビア,SA,1
```

## 保存仕様

### `raw_trade`

以下の列で保存します。

- `year_month`
- `hs_code`
- `item_name`
- `category`
- `country_name`
- `country_code`
- `import_value_yen`
- `quantity_2`
- `quantity_2_unit`
- `calc_unit_name`
- `source`
- `source_url`
- `fetched_at`

一意キーは `year_month + hs_code + country_code` です。同じキーが既に存在する場合は上書きします。

### `calc_unit_price`

以下の列で保存します。

- `year_month`
- `hs_code`
- `item_name`
- `category`
- `country_name`
- `country_code`
- `import_value_yen`
- `quantity_2`
- `quantity_2_unit`
- `calc_unit_name`
- `unit_multiplier`
- `unit_price`
- `formula_note`
- `source`
- `source_url`
- `fetched_at`

`formula_note` は固定で `金額×単位÷第2数量` を保存します。

## 単価計算ルール

- `円/KG`: `unit_multiplier = 1`
- `円/MT`: `unit_multiplier = 1000`
- `円/KL`: 税関データの第2数量単位が `KL` のときだけ `unit_multiplier = 1`
- それ以外は warning を出して `calc_unit_price` には保存しません

計算式:

```text
unit_price = import_value_yen * unit_multiplier / quantity_2
```

以下の場合は `raw_trade` のみ保存し、`calc_unit_price` は保存しません。

- 金額が空
- 第2数量が空
- 第2数量が 0

## GitHub Actions

ワークフローは `.github/workflows/update_trade.yml` にあります。

対応トリガー:

- `schedule`
- `workflow_dispatch`

Secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `SPREADSHEET_ID`

月次実行は GitHub Actions の cron 制約上、毎月 18 日 06:00 JST 相当で設定しています。税関の公表タイミングずれに備え、必要に応じて `workflow_dispatch` で再実行してください。

## ログ

以下を INFO/WARNING ログに出します。

- `master_codes` 読み込み件数
- 税関データ取得件数
- 対象レコード抽出件数
- `raw_trade` 保存件数
- `calc_unit_price` 保存件数
- warning 件数

## 前提・仮定

この実装は、まず安定稼働する最小構成を優先しています。税関データの実ファイル仕様は月次更新や e-Stat 側の出し分けに影響されるため、以下の前提で実装しています。

1. 取得元 URL は財務省貿易統計サイトの e-Stat CSV 一覧を起点にしています。
   - 財務省貿易統計 ダウンロード案内: [Trade Statistics (Download)](https://www.customs.go.jp/toukei/info/tsdl_e.htm)
   - e-Stat 月次ファイル一覧の基点: [Commodity by Country Import](https://www.e-stat.go.jp/en/stat-search/files?cycle=1&cycle_facet=cycle&data=1&layout=datalist&metadata=1&page=1&tclass1=000001013180&tclass2=000001013182&tclass3val=0&toukei=00350300&tstat=000001013141)
2. 月次ファイルは章ごとの CSV に分かれているため、対象 HS コードの先頭 2 桁から必要章だけ取得します。
3. 金額は e-Stat の説明上 `1,000YEN` 単位のため、コード内では `import_value_yen` として扱うために 1000 倍しています。
4. CSV の列名は日本語/英語や表記ゆれがある前提で、代表的な別名を吸収する実装にしています。
5. `country_code` は `master_codes` では ISO Alpha-2 を推奨します。
   - 内部では財務省の国コード表から Customs 独自の数値コードを解決するようにしています。
   - 国コード表: [Country code list](https://www.customs.go.jp/toukei/sankou/code/country_e.htm)
6. 国名の揺れは一部の代表的な別名のみ吸収しています。将来、対象国が増えて名称差異が問題になる場合は別途マッピング設定を追加してください。
7. 数量単位は FAQ の略号説明を前提に `KG` `MT` `KL` 等を扱います。
   - FAQ: [数量単位の略号](https://www.customs.go.jp/toukei/sankou/howto/faq.htm)
8. 税関 CSV の実列名が大きく変わった場合は、`src/transformers.py` のヘッダー別名定義を更新してください。

## 拡張方針

将来、鉱工業生産や企業物価指数などを追加することを想定し、以下のように責務を分離しています。

- `customs_fetcher.py`: 外部統計ソースからの取得
- `transformers.py`: 列名吸収、抽出、整形、単価計算
- `sheets_client.py`: Google Sheets の読書き
- `main.py`: 実行フロー制御

別の統計を追加する場合は、同様の fetcher と transformer を追加し、`main.py` から呼び分ける構成に拡張しやすくしています。
