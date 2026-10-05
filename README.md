# Culinary Expansion

Minecraft Java Edition **26.3 / Forge 66.0.5 / JDK 25** 向けに、料理系のアイテムとレシピを追加するMODです。

料理の種類や調理レシピを拡張していくプロジェクトで、現在のv0.1.0では最初の料理として目玉焼きを実装しています。

## ダウンロード

**[ダウンロードページを開く](https://lotcarnage.github.io/minecraft-culinary-expansion/deliverables/)**

配布用JAR、SHA-256チェックサム、導入手順を掲載しています。Minecraft 26.3とForge 66.0.5を使用し、ダウンロードしたJARをゲームディレクトリの`mods`に配置してください。

リポジトリ内のページは[deliverables/index.html](deliverables/index.html)です。公開URLはGitHub Pagesのデプロイ完了後に利用できます。

## 現在の追加料理

- 卵1個をかまどで200 tick（10秒）、または燻製器で基準200 tick（通常の実調理時間は5秒）加熱すると目玉焼き1個になります。燃料が必要です。
- 満腹度を5、隠し満腹度を6回復します。最大64個スタックできます。
- クリエイティブの「食べ物と飲み物」に表示されます。
- 卵を入手するとレシピ本に登録されます。
- 日本語・英語の名前と16×16のオリジナルテクスチャを同梱しています。

## 開発環境

Python 3.9以上と64-bit JDK 25をインストールし、`JAVA_HOME`をJDKのディレクトリに設定してください。Gradleの別途インストールは不要です。初回はインターネット接続が必要です。

```sh
# 配布用JARをビルド（リポジトリのルートで実行）
python helper/build_deliverable.py
# JDKを明示する場合
python helper/build_deliverable.py --java-home "C:\path\to\jdk-25"
# 開発用クライアント起動
./build/gradlew.bat --project-dir build --project-cache-dir intermediate/gradle-cache runClient
# IntelliJ IDEAでbuild/build.gradleを開いてGradleプロジェクトとして読み込めます。
```

配布物は `deliverables/downloads/culinary-expansion-26.3-0.1.0.jar` と同名の `.jar.sha256` です。ビルド失敗時はスクリプトも失敗し、配布物の生成に進みません。過去バージョンのdeliverables内のファイルは残るため、配布時は表示されたファイル名を使用してください。

Windows・Linux・macOSで同じPythonスクリプトを使用します。環境によっては`python`を`python3`（Linux/macOS）または`py -3`（Windows）に読み替えてください。追加のPythonパッケージやPowerShellは不要です。Gradle WrapperをOSに応じて呼び分け、チェックサム生成と公開ページ更新まで実行します。Linux/macOSの開発用クライアント起動は`sh ./build/gradlew --project-dir build --project-cache-dir intermediate/gradle-cache runClient`です。

## 導入・動作確認

Minecraft 26.3にForge 66.0.5を導入し、生成したJARをゲームディレクトリの`mods`にコピーします。マルチプレイではサーバー・クライアント両方に同じMODを入れてください。Fabric APIなど追加MODは不要です。

1. MOD一覧にCulinary Expansionが表示されることを確認。
2. 卵を入手して、かまどと燻製器に卵・燃料を入れ、各1個の目玉焼きができることを確認。
3. 空腹状態で食べられること、クリエイティブの食べ物タブに表示されること、日本語設定で「目玉焼き」と表示されることを確認。
4. コマンドで取り出す場合は `/give @s culinary_expansion:fried_egg`。

## 構成と拡張

- `document/`: 開発用文書。
- `deliverables/`: 公開用HTML・画像・配布JAR・チェックサム。
- `intermediate/`: Gradleの作業用出力（クラス・一時JAR・レポート等、Git管理対象外）。
- `intermediate/gradle-cache/`: Gradleのプロジェクトキャッシュ（Git管理対象外）。
- `build/.gradle/`: ForgeGradleが自動生成する依存情報キャッシュ（Git管理対象外）。
- `build/`: Gradle構成・Wrapper・ページテンプレート。
- `helper/`: 開発補助スクリプト。
- [リソース管理一覧](document/resource_dashboard.html): ソース・モデル・レシピ・画像ファイル等の管理用メタ情報。
- [追加アイテム一覧](document/item_dashboard.html): レシピ・スタック数・使用効果・テクスチャ等の開発用ダッシュボード。`python helper/generate_item_dashboard.py`で再生成。

- `source/items_project.json`: GUIエディターの編集元となる単一のアイテムプロジェクト。
- `source/main/java/dev/lotcarnage/culinaryexpansion/ModItems.java`: 自動生成されるアイテム登録・食事性能・クリエイティブタブ登録。
- `source/main/resources/data/culinary_expansion/recipe/`: 調理レシピ。26.3ではフォルダー名は単数形の`recipe`です。
- `source/main/resources/data/culinary_expansion/advancement/`: レシピ本の解放条件。
- `source/main/resources/assets/culinary_expansion/`: 翻訳・モデル・テクスチャ。
- `build/gradle.properties`: MODバージョンとMinecraft/Forgeのバージョン。
- `helper/build_deliverable.py`: クリーンビルド・配布用コピー・チェックサム生成。

MinecraftやForgeの対象を変更する場合は、Gradle設定に加え`META-INF/mods.toml`の依存範囲と各バージョンのAPI・データ形式も更新してください。

ソースコードは[MITライセンス](LICENSE)で公開しています。Forge公式MDKのGradle Wrapperを使用しています。

画像素材（アイテムのテクスチャを含む）はMITライセンスの適用対象外です。画像素材の著作権その他の権利はすべて各素材の作者に帰属します。作者の許可なく、画像素材を再頒布、加工、販売その他の二次利用をすることを禁止します。

公式資料: [Forge 26.3](https://files.minecraftforge.net/net/minecraftforge/forge/index_26.3.html)、[開発環境](https://docs.minecraftforge.net/en/latest/gettingstarted/)、[Forge 26.3公式MDK](https://maven.minecraftforge.net/net/minecraftforge/forge/26.3-66.0.5/forge-26.3-66.0.5-mdk.zip)。

## GitHub Pagesで配布

`deliverables/index.html`がダウンロードページ、`deliverables/downloads/`が配布JARとSHA-256、`deliverables/assets/`が画像です。相対リンクなのでリポジトリ配下のPages URLでも利用できます。

`python helper/build_deliverable.py`はビルド成功後にPages用ファイルも更新します。既存のintermediate/gradle-output/libsからページだけ更新する場合は `python helper/build_deliverable.py --pages-only` を実行します。ページのデザイン・文章は `build/download-page.template.html` を編集してください。バージョン・ファイル名・チェックサムは `build/gradle.properties` と生成JARから自動反映されます。旧バージョンのダウンロードファイルは保持されます。

公開手順:

1. `deliverables/`とルートの`.nojekyll`を含む変更をGitHubの`main`ブランチにコミット・pushします。
2. リポジトリの **Settings → Pages → Build and deployment** で **Deploy from a branch** を選択します。
3. **main / /(root)** を選択して保存します。
4. デプロイ完了後、[ダウンロードページ](https://lotcarnage.github.io/minecraft-culinary-expansion/deliverables/)でJARをダウンロードできます。

手順の公式資料: [GitHub Pagesの公開元設定](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。

## GUIアイテムエディター

`python helper/item_editor.py`で、1アイテム1行・1属性1列のテーブルで比較・選択し、別の編集ペインで値を編集してアイテムを追加・変更・削除できます。設定は`source/items_project.json`の1ファイルにまとめ、代表名からJava定義・レシピ・モデル・各種識別子を生成します。削除時も画像は保持します。

操作の詳細は[アイテムエディター](document/item_editor.md)を参照してください。編集後は「定義へ反映」を実行し、`python helper/build_deliverable.py`で再ビルドしてください。
