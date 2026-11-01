---
title: "【PyAutoGUI】Pythonでマウスの自動操作スクリプトを実装"
emoji: "📝"
type: "tech"
topics: ["python", "pyautogui"]
published: true
---

## 概要

Pythonでマウスを自動操作するスクリプトを作成したので、コードを記しておきます。

マウスの操作には、PyAutoGUIというライブラリを利用しました。このライブラリはマウスの移動、クリックなどGUI操作に関する関数がたくさん実装されている便利なライブラリです。公式リファレンス[こちら](https://pyautogui.readthedocs.io/en/latest/#)にあるのでご参照ください。

### 環境

Python 3.7.3

PyAutoGUI 0.9.52

## 実装

### やりたい事

マウスを触らずに、マウスのカーソルが画面上をランダムに動き回るスクリプトを書きます。

なんでこんなものを作ったかというと、在宅勤務中が始まってから、チャットツールが退席中になっている人がいると「あいつサボってない？」みたいなことが会社でよく話題になっていたためです。

そういう方のためのスリープ対策兼、遊びで作りました。

### 作成

作成したコードが下記になってます。

```python
#マウス自動操作スクリプト
import pyautogui
import sys
import random
import time

print('Press Ctr-C when you want to stop')

while True:
    try:
        #ランダムなx,yの位置を定義
        x = random.randint(100,1600)
        y = random.randint(100,1000)
            #pass
        #マウスを移動
        pyautogui.moveTo(x,y,0.3)
        
        time.sleep(0.5)
            
    except:
        #Ctr-Cでループを抜ける
        print('STOP')
        sys.exit(0)
```

利用したPyAutoGUIの関数は、moveTo関数のみです。

指定のX,Y座標に何秒かけて到達するか。を指定すると使えます。

今回のコードはランダムに発生させたX,Y座標に0.3秒で到達し、0.5秒スリープするという処理になってます。

### 動作確認

上記スクリプトを実行した結果が下記のツイートになります。

> 「今日リモートしてる佐藤さん（仮名）、オフラインの時間長すぎなんだけど寝てるんじゃないの～ｗｗ」  
> みたいな至極どうでもいい話が職場で話題になってたので、オフラインにならないようにマウスの自動操作スクリプト組みました。  
> 明日佐藤さん（仮名）に渡そうと思います。 [pic.twitter.com/2uuVgrn52G](https://t.co/2uuVgrn52G)
> 
> — しぃたけ (@cpp\_take) [May 25, 2021](https://twitter.com/cpp_take/status/1397151217684344835?ref_src=twsrc%5Etfw)

荒ぶってます。

Sleepの時間やマウス速度の引数を変更するともう少し早くしたり遅くしたりも簡単に変更できます。これでPCのスリープも怖くないです。

## まとめ

PyAutoGUIを使って簡単なマウス操作スクリプトを作成しました。

非常に簡単なスクリプトで、実装自体も10分くらいでできました。PyAutoGUIには他の関数も多数あるので、気になる操作を実装してみてください。
