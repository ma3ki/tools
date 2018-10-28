#Android アプリ Cloud Message の紹介
![ロゴ](https://lh5.ggpht.com/qGtxVcjqoYEm_WRPw7Ebzi83UN3m2_F6qVjdKvgHDrXpzUtQ9D8-kbb7hN2fNnHt5G8=w300)
---
##Google Play URL
https://play.google.com/store/apps/details?id=ma3ki.cloudmessage

##アプリ機能
**プッシュ通知の受信時の機能**
 - メッセージを表示する
 - アラーム音を再生する [アプリ起動中は一度だけ]
 - バイブレーションをする [アプリ起動中は一度だけ]
 - 特定URLにプッシュ通知を受信したことを受信時に応答する
 - 特定URLにプッシュ通知を内容を確認したことを明示的に応答する
 - アプリを起動するとアラーム音、バイブレーションを停止する
 - アラームの履歴を残す(10件)

##用途
 - システム障害時の自動連絡システム

##自動連絡システムの構成
![demo](https://ma3ki.net/cloudmessage/wp-content/uploads/2014/02/system_structure.png)

##自動連絡システムのデモ動画
https://ma3ki.net/cloudmessage/wp-content/uploads/2015/03/CloudMessage480.mov

##プッシュ通知を使用するための準備
1. Google Developers Consoleを開く
2. プロジェクトを作成(Project ID)
3. APIを有効にする
4. Google Cloud Messaging for Android
5. Google Developers Consoleを開く
6. サーバキーの生成(API KEY)

##設定項目(CONFIGUREタブ)
####Project ID
 - 端末とプロジェクトを結びつける為に入力
 - 入力後、Registration することで Registration ID が発行される

####Registration ID
 - プッシュ通知の送信先として使用
 - Copy to Clipboard でコピーするのでメール等に貼り付けできます。

####Registration URL
 - httpで Registration ID , 端末名 , グループ名を、、、

####Http Reply Basic Authentication
 - 各 Http 通信で共通に使用する Basic 認証設定

####Enable Action
 - アラートを受信した際の有効な動作を設定(Alarm, Vibration, Http Reply)

####Google Cloud Messaging Test
 - 自分の端末宛へプッシュ通知を送信する(API Keyが必要)

##詳しくは
https://ma3ki.net/cloudmessage/
