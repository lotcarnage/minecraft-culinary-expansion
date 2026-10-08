# Culinary Expansion

Minecraft Java Edition向けに、料理系のアイテムとレシピを拡張するForge MODとPaperMCプラグインの開発リポジトリです。共通のアイテム定義から両方の配布物を生成します。

## ダウンロード

**[ダウンロードページを開く](https://lotcarnage.github.io/minecraft-culinary-expansion/deliverables/)**

配布JAR、対応バージョン、チェックサム、導入手順はダウンロードページを参照してください。MODに含まれる料理の紹介と、効果・回復量・材料・クラフト配置は [料理図鑑](https://lotcarnage.github.io/minecraft-culinary-expansion/deliverables/foods.html) で検索・比較できます。

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

# Forge版とPaperMC版を両方ビルドして配布物を更新
python helper/build_deliverable.py --platform all

# PaperMC版のみビルド（Forge環境の取得は不要）
python helper/build_deliverable.py --platform paper

# Minecraft 26.2だけをビルド
python helper/build_deliverable.py --platform all --minecraft-version 26.2

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

WindowsのPATHがJava 8を指している場合も、`intermediate/jdk25/`以下に展開済みのJDK 25があれば自動で使います。Windows x64では、`--java-home`と`JAVA_HOME`が未指定でローカルJDKがない場合、`helper/setup_jdk.py`がMicrosoft Build of OpenJDK 25.0.4.1を公式の固定バージョンURLから取得し、公式SHA-256と照合してから同ディレクトリに展開します。取得URLとハッシュは展開先の`download-source.txt`に記録します。システムへのインストールや永続的な環境変数変更は行いません。`python helper/setup_jdk.py`でセットアップだけを実行できます。`intermediate/`を削除した場合も、この手順で復元できます。Pythonは事前にインストールしてください。その他のOS・CPUではJDK 25を用意して`--java-home`で指定します。配布元・ライセンスは[Microsoftの公式案内](https://learn.microsoft.com/en-us/java/openjdk/download)を参照してください。

Gradleのキャッシュは`intermediate/gradle-user-home/`に保存します（`GRADLE_USER_HOME`指定時はその値を優先します）。Pythonファイルの関連付けに依存せず、上記のように`python helper/build_deliverable.py`で実行してください。

操作の詳細は[アイテムエディターの開発文書](document/item_editor.md)、開発用クライアントの起動などは[開発文書](document/README.md)を参照してください。

## 開発用の管理一覧

- [アイテム一覧](document/item_dashboard.html)：編集元の定義から生成する、アイテム属性・レシピ・画像の比較用一覧です。
- [リソース管理一覧](document/resource_dashboard.html)：定義ファイル、識別子、画像などを確認する一覧です。

アイテムごとの最新の値は編集元JSONと生成された一覧で管理します。

## GitHub Pagesで配布

ローカルでビルドした `deliverables/` とルートの `.nojekyll` をコミット・pushして公開します。専用のGitHub Actionsワークフローをリポジトリに用意する必要はありません。

GitHubの **Settings → Pages** で **Deploy from a branch**、**main / /(root)** を指定します。公開処理が完了すると、READMEのダウンロードリンクから `deliverables/index.html` にアクセスできます。

既存のビルド済みJARから公開ページだけを更新する場合は、`python helper/build_deliverable.py --pages-only` を実行してください。

## PaperMC版

Minecraftのビルド対象は既定で26.3と26.2です。`--minecraft-version 26.3`または`26.2`で対象を限定できます。26.2用のForge・Paper APIバージョンは`build/legacy-versions.json`で管理します。プロジェクトのバージョンは両対象で共通です。26.2の中間成果物は`intermediate/gradle-output-26.2/`、`paper-output-26.2/`、`paper-generated-26.2/`に分離し、Forgeの依存範囲とPaperのAPIバージョンを対象に合わせて生成します。選択したすべての対象のビルドと検査が成功してから配布物を更新します。

配布ページ上部のペインは26.3用です。26.2用のJAR・リソースパックとハッシュ値ファイルは、ページ下部の「旧バージョンのダウンロード」にテキストリンクで列挙します。既存の旧版配布物も、ハッシュ値を検査して掲載します。

`--platform`は`forge`（既定）、`paper`、`all`を指定できます。`all`では両方のビルドと成果物の検査に成功した後に配布物を更新します。`--pages-only --platform all`で両方の既存成果物からページを再生成できます。片方だけ更新した場合も、公開ページのもう片方のダウンロード欄を保持します。

Paper版はMinecraft 26.3／26.2・Java 25向けです。Paper APIの固定バージョンは`build/gradle.properties`の`paper_api_version`で管理します。Gradle構成は`build/paper/`、プラグインの実装は`source/paper/java/`、共通JSONからの生成処理は`helper/paper_release.py`です。生成Java・プラグイン定義・リソースパックは`intermediate/paper-generated/`、ビルド済みJARは`intermediate/paper-output/libs/`に保存します。通常は上記のPythonスクリプトで生成とビルドをまとめて実行してください。

`deliverables/downloads/`に次のファイルと、それぞれのSHA-256ファイルを生成します。

- `culinary-expansion-paper-<Minecraftバージョン>-<プロジェクトバージョン>.jar`
- `culinary-expansion-paper-resources-<Minecraftバージョン>-<プロジェクトバージョン>.zip`

JARをPaperサーバーの`plugins/`に入れて再起動します。クライアントにはMODが不要です。リソースパックZIPを参加者の`resourcepacks/`に配置して有効化すると、料理の画像と翻訳名が表示されます。サーバーの`server.properties`の`resource-pack`に公開ZIPのURLを設定して配布することもできます。リソースパックなしでは料理は紙の見た目になります。

共通定義の組込み対象だけを登録し、回復量、満腹度、食べる時間、効果と確率、返却容器、スタック数、クラフト・精錬・燻製・焚き火のレシピを反映します。管理者は`/culinary <アイテムID>`で料理を取得できます（権限`culinary.give`、既定はOP）。料理は通常のレシピでも作成できます。Paper版は既存の紙に専用データを付けて識別するため、Forge版のアイテムIDやワールドデータとは互換性がありません。Forge版のクリエイティブタブやレシピ解除の進捗はPaper版には追加しません。

Paper版はビルド入力のハッシュをJARとリソースパックに記録し、定義・ソース・リソース・設定が変わった状態で`--pages-only`を実行すると再ビルドを要求します。

[GitHub Pagesの公開元設定](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

## ライセンス

ソースコードは[MITライセンス](LICENSE)で公開しています。Forge公式MDKのGradle Wrapperを使用しています。

画像素材（アイテムのテクスチャを含む）はMITライセンスの適用対象外です。画像素材の著作権その他の権利はすべて各素材の作者に帰属します。作者の許可なく、画像素材を再頒布、加工、販売その他の二次利用をすることを禁止します。
