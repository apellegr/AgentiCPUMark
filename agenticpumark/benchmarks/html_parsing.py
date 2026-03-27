"""HTML/DOM Parsing benchmark.

Research agents and web-browsing tools spend significant CPU time parsing
HTML into DOM trees, applying CSS-like selectors, extracting content, and
converting HTML to markdown/plaintext for LLM consumption. MCP fetch servers,
Puppeteer/Playwright scrapers, and web search tools all hit this path.
"""

import html.parser
import re
import random
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_PAGES = 50
NUM_SELECTOR_QUERIES = 200
NUM_MARKDOWN_CONVERSIONS = 40


def _generate_html_page(seed: int) -> str:
    """Generate a realistic HTML page with nested structure."""
    rng = random.Random(seed)
    tags = ["div", "span", "p", "section", "article", "main", "header", "footer", "nav", "aside"]
    classes = [
        "container", "content", "sidebar", "header", "footer", "nav-item",
        "card", "card-body", "list-group", "list-item", "text-muted",
        "btn", "btn-primary", "form-control", "alert", "badge",
        "result-item", "search-result", "article-body", "code-block",
    ]
    words = [
        "the", "agent", "processes", "data", "from", "multiple", "sources",
        "including", "web", "searches", "API", "calls", "and", "file",
        "system", "operations", "to", "build", "comprehensive", "context",
        "for", "reasoning", "about", "complex", "tasks", "that", "require",
        "tool", "orchestration", "across", "different", "modalities",
    ]

    parts = [
        '<!DOCTYPE html><html lang="en"><head>',
        f'<meta charset="utf-8"><title>Page {seed}</title>',
        '<style>.container { max-width: 1200px; } .highlight { color: red; }</style>',
        '</head><body>',
    ]

    def make_text(n: int) -> str:
        return " ".join(rng.choices(words, k=n))

    def make_element(depth: int = 0) -> str:
        if depth > 6:
            return f"<p>{make_text(rng.randint(10, 40))}</p>"
        tag = rng.choice(tags)
        cls = rng.choice(classes)
        id_attr = f' id="el-{seed}-{rng.randint(0, 9999)}"' if rng.random() < 0.3 else ""
        data_attr = f' data-index="{rng.randint(0, 100)}"' if rng.random() < 0.2 else ""
        inner = ""
        if rng.random() < 0.6 and depth < 5:
            num_children = rng.randint(1, 5)
            inner = "".join(make_element(depth + 1) for _ in range(num_children))
        else:
            inner = make_text(rng.randint(5, 30))
        return f'<{tag} class="{cls}"{id_attr}{data_attr}>{inner}</{tag}>'

    # Build page structure
    parts.append('<header class="header"><nav class="nav">')
    for i in range(rng.randint(4, 8)):
        parts.append(f'<a href="/page/{i}" class="nav-item">Link {i}</a>')
    parts.append('</nav></header>')

    parts.append('<main class="container">')
    for _ in range(rng.randint(5, 15)):
        parts.append(make_element(0))
    parts.append('</main>')

    # Table with data (common in search results, dashboards)
    parts.append('<table class="data-table"><thead><tr>')
    cols = rng.randint(3, 8)
    for c in range(cols):
        parts.append(f'<th>Column {c}</th>')
    parts.append('</tr></thead><tbody>')
    for row in range(rng.randint(10, 30)):
        parts.append('<tr>')
        for c in range(cols):
            parts.append(f'<td>{make_text(rng.randint(1, 5))}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')

    # Code blocks (common in technical docs agents scrape)
    for _ in range(rng.randint(1, 3)):
        code_lines = [f"    line_{i} = process({rng.randint(0, 999)})" for i in range(rng.randint(5, 20))]
        parts.append(f'<pre class="code-block"><code>{"&#10;".join(code_lines)}</code></pre>')

    parts.append('<footer class="footer"><p>Footer content</p></footer>')
    parts.append('</body></html>')
    return "\n".join(parts)


class DOMNode:
    """Lightweight DOM node for tree construction and traversal."""

    __slots__ = ("tag", "attrs", "children", "text", "parent")

    def __init__(self, tag: str, attrs: dict[str, str]):
        self.tag = tag
        self.attrs: dict[str, str] = attrs
        self.children: list[DOMNode] = []
        self.text: str = ""
        self.parent: DOMNode | None = None

    def query_by_class(self, cls: str) -> list["DOMNode"]:
        """Find all descendants with the given class."""
        results: list[DOMNode] = []
        if cls in self.attrs.get("class", "").split():
            results.append(self)
        for child in self.children:
            results.extend(child.query_by_class(cls))
        return results

    def query_by_tag(self, tag: str) -> list["DOMNode"]:
        """Find all descendants with the given tag."""
        results: list[DOMNode] = []
        if self.tag == tag:
            results.append(self)
        for child in self.children:
            results.extend(child.query_by_tag(tag))
        return results

    def get_text(self) -> str:
        """Extract all text content recursively."""
        parts = [self.text]
        for child in self.children:
            parts.append(child.get_text())
        return " ".join(p for p in parts if p)

    def depth(self) -> int:
        """Compute tree depth."""
        if not self.children:
            return 1
        return 1 + max(c.depth() for c in self.children)

    def count_nodes(self) -> int:
        """Count total nodes in subtree."""
        return 1 + sum(c.count_nodes() for c in self.children)


class DOMBuilder(html.parser.HTMLParser):
    """Build a DOM tree from HTML using stdlib parser."""

    SELF_CLOSING = frozenset(["br", "hr", "img", "input", "meta", "link", "area", "base", "col"])

    def __init__(self):
        super().__init__()
        self.root = DOMNode("document", {})
        self._stack: list[DOMNode] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v or "" for k, v in attrs}
        node = DOMNode(tag, attr_dict)
        node.parent = self._stack[-1]
        self._stack[-1].children.append(node)
        if tag not in self.SELF_CLOSING:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if len(self._stack) > 1 and self._stack[-1].tag == tag:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped and self._stack:
            self._stack[-1].text += " " + stripped if self._stack[-1].text else stripped


def _html_to_markdown(node: DOMNode) -> str:
    """Convert a DOM tree to markdown (simplified, like MCP fetch does)."""
    if node.tag == "document":
        return "\n".join(_html_to_markdown(c) for c in node.children)

    text = node.text or ""
    children_md = "\n".join(_html_to_markdown(c) for c in node.children)
    content = f"{text} {children_md}".strip() if text else children_md

    if node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(node.tag[1])
        return f"{'#' * level} {content}\n"
    elif node.tag == "p":
        return f"\n{content}\n"
    elif node.tag == "a":
        href = node.attrs.get("href", "")
        return f"[{content}]({href})"
    elif node.tag in ("strong", "b"):
        return f"**{content}**"
    elif node.tag in ("em", "i"):
        return f"*{content}*"
    elif node.tag == "code":
        return f"`{content}`"
    elif node.tag == "pre":
        return f"\n```\n{content}\n```\n"
    elif node.tag == "li":
        return f"- {content}"
    elif node.tag in ("ul", "ol"):
        return content
    elif node.tag == "table":
        return content
    elif node.tag == "tr":
        cells = [_html_to_markdown(c) for c in node.children]
        return "| " + " | ".join(cells) + " |"
    elif node.tag in ("td", "th"):
        return content
    elif node.tag in ("head", "style", "script"):
        return ""
    else:
        return content


class HtmlParsingBenchmark(BaseBenchmark):
    name = "html_parsing"
    description = "DOM tree construction, CSS-like queries, and HTML-to-markdown conversion"
    weight = 0.10

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Parse HTML pages into DOM trees
        pages: list[tuple[str, DOMNode]] = []
        for i in range(NUM_PAGES):
            html_text = _generate_html_page(i)
            builder = DOMBuilder()
            builder.feed(html_text)
            pages.append((html_text, builder.root))
            ops += 1

        # Phase 2: DOM queries (simulating CSS selector matching)
        query_classes = [
            "container", "content", "card", "list-item", "search-result",
            "code-block", "nav-item", "alert", "badge", "form-control",
        ]
        query_tags = ["div", "p", "span", "a", "table", "tr", "td", "pre", "code"]

        for i in range(NUM_SELECTOR_QUERIES):
            _, dom = pages[i % len(pages)]
            # Query by class
            cls = query_classes[i % len(query_classes)]
            matches = dom.query_by_class(cls)
            ops += len(matches)
            # Query by tag
            tag = query_tags[i % len(query_tags)]
            matches = dom.query_by_tag(tag)
            ops += len(matches)

        # Phase 3: Text extraction (agents extract text from DOM for LLM context)
        for _, dom in pages:
            text = dom.get_text()
            _ = len(text)
            ops += dom.count_nodes()

        # Phase 4: HTML to markdown conversion (MCP fetch pattern)
        for i in range(NUM_MARKDOWN_CONVERSIONS):
            _, dom = pages[i % len(pages)]
            md = _html_to_markdown(dom)
            _ = len(md)
            ops += 1

        # Phase 5: Regex-based HTML content extraction
        # Fallback pattern when DOM parsing is too expensive
        tag_pattern = re.compile(r"<(\w+)[^>]*>(.*?)</\1>", re.DOTALL)
        attr_pattern = re.compile(r'(\w+)=["\']([^"\']*)["\']')
        for html_text, _ in pages[:20]:
            tag_matches = tag_pattern.findall(html_text)
            attr_matches = attr_pattern.findall(html_text)
            ops += len(tag_matches) + len(attr_matches)

        return ops
