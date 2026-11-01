# WordPress記事の取得とZenn CLI

`wordpress_exporter.py` は https://cpptake.com/wp-json/wp/v2/posts から公開記事を取得します。
RSS、管理画面認証、WordPressへの書き込みは使用しません。
HTMLのMarkdown変換、Zenn投稿、画像ファイルのダウンロードは行いません。

## 環境構築

Python 3.10以降を使用してください。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 最初の3記事の取得

```bash
python wordpress_exporter.py --limit 3
python -m unittest discover -s tests -v
```

`per_page=100` でAPIの1ページを取得し、3記事だけ保存します。
本文を切り詰めたり、言い回しを変更したりしません。公開記事でもパスワード保護された本文は取得失敗として記録します。

```text
wordpress_export/
├── raw/
│   ├── 956.json
│   └── ...
├── index.json
└── export_summary.json
```

- `raw/{id}.json`: APIの記事オブジェクト全体。未知のフィールドも保持し、HTMLはそのまま保存します。JSONの空白等は整形するため、HTTPレスポンスのバイト列そのものではありません。
- `index.json`: 今回保存できた記事のID、タイトル、URL (`link`)、日時、slug、状態、元JSONのパス。
- `export_summary.json`: UTCの取得開始・終了日時、保存件数、失敗件数、API総数・総ページ数、失敗ページ、警告、エラー。

`complete` は今回の目標件数（limit指定時はAPI総数との小さい方）をエラーなしで保存できたかを示します。
`full_export` はAPI総数を保存できたかを示します。失敗や目標件数の不足時は終了コード1になります。
`failure_count` は失敗した記事とページの合計です。失敗ページ内の記事数は不明のため記事単位の失敗数には含めません。
limit指定時もAPI総数との差を警告しますが、予定した件数を保存できれば正常終了します。

ファイルはUTF-8・日本語のまま整形して保存し、同じ記事IDは重複保存しません。
再実行では同じIDのファイルを一時ファイル経由で置換し、一覧とサマリーは今回の結果に更新します。
過去のrawファイルは削除しません。今回の対象は `index.json` を参照してください。
複数プロセスから同じ出力先へ同時実行しないでください。
実行途中の中断では一覧とrawが一致しない可能性があるため、再実行して完了させてください。

## 全記事の取得（3記事の結果を確認した後に手動実行）

```bash
python wordpress_exporter.py
```

`page=1` から `X-WP-TotalPages` の全ページを順番に取得します。
ID昇順で取得し、重複IDを除外します。API総数と保存件数の不一致や取得途中の総数変化を警告します。
取得中の新規公開・削除はAPIのスナップショットを保証できないため、警告が出た場合は再実行して確認してください。

```bash
python wordpress_exporter.py --limit 3 --output wordpress_export_trial --interval 1 --timeout 30 --retries 3
```

既定では呼び出し開始の間隔は最低1秒、各リクエストのタイムアウトは30秒、リトライは初回の後3回です。
タイムアウト、接続エラー、429、5xx、不正JSON・ページ情報は上限付きで再試行します。
指数バックオフと `Retry-After`（秒数・HTTP日時）を使用します。他のHTTPエラーは即座に失敗として記録します。
最初のページの取得失敗時は総ページ数が不明なので終了し、以降のページの失敗時は続くページを取得します。
ログは標準エラーに出力します。ファイルにも残す場合:

```bash
python wordpress_exporter.py --limit 3 2>wordpress_export.log
```

拡張時は `WordPressClient`（通信）、`export_posts`（取得・保存）、`write_json`（永続化）を利用できます。
将来の変換処理は保存済みの元JSONを入力にし、取得処理とは分離してください。

## Zenn CLI

- 記事: `articles/`
- 本: `books/`
- [Zenn CLIの使い方](https://zenn.dev/zenn/articles/zenn-cli-guide)
- [WordPress REST API: Posts](https://developer.wordpress.org/rest-api/reference/posts/)
- [Requestsの使い方](https://requests.readthedocs.io/en/latest/user/quickstart/)

## 保存済み記事をZennの下書きへ変換

```bash
python3 wordpress_to_zenn.py
```

`wordpress_export/index.json` にある記事を読み、`articles/wordpress-{6桁の記事ID}.md` を生成します。
全記事を `published: false`、`type: tech`、`topics: []` にします。topicsは公開前に設定してください。
本文の言い回しを維持し、見出し、段落、リスト、表、リンク、コード、画像をMarkdownへ変換します。
`raw_images/` と `images/` のSHA-256の一致から画像名を復元し、同名画像の取り違えを防ぎます。
GIFは対象外です。リンクカードの装飾画像は除き、カード内のテキストとリンクは保持します。
ローカルにない外部画像は元画像へのリンクにし、iframeはリンクへ変換します。
Amazon広告のiframeは商品ページ、はてなのiframeは元ページへのリンクにします。
スクリプトとHTMLコメントは出力しません。コード中の角括弧はショートコードとして変換しません。
今回の元データには変換が必要な未展開ショートコードは確認されていません。

変換結果と確認事項は `wordpress_export/conversion_report.json` に記録します。
コードブロックの本文一致、参照画像の存在、Front Matter、slugを検証していますが、
外部画像へのリンクや埋め込みの表示は公開前にプレビューで確認してください。

```bash
npx zenn preview
```

既存の記事が異なる内容なら上書きを拒否します。再生成して置き換える場合のみ:

```bash
python3 wordpress_to_zenn.py --overwrite
```

`--export`、`--raw-images`、`--images`、`--output` で入出力ディレクトリを変更できます。
取得元のJSONと画像は変更しません。
