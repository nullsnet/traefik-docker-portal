Dockerコンテナから情報を収集し、ポータルを表示するWebアプリケーションを作成してください。

## 機能

* /var/run/docker.sockから情報を取得し、labelsに設定されているtraefik.hostをホスト名とする
* ドメイン名とホスト名からURLを生成してWebページに表示する

## ログ

* 起動時
    * リンクをログに出力する
    * 環境変数をログに出力する

## ファイル構成

* HTML、CSS、JavaScriptを別ファイルに切り出す

## 環境変数

* DOMAIN_PREFIX : ドメイン名
* PORTAL_PORT : リッスンするポート番号
* LOG_LEVEL : ログレベル

## CI/CD

* GitHub Actionsでイメージをビルドする
* Container registryに登録する