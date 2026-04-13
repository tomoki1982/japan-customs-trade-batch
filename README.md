# 日本の税関データ月次バッチ

日本の税関公開データから対象年月の輸入統計を取得し、`config/master_codes.csv` で管理する 9 桁 HS コード・国コードの組み合わせに一致するデータを `data/raw_trade.csv` と `data/calc_unit_price.csv` に保存する Python バッチです。

構成は `Trend Analysis` に寄せてあり、GitHub Actions で CSV を更新して GitHub に push し、Google Sheets 側は `IMPORTDATA()` でその CSV を読み込みます。Google Sheets API やサービスアカウントは使いません。

## 構成

```text
Python -> GitHub Actions -> GitHub raw CSV -> Google Sheets(IMPORTDATA)
```

## ディレクトリ構成

```text
.
├─ .github/workflows/update_trade.yml
├─ config/master_codes.csv
├─ data/raw_trade.csv
├─ data/calc_unit_price.csv
├─ requirements.txt
├─ README.md
└─ src
   ├─ config.py
   ├─ customs_fetcher.py
   ├─ file_store.py
   ├─ logging_utils.py
   ├─ main.py
   └─ transformers.py
```

## セットアップ

### 1. Python を用意する

Python 3.11 を使います。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. `config/master_codes.csv` を編集する

`enabled = 1` の行だけが対象です。列名は多少揺れても吸収しますが、以下の意味を想定しています。

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

### 3. ローカル実行

前月分を取得:

```powershell
python src/main.py
```

対象年月を指定:

```powershell
python src/main.py --year-month 2026-03
```

CSV 更新なしで確認:

```powershell
python src/main.py --year-month 2026-03 --dry-run
```

## 出力ファイル

### `data/raw_trade.csv`

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

一意キーは `year_month + hs_code + country_code` です。同じキーは上書きします。

### `data/calc_unit_price.csv`

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

一意キーは `year_month + hs_code + country_code` です。同じキーは上書きします。

## 単価計算ルール

- `円/KG`: `unit_multiplier = 1`
- `円/MT`: `unit_multiplier = 1000`
- `円/KL`: 税関データの第2数量単位が `KL` のときだけ `unit_multiplier = 1`
- それ以外は warning を出して `calc_unit_price.csv` には保存しません

計算式:

```text
unit_price = import_value_yen * unit_multiplier / quantity_2
```

以下の場合は `raw_trade.csv` のみ保存し、`calc_unit_price.csv` は保存しません。

- 金額が空
- 第2数量が空
- 第2数量が 0

## GitHub Actions

ワークフローは `.github/workflows/update_trade.yml` です。

- `schedule`: 毎月 18 日 06:00 JST 相当
- `workflow_dispatch`: 手動実行
- Python 3.11 を使用
- 更新された `data/raw_trade.csv` と `data/calc_unit_price.csv` を自動 commit / push

Secrets は不要です。

補足:

- 指定した年月のファイルが e-Stat で未公開の場合は、その年月以前で直近の公開月に自動フォールバックします
- 例: 2026-04-14 時点で `2026-03` が未公開なら `2026-02` を取得します

## Google Sheets 設定

Google Sheets 側では `IMPORTDATA()` で GitHub の raw CSV を読み込みます。

`raw_trade` シートの例:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/tomoki1982/japan-customs-trade-batch/main/data/raw_trade.csv")
```

`calc_unit_price` シートの例:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/tomoki1982/japan-customs-trade-batch/main/data/calc_unit_price.csv")
```

注意:

- `master_codes` は Google Sheets ではなく `config/master_codes.csv` を元データとして管理します
- `master_codes` を更新したいときは、このリポジトリの CSV を編集して commit します

## ログ

以下を INFO / WARNING ログに出します。

- `master_codes` 読み込み件数
- 税関データ取得件数
- 対象レコード抽出件数
- `raw_trade` 保存件数
- `calc_unit_price` 保存件数
- warning 件数

## 前提・仮定

この実装は、まず動く最小構成を優先しています。税関データの実ファイル仕様は月次更新や e-Stat 側の出し分けに影響されるため、以下の前提で実装しています。

1. 取得元 URL は財務省貿易統計サイトの e-Stat CSV 一覧を起点にしています。
   - [Trade Statistics (Download)](https://www.customs.go.jp/toukei/info/tsdl_e.htm)
   - [Commodity by Country Import](https://www.e-stat.go.jp/en/stat-search/files?cycle=1&cycle_facet=cycle&data=1&layout=datalist&metadata=1&page=1&tclass1=000001013180&tclass2=000001013182&tclass3val=0&toukei=00350300&tstat=000001013141)
2. 月次ファイルは章ごとの CSV に分かれているため、対象 HS コードの先頭 2 桁から必要章だけ取得します。
3. 金額は e-Stat の説明上 `1,000YEN` 単位のため、コード内では `import_value_yen` として扱うために 1000 倍しています。
4. CSV の列名は日本語/英語や表記ゆれがある前提で、代表的な別名を吸収する実装にしています。
5. `country_code` は `config/master_codes.csv` では ISO Alpha-2 を推奨します。
   - 内部では財務省の国コード表から Customs 独自の数値コードを解決するようにしています。
   - [Country code list](https://www.customs.go.jp/toukei/sankou/code/country_e.htm)
6. 数量単位は FAQ の略号説明を前提に `KG` `MT` `KL` 等を扱います。
   - [数量単位の略号](https://www.customs.go.jp/toukei/sankou/howto/faq.htm)
7. 税関 CSV の実列名が大きく変わった場合は `src/transformers.py` のヘッダー別名定義を更新してください。

## 拡張方針

将来、鉱工業生産や企業物価指数などを追加することを想定し、以下のように責務を分離しています。

- `customs_fetcher.py`: 外部統計ソースからの取得
- `transformers.py`: 列名吸収、抽出、整形、単価計算
- `file_store.py`: ローカル CSV の読み書き
- `main.py`: 実行フロー制御
