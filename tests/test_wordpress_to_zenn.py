import unittest
from pathlib import Path
import tempfile
from wordpress_to_zenn import Converter, image_map


class ConversionTests(unittest.TestCase):
    def test_prose_and_code(self):
        c = Converter({}, Path('images'))
        code = 'a = [i for i in range(3)]\n\nprint("<文字>")\n'
        body = c.convert('<h2>見出し</h2><p>言い回し<strong>そのまま</strong>。</p><pre><code>'
                         + code.replace('<', '&lt;').replace('>', '&gt;') + '</code></pre>')
        self.assertIn('## 見出し', body)
        self.assertIn('言い回し**そのまま**。', body)
        self.assertIn(code, body)
        self.assertEqual(len(c.code_sources), 1)

    def test_images_gif_and_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'image__2.png').write_bytes(b'image')
            c = Converter({'2020/01/image.png': 'image__2.png'}, root)
            body = c.convert('<img src="https://cpptake.com/wp-content/uploads/2020/01/image.png" alt="図">'
                             '<img src="https://example.com/animated.gif">'
                             '<img src="https://example.com/other.png">')
            self.assertIn('![図](/images/image__2.png)', body)
            self.assertNotIn('animated.gif', body)
            self.assertIn('[画像](https://example.com/other.png)', body)

    def test_hash_mapping_with_duplicate_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, images = root / 'raw', root / 'images'
            images.mkdir()
            for month, content, name in [('01', b'a', 'image.png'), ('02', b'b', 'image__2.png')]:
                path = raw / month
                path.mkdir(parents=True)
                (path / 'image.png').write_bytes(content)
                (images / name).write_bytes(content)
            self.assertEqual(image_map(raw, images), {'01/image.png': 'image.png', '02/image.png': 'image__2.png'})

    def test_iframe_and_table(self):
        c = Converter({}, Path('images'))
        body = c.convert('<iframe src="https://rcm-fe.amazon-adsystem.com/e/cm?asins=B123"></iframe>'
                         '<table><tr><td>本文</td><td>値</td></tr></table>')
        self.assertIn('https://www.amazon.co.jp/dp/B123', body)
        self.assertIn('| 本文 | 値 |', body)
        self.assertIn('| --- | --- |', body)

    def test_fence_and_lists(self):
        c = Converter({}, Path('images'))
        body = c.convert('<pre><code>```\ncode</code></pre><ul><li>項目<ul><li>子</li></ul></li></ul>')
        self.assertIn('````\n```\ncode\n````', body)
        self.assertIn('- 項目', body)
        self.assertIn('  - 子', body)
