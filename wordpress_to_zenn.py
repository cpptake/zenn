"""Convert saved WordPress JSON to unpublished Zenn Markdown (offline)."""
from __future__ import annotations
import argparse
from dataclasses import dataclass, field
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, quote, parse_qs
from wordpress_exporter import write_json


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)

    def text(self) -> str:
        return ''.join(c if isinstance(c, str) else c.text() for c in self.children)

    def descendants(self, tag: str) -> list[Node]:
        return [n for c in self.children if isinstance(c, Node)
                for n in ([c] if c.tag == tag else []) + c.descendants(tag)]


class Tree(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: v or '' for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_map(raw: Path, images: Path) -> dict[str, str]:
    """Recover flattened names by hash, never by ambiguous basename alone."""
    hashes: dict[str, list[str]] = {}
    for p in sorted(images.iterdir()):
        if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
            hashes.setdefault(digest(p), []).append(p.name)
    mapping = {}
    for p in sorted(raw.rglob('*')):
        if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
            candidates = hashes.get(digest(p), [])
            if candidates:
                name = p.name if p.name in candidates else candidates[0]
                mapping[p.relative_to(raw).as_posix()] = name
    return mapping


def escape(text: str) -> str:
    # HTML collapses ordinary whitespace; preserve nonbreaking/full-width spaces.
    text = re.sub(r'[\t\r\n ]+', ' ', text)
    return re.sub(r'([\\`*_\[\]<>|])', r'\\\1', text)


def destination(url: str) -> str:
    return quote(url, safe="/:?&=#%+~@!$;,._-[]")


class Converter:
    def __init__(self, mapping: dict[str, str], images: Path):
        self.mapping = mapping
        self.images = images
        self.issues: list[dict] = []
        self.codes: list[tuple[str, str]] = []
        self.code_sources: list[str] = []
        self.paragraphs: list[str] = []
        self.local_images: set[str] = set()

    def issue(self, kind: str, detail: str):
        self.issues.append({'kind': kind, 'detail': detail})

    def image(self, node: Node) -> str:
        url = node.attrs.get('src') or node.attrs.get('data-src', '')
        if 'blogcard-' in node.attrs.get('class', ''):
            self.issue('card_decoration_removed', url)
            return ''
        if url.startswith('//'):
            url = 'https:' + url
        parsed = urlsplit(url)
        if parsed.path.lower().endswith('.gif'):
            self.issue('gif_skipped', url)
            return ''
        key = unquote(parsed.path).split('/wp-content/uploads/', 1)
        name = self.mapping.get(key[1]) if len(key) == 2 and parsed.hostname in {'cpptake.com', 'www.cpptake.com'} else None
        if name:
            if (self.images / name).stat().st_size > 3_000_000:
                self.issue('oversize_image', name)
            self.local_images.add(name)
            url = '/images/' + destination(name)
        else:
            self.issue('unresolved_image', url)
            # Preserve access to unavailable external images without remote embeds.
            return f'[{escape(node.attrs.get("alt") or "画像")}]({destination(url)})' if url else ''
        alt = escape(node.attrs.get('alt', ''))
        return f'![{alt}]({destination(url)})' if url else alt

    def children(self, node: Node) -> str:
        return ''.join(self.render(c) for c in node.children)

    def render(self, node: Node | str) -> str:
        if isinstance(node, str):
            return escape(node)
        tag = node.tag
        if tag in {'script', 'style'}:
            self.issue('removed_script_or_style', tag)
            return ''
        if tag == 'img':
            return self.image(node)
        if tag == 'pre':
            code = node.text()
            self.code_sources.append(code)
            classes = node.attrs.get('class', '') + ' ' + ' '.join(c.attrs.get('class', '') for c in node.descendants('code'))
            match = re.search(r'(?:language-|lang-)([\w+-]+)', classes)
            language = match[1] if match else ''
            fence = '`' * max(3, max((len(m[0]) + 1 for m in re.finditer(r'`+', code)), default=3))
            block = f'\n\n{fence}{language}\n{code}' + ('' if code.endswith('\n') else '\n') + f'{fence}\n\n'
            token = f'\x00CODE{len(self.codes)}\x00'
            self.codes.append((token, block))
            return '\n\n' + token + '\n\n'
        if tag == 'code':
            text = node.text()
            fence = '`' * max(1, max((len(m[0]) + 1 for m in re.finditer(r'`+', text)), default=1))
            pad = ' ' if text.startswith(('`', ' ')) or text.endswith(('`', ' ')) else ''
            return fence + pad + text + pad + fence
        if tag == 'iframe':
            url = node.attrs.get('src', '')
            if url.startswith('//'):
                url = 'https:' + url
            self.issue('iframe_to_link', url)
            parsed = urlsplit(url)
            params = parse_qs(parsed.query)
            if parsed.hostname == 'rcm-fe.amazon-adsystem.com' and params.get('asins'):
                url = 'https://www.amazon.co.jp/dp/' + params['asins'][0].split(',')[0]
            elif parsed.hostname == 'hatenablog-parts.com' and params.get('url'):
                url = params['url'][0]
            return f'\n\n[埋め込みコンテンツ]({destination(url)})\n\n' if url else ''
        if tag == 'table':
            rows = []
            for row in node.descendants('tr'):
                cells = [c for c in row.children if isinstance(c, Node) and c.tag in {'th', 'td'}]
                rows.append([self.children(c).strip().replace('\n', ' ') for c in cells])
                if any(c.attrs.get('rowspan', '1') != '1' or c.attrs.get('colspan', '1') != '1' for c in cells):
                    self.issue('table_span_needs_review', node.text()[:100])
            if not rows:
                return ''
            width = max(map(len, rows))
            has_header = bool(node.descendants('th'))
            if not has_header:
                rows.insert(0, [''] * width)
            lines = ['| ' + ' | '.join(row + [''] * (width - len(row))) + ' |' for row in rows]
            lines.insert(1, '| ' + ' | '.join(['---'] * width) + ' |')
            return '\n\n' + '\n'.join(lines) + '\n\n'
        if tag in {'ul', 'ol'}:
            lines = []
            start = int(node.attrs.get('start', '1'))
            for i, child in enumerate(c for c in node.children if isinstance(c, Node) and c.tag == 'li'):
                marker = f'{start+i}. ' if tag == 'ol' else '- '
                content = self.children(child).strip()
                lines.append(marker + content.replace('\n', '\n' + ' ' * len(marker)))
            return '\n\n' + '\n'.join(lines) + '\n\n'
        content = self.children(node)
        if tag == 'a':
            url = node.attrs.get('href', '')
            if url.startswith('//'):
                url = 'https:' + url
            # No multiline/block markup inside Markdown link labels.
            label = re.sub(r'\s+', ' ', content).strip()
            return f'[{label}]({destination(url)})' if url and label else content
        if re.fullmatch(r'h[1-6]', tag):
            return '\n\n' + '#' * int(tag[1]) + ' ' + content.strip() + '\n\n'
        if tag in {'strong', 'b', 'em', 'i', 'del', 's'}:
            marker = {'strong': '**', 'b': '**', 'em': '*', 'i': '*', 'del': '~~', 's': '~~'}[tag]
            return marker + content.strip() + marker if content.strip() else content
        if tag == 'blockquote':
            return '\n\n' + '\n'.join('> ' + line for line in content.strip().splitlines()) + '\n\n'
        if tag == 'br':
            return '  \n'
        if tag == 'hr':
            return '\n\n---\n\n'
        if tag == 'figcaption':
            return '\n*' + content.strip() + '*\n'
        if tag in {'p', 'div', 'figure'}:
            if tag == 'p' and not node.descendants('img') and not node.descendants('code'):
                self.paragraphs.append(node.text())
            return '\n\n' + content.strip() + '\n\n' if content.strip() else ''
        if tag not in {'root', 'span', 'cite', 'li', 'tbody', 'tr', 'td', 'th'}:
            self.issue('unknown_html', tag)
        return content

    def convert(self, source: str) -> str:
        tree = Tree(source)
        body = self.render(tree.root)
        body = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', body).strip() + '\n'
        for token, block in self.codes:
            body = body.replace(token, block.strip('\n'))
        # Verify fenced code content survived byte-for-byte (apart from final newline).
        for code in self.code_sources:
            if code not in body:
                raise ValueError('Code content changed during conversion')
        return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, default=Path('wordpress_export'))
    parser.add_argument('--raw-images', type=Path, default=Path('raw_images'))
    parser.add_argument('--images', type=Path, default=Path('images'))
    parser.add_argument('--output', type=Path, default=Path('articles'))
    parser.add_argument('--overwrite', action='store_true', help='replace existing generated files')
    args = parser.parse_args()
    mapping = image_map(args.raw_images, args.images)
    index = json.loads((args.export / 'index.json').read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    report = []
    pending = []
    for item in index:
        post = json.loads((args.export / item['raw_file']).read_text(encoding='utf-8'))
        slug = f'wordpress-{post["id"]:06d}'
        title = html.unescape(post['title']['rendered'])
        if len(title) > 70:
            raise ValueError(f'Title exceeds 70 characters: {post["id"]}')
        converter = Converter(mapping, args.images)
        body = converter.convert(post['content']['rendered'])
        header = '---\ntitle: ' + json.dumps(title, ensure_ascii=False) + '\nemoji: "📝"\ntype: "tech"\ntopics: []\npublished: false\n---\n\n'
        path = args.output / f'{slug}.md'
        if path.exists() and path.read_text(encoding='utf-8') != header + body and not args.overwrite:
            raise FileExistsError(f'Refusing to overwrite existing article: {path}')
        pending.append((path, header + body))
        report.append({'id': post['id'], 'source_url': post['link'], 'file': str(path),
                       'code_blocks_verified': len(converter.code_sources),
                       'local_images': sorted(converter.local_images), 'issues': converter.issues})
    for path, text in pending:
        if not path.exists() or args.overwrite:
            with path.open('w' if args.overwrite else 'x', encoding='utf-8') as stream:
                stream.write(text)
    write_json(args.export / 'conversion_report.json', report)
    print(f'Generated {len(report)} unpublished articles; see {args.export}/conversion_report.json')


if __name__ == '__main__':
    main()
