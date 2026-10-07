# Culinary Expansion

Minecraft Java Edition向けに、料理系のアイテムとレシピを拡張するForge MODの開発リポジトリです。MODのソース、アイテム定義を編集する開発ツール、ビルド構成、配布ページを管理します。

## ダウンロード

**[ダウンロードページを開く](https://lotcarnage.github.io/minecraft-culinary-expansion/deliverables/)**

配布JAR、対応バージョン、チェックサム、導入手順はダウンロードページを参照してください。料理の効果・回復量・材料・クラフト配置は [料理図鑑](deliverables/foods.html) で検索・比較できます。

ページの生成元は `build/download-page.template.html`、公開ファイルは `deliverables/index.html` です。

## リポジトリ構成

| ディレクトリ | 用途 |
|---|---|
| `build/` | Gradle構成、Wrapper、配布ページのテンプレート。 |
| `source/` | Javaソース、ゲーム用リソース、アイテムの編集元JSON、公式食料の参考データ。 |
| `document/` | 開発用文書と自動生成する管理一覧。 |
| `helper/` | アイテムエディター、一覧生成、ビルド・配布補助スクリプト、テスト。 |
| `deliverables/` | 公開用HTML、画像、配布JAR、チェックサム。 |
| `intermediate/` | クラス、一時JAR、キャッシュ、レポートなどの中間成果物。Git管理対象外。 |

Minecraft・Forgeのバージョンは `build/gradle.properties`、MODのバージョンは `source/items_project.json` の `version`、依存範囲は `source/main/resources/META-INF/mods.toml` で管理します。MODのバージョンは人間が必要に応じて更新するメタ情報で、自動更新しません。JAR名は `culinary-expansion-<Minecraftバージョン>-<プロジェクトバージョン>.jar` です。

## 開発とビルド

Python 3.9以上と64-bit JDK 25が必要です。GUIにはPython標準のTkinterを使用します。Gradleは同梱のWrapperを使うため、別途インストールする必要はありません。初回ビルドにはインターネット接続が必要です。

リポジトリのルートで実行します。

```sh
# アイテム定義を編集
python helper/item_editor.py

# 保存済みJSONから定義を生成し、配布JARと公開ページを更新
python helper/build_deliverable.py

# JDKの場所を指定する場合
python helper/build_deliverable.py --java-home "JDKのディレクトリ"

# 開発用の管理一覧を生成
python helper/generate_item_dashboard.py

# 自動テスト
python -m unittest discover -s helper -p "test_*.py"
```

Windows・Linux・macOSで同じPythonスクリプトを使用できます。環境に応じて `python` を `python3` または `py -3` に読み替えてください。LinuxでTkinterがない場合はOSのパッケージ管理から追加してください。

アイテム編集の保存先は `source/items_project.json` です。ビルドスクリプトは保存済みJSONからJava・リソース・管理一覧を生成し、GradleでビルドしてJARを検査します。検査に成功した配布物を `deliverables/` に配置します。利用者向けの料理図鑑 `deliverables/foods.html` も生成します。生成元は `build/food-guide.template.html` と `helper/generate_food_guide.py` です。掲載対象・効果・レシピは `source/items_project.json` の組込み有無と属性から取得し、無効な料理と、その料理を材料に使うレシピは除外します。画像を埋め込むためオフラインでも閲覧できます。使用するJDKは `JAVA_HOME` または `--java-home` で指定できます。

配布物生成の順序は「JSONから生成 → Gradleビルド → JAR検査 → `deliverables/downloads/`とチェックサム・配布ページを更新」です。このスクリプトの操作はリポジトリ内に閉じ、Minecraftのゲームフォルダへのインストールは行いません。完了メッセージと終了コード0を確認してください。失敗時は以後の工程を実行せず、古い配布物が残っていても今回の生成結果として扱いません。

WindowsのPATHがJava 8を指している場合も、`intermediate/jdk25/`以下に展開済みのJDK 25があれば自動で使います。Gradleのキャッシュは`intermediate/gradle-user-home/`に保存します（`GRADLE_USER_HOME`指定時はその値を優先します）。Pythonファイルの関連付けに依存せず、上記のように`python helper/build_deliverable.py`で実行してください。

操作の詳細は[アイテムエディターの開発文書](document/item_editor.md)、開発用クライアントの起動などは[開発文書](document/README.md)を参照してください。

## 開発用の管理一覧

- [アイテム一覧](document/item_dashboard.html)：編集元の定義から生成する、アイテム属性・レシピ・画像の比較用一覧です。
- [リソース管理一覧](document/resource_dashboard.html)：定義ファイル、識別子、画像などを確認する一覧です。

アイテムごとの最新の値は編集元JSONと生成された一覧で管理します。

## GitHub Pagesで配布

ローカルでビルドした `deliverables/` とルートの `.nojekyll` をコミット・pushして公開します。専用のGitHub Actionsワークフローをリポジトリに用意する必要はありません。

GitHubの **Settings → Pages** で **Deploy from a branch**、**main / /(root)** を指定します。公開処理が完了すると、READMEのダウンロードリンクから `deliverables/index.html` にアクセスできます。

既存のビルド済みJARから公開ページだけを更新する場合は、`python helper/build_deliverable.py --pages-only` を実行してください。

[GitHub Pagesの公開元設定](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

## ライセンス

ソースコードは[MITライセンス](LICENSE)で公開しています。Forge公式MDKのGradle Wrapperを使用しています。

画像素材（アイテムのテクスチャを含む）はMITライセンスの適用対象外です。画像素材の著作権その他の権利はすべて各素材の作者に帰属します。作者の許可なく、画像素材を再頒布、加工、販売その他の二次利用をすることを禁止します。
