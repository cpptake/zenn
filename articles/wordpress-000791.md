---
title: "kaggle expertになったのでIndoorコンペ、1週間で銅メダル取るためにやったことまとめます"
emoji: "📝"
type: "tech"
topics: ["kaggle"]
published: false
---

![しぃたけ](/images/tio-150x150.jpg)

しぃたけ

kaggle初心者向きです

## はじめに

### KaggleExpertになりました

> Indoorのメダルが反映されてようやくkaggle expertに昇格しました！（去年9月～今年5月の8か月くらい）  
> 機械学習何もわからないですがこれからも精進して参ります。 [pic.twitter.com/JYe1m7hMv5](https://t.co/JYe1m7hMv5)
> 
> — しぃたけ@kaggler (@cpp\_take) [May 18, 2021](https://twitter.com/cpp_take/status/1394583024323362820?ref_src=twsrc%5Etfw)

先日参加していたIndoorコンペで銅メダルを獲得して、念願のKaggle Expertに昇格しました。Kaggle始めて半年ほどメダルが取れなくてく苦しかったのですが、ようやく昇格できて非常に嬉しいです。

ちなみに、今回メダルを獲得できたIndoorコンペは、**コンペ終了1週間前に駆け込み参加して短期間で銅メダル獲得に至ったという経緯があります。**

自分としても1週間でメダル獲得できたのは驚きなので、今回の活動の内容を記録しておきます。自分のようにメダル取れずに困っている誰かの役に立てれば幸いです。

### こんな人向け

- Kaggle始めたけどメダル取ったことなくて挫けそうな人
- これからKaggle始めようと思ってる人
- 1週間で何をしたか気になる人

また、本記事は詳細な解法の紹介ではなく、1週間でどんなことをしたのかを記録することが目的の記事なのでご承知ください。

### 21/5/30　追記

簡単なソリューションだけgithubにアップしました。モデルの作成パートはなく、後処理メインのソリューションなのでご承知ください。

 [GitHub - cpptake/Indoor\_1week\_challenge Contribute to cpptake/Indoor\_1week\_challenge development by creating an account on GitHub. github.com](https://github.com/cpptake/Indoor_1week_challenge)  

### Indoorコンペについて

今回参加したIndoorコンペは[こちら](https://www.kaggle.com/c/indoor-location-navigation)です。

 [Indoor Location & Navigation Identify the position of a smartphone in a shopping mall kaggle.com](https://www.kaggle.com/c/indoor-location-navigation) 

このコンペは、センサーが取り付けられたショッピングモールにスマートフォンをもった被験者を歩かせ、センサーのデータから被験者の位置を推定するというコンペです。今回詳細な内容は説明しないので、上記のリンク先を確認ください。

## やったこと

### 活動のポイント

結論先に行ってしまうと、初心者かつ、時間がないときに取り組むべきは

**Discussionと公開されているCodeの読み込みに尽きると思います。**

詳細は後述しますが、メダル圏内（銅圏）に入るために必要な情報はほとんど、Disucussionに乗ってることが多いです。

また、1日に提出できるサブ数は決まっているので、今回のように1週間しか時間がないのであれば、サブを無駄打ちできません。そのため、まずはDisucussion、公開Codeを読んでコンペの勘所を探ることが先決だと思います。

次項から今回のIndoorコンペでやったことは時系列でまとめていきます。

### 1，2日目　・・・　モデル作成

コンペ参加当初はデータを眺めながら、公開Codeで評価の高いモデルを参考に、実験やアンサンブルを行っていました。（モデルは[MultiOutputMLP](https://www.kaggle.com/joelqv/multioutput-mlp-weighted-loss)、[LSTM](https://www.kaggle.com/joelqv/multioutput-mlp-weighted-loss)などを主に参考にさせていただきました。）

ただ、結果的に今回のコンペで**モデル作成のパートはあまり機能しませんでした。**

理由は、自作のモデルでは公開Codeに上がっているアンサンブルモデル（いわゆる脳死アンサンブル）のscoreに勝てなかったからです。

一般的には嫌われがちな脳死アンサンブルですが、今回はあまりにも時間がなかったので、しばらく公開アンサンブルのモデルをベースラインにすることにしました。

**（LB score : 4.49）**

### 3，4日目　・・・　リーク処理の追加

この辺りから、上がっているほとんどのDisucussionを読み込み始めました。すると、データにいくつかのLeakが報告されているのでそれらを追加するとscore上がるよという内容の[Discussion](https://www.kaggle.com/c/indoor-location-navigation/discussion/234543)を発見しました。

（詳細に言うと、センサーのdevice idとtime stampに法則性があるので、法則通りに後処理を入れるとscoreが上がるというもの。）

上記のDisucussionを参考に様々なリークを追加する実験を行ったところ、LBスコアが向上しました。

**（LB score:**4.49**** ⇒ **4.38)**

### 5日目　・・・　後処理追加

他のネタを探してると後処理についてのDisucussionやNotebookをいろいろと見つけました。

というか、DisucussionやCodeを読んでると、予測モデルに対して、カルマンフィルタや近くのグリッドに予測結果を送付するような後処理の記事が多く、このコンペは後処理コンペなのだと気づきます。

いろいろ、後処理を試してみた結果scoreが向上し、この辺で銅圏内に入ります。（実際にモデルに組み込んだのは[こちら](https://www.kaggle.com/robikscube/indoor-navigation-snap-to-grid-post-processing)のNotebookです。）

**(LB score:4.38 ⇒ 4.33)**

### 6，7日目　・・・　アンサンブル & ハイパラ調整

最後にベースラインにしていた公開アンサンブルモデルに初日に作ったモデルをアンサンブルしたり、後処理のパラメータを追い込んむことでスコアの底上げを図って最終subを行いました。

最終サブ時には順位が96位まで上がってました。ちなみに1日5サブが限度なので全部で35サブ使いきってます。

> Indoor1週間でここまで来ました！1日5サブで35サブ使いきりました！おやすみなさい！ [pic.twitter.com/xeHBkoZirB](https://t.co/xeHBkoZirB)
> 
> — しぃたけ@kaggler (@cpp\_take) [May 17, 2021](https://twitter.com/cpp_take/status/1394301507781099522?ref_src=twsrc%5Etfw)

**(LB score:**4.33**** ⇒**4.26)**

### 結果

結果はPrivateで20位以上shake downしましたが、ギリギリ銅圏内残ってメダル獲得できました。Privateスコアも最後に作ったモデルが一番高かったため、最後まで追い込みをしてよかったです。

> メダル圏外かと思いきや、  
> 確定Scoreで順位上がってギリギリ銅圏入りました！  
> Indoorコンペ1週間チャレンジで初ソロメダル！ [pic.twitter.com/ZUnzUrrJAa](https://t.co/ZUnzUrrJAa)
> 
> — しぃたけ@kaggler (@cpp\_take) [May 18, 2021](https://twitter.com/cpp_take/status/1394487888197214209?ref_src=twsrc%5Etfw)

## 短期間での活動のポイント

前章でも述べた通り、**Discussionと公開されているCodeの読み込みに尽きると思います。**

今回自分が実施した解法についても、オリジナルの解法の部分はほとんどなく、Disucussion、公開Codeに書かれていることを愚直に実装したにすぎません。

むしろ1週間では試しきれないくらいの情報があったので、時間があればもう少しスコアを伸ばす余地があったとすら感じてます。

Kaggleへの取り組み方が分からない方でも、コンペに途中参加される方でも共通して公開されてるデータを読み解くことは重要だと今回身をもって感じました。

## 挫折ポイント

とはいえ、自分も最近までDisucussion読んでても取り組み方がわからず、メダルを逃し続けていたので、挫折するポイントがあると思うので、自分なりに考えられる対策を残しときます。

### 専門用語多すぎ問題

この分野はややこしい横文字の専門用語が多いので、用語がネックになってDisucussionや公開Codeの内容が分からない問題が発生すると思います。

例えば、**validデータを作成する際もk-fold, stratified k-fold, group k-foldなど似たような用語がたくさんあって分かりにくいです。**（なんなら未だによくわかってない。）

これについては、分析の進め方を体系的に説明されているKaggle本などで勉強して、用語になれることが手っ取り早いのかなと思ってます。Kaggle本は下記のものが人気らしいです。

 [[画像](https://ws-fe.amazon-adsystem.com/widgets/q?_encoding=UTF8&MarketPlace=JP&ASIN=B07YTDBC3Z&ServiceVersion=20070822&ID=AsinImage&WS=1&Format=_SL160_&tag=cpptake0a-22)](https://www.amazon.co.jp/gp/product/B07YTDBC3Z/ref=as_li_tl?ie=UTF8&camp=247&creative=1211&creativeASIN=B07YTDBC3Z&linkCode=as2&tag=cpptake0a-22&linkId=716e1637bce96654efff17213f3414c5) [[画像](https://ws-fe.amazon-adsystem.com/widgets/q?_encoding=UTF8&MarketPlace=JP&ASIN=4065190061&ServiceVersion=20070822&ID=AsinImage&WS=1&Format=_SL160_&tag=cpptake0a-22)](https://www.amazon.co.jp/gp/product/4065190061/ref=as_li_tl?ie=UTF8&camp=247&creative=1211&creativeASIN=4065190061&linkCode=as2&tag=cpptake0a-22&linkId=ec9c894a4692fa2509522634bc578938)  

### コンペの期間長すぎ問題

コンペの開始から終了までの期間は平均3か月くらいあるので、長期間コミットし続けると最後の方でスタミナ切れになってしまう現象が多々見受けられます。

これについては、**コンペの終盤の1か月だけ参加するという方法がいいと思います。**現に強い方でも終盤1か月だけ参加の方は多いです。

理由は、後半になるにつれてDisucussionの情報量が増えているので、効率よくコンペを進めることができる＋スタミナ切れを起こさない。みたいなメリットがあるためです。（現に自分も終盤に参加したためにDisucussionが豊富で参考になりました。）

継続が難しい方はこの方法がいいかなと思います。

### Kaggler学歴高すぎ問題

先日[@kurupical](https://twitter.com/kurupical?s=20)さんが興味深いツイートをされてました。

> kaggle expert以上の人に質問です。あなたの学歴は？
> 
> — くるぴー (@kurupical) [May 21, 2021](https://twitter.com/kurupical/status/1395710768851558400?ref_src=twsrc%5Etfw)

どうやら**日本人でKaggle Expert以上の方の半数以上が旧帝、一工、早慶の出身**のようで、地方国立大出身の自分は戦慄してました。（学歴だけで物事を語るのはどうかと思いますが、ここまで顕著だとさすがにビビります。）

学歴に焦って挫折しそうな方、もしおられたら自分のことを思い出してください。

### 英語読めない問題

**DeepL使いましょう。**

自分はKaggle始めた理由の一つが英語に慣れたいという想いがあったのですが、諦めました。みんなでDeepL使いましょう。

## まとめ

Indoorコンペで銅メダルを取ってKaggle Expertになりました。まだまだ雑魚なので今後も精進しようと思います。

また、Disucussionと公開Code読み込めば短期間でも銅メダル取れることが分かったので、Kaggle始めたばかりの方は参考にしていただければと思います。

  [[画像](https://ws-fe.amazon-adsystem.com/widgets/q?_encoding=UTF8&MarketPlace=JP&ASIN=B07YTDBC3Z&ServiceVersion=20070822&ID=AsinImage&WS=1&Format=_SL160_&tag=cpptake0a-22)](https://www.amazon.co.jp/gp/product/B07YTDBC3Z/ref=as_li_tl?ie=UTF8&camp=247&creative=1211&creativeASIN=B07YTDBC3Z&linkCode=as2&tag=cpptake0a-22&linkId=716e1637bce96654efff17213f3414c5) [[画像](https://ws-fe.amazon-adsystem.com/widgets/q?_encoding=UTF8&MarketPlace=JP&ASIN=4065190061&ServiceVersion=20070822&ID=AsinImage&WS=1&Format=_SL160_&tag=cpptake0a-22)](https://www.amazon.co.jp/gp/product/4065190061/ref=as_li_tl?ie=UTF8&camp=247&creative=1211&creativeASIN=4065190061&linkCode=as2&tag=cpptake0a-22&linkId=ec9c894a4692fa2509522634bc578938) [[画像](https://ws-fe.amazon-adsystem.com/widgets/q?_encoding=UTF8&MarketPlace=JP&ASIN=4873117585&ServiceVersion=20070822&ID=AsinImage&WS=1&Format=_SL160_&tag=cpptake0a-22)](https://www.amazon.co.jp/gp/product/4873117585/ref=as_li_tl?ie=UTF8&camp=247&creative=1211&creativeASIN=4873117585&linkCode=as2&tag=cpptake0a-22&linkId=5c02d441bf9bc534fa7d1983d7dbbb3c)
