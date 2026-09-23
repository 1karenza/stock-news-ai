"""Evidence-based summaries and a wrapping, accessible news table."""
import html
import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def extract_article(document, title=""):
    soup = BeautifulSoup(document, "html.parser")
    structured = []

    def visit(value):
        if isinstance(value, dict):
            body = value.get("articleBody")
            if isinstance(body, str):
                structured.append(BeautifulSoup(body, "html.parser").get_text(" ", strip=True))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            visit(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            pass
    for tag in soup.select("script, style, noscript, nav, aside, footer, .related-news, .related-articles"):
        tag.decompose()
    candidates = structured[:]
    for selector in ("[itemprop='articleBody']", ".article-editor", ".mekong-detail-body", ".article-body", ".article-content",
                     ".detail-content", ".content-detail", ".fck_detail", ".entry-content",
                     ".post-content", ".detail__content", "article"):
        for node in soup.select(selector):
            paras = [p.get_text(" ", strip=True) for p in node.select("p")]
            if selector == "article" and title:
                terms = set(re.findall(r"\w{3,}", re.sub(r"\s+-\s+[^-]+$", "", title).lower()))
                words = set(re.findall(r"\w{3,}", node.get_text(" ", strip=True).lower()))
                if (len(paras) < 3 and len(soup.select("article")) > 1) or len(terms & words) < max(2, len(terms)*.35):
                    continue
            text = "\n".join(p for p in paras if len(p) > 35)
            if not text:
                text = node.get_text(" ", strip=True)
            if len(text) >= 180:
                candidates.append(text)
        if candidates:
            break
    if candidates:
        return max(candidates, key=len)[:16000]
    # A publisher description is still useful evidence; don't collect unrelated
    # page-wide paragraphs from navigation, sign-in or consent screens.
    description = soup.select_one('meta[property="og:description"], meta[name="description"]')
    text = description.get("content", "").strip() if description else ""
    if title and text:
        title_words = set(re.findall(r"\w{3,}", title.lower()))
        content_words = set(re.findall(r"\w{3,}", text.lower()))
        if len(title_words & content_words) < 2:
            return ""
    return text


def summary_sentences(item, detail=False):
    title = re.sub(r"\s+-\s+[^-]+$", "", item.get("title", "")).strip()
    source = item.get("article_text") or item.get("summary") or ("" if detail else title)
    source = BeautifulSoup(source, "html.parser").get_text(" ", strip=True)
    source = re.sub(r"\s+", " ", source).strip()
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ỹ0-9\"“])", source)
    unique, seen = [], set()
    for sentence in sentences:
        sentence = sentence.strip()
        key = re.sub(r"\W+", "", sentence.lower())
        if not sentence or (len(sentence) < 30 and (not detail or len(source) >= 160)) or key in seen or (detail and key == re.sub(r"\W+", "", title.lower())):
            continue
        seen.add(key)
        unique.append(sentence)
    if not unique:
        return [title] if title and not detail else []

    # Keep the lead for context, then favour facts, dates and explanations.
    terms = ("doanh thu", "lợi nhuận", "cổ tức", "phát hành", "kỳ hạn", "lãi suất",
             "mục đích", "dự kiến", "so với", "do", "nhằm", "rủi ro", "ngày")
    ranked = sorted(range(1, len(unique)), key=lambda i: (
        -(2 * bool(re.search(r"\d", unique[i])) + sum(t in unique[i].lower() for t in terms)), i))
    limit, budget = (12, 520) if detail else (4, 140)
    selected, words = [0], len(unique[0].split())
    for i in ranked:
        count = len(unique[i].split())
        if len(selected) >= limit:
            break
        if words + count <= budget:
            selected.append(i)
            words += count
    result = [unique[i] for i in sorted(selected)]
    # Bound pathological single-sentence feeds without splitting words.
    if len(result[0].split()) > budget:
        result[0] = " ".join(result[0].split()[:budget]) + "…"
    return result


def news_table(rows):
    """Natural row heights; summary gets most of the available width."""
    cells = []
    for index, row in enumerate(rows, start=1):
        esc = lambda key: html.escape(str(row[key]))
        title = html.escape(str(row.get('Tiêu đề bài báo', '')))
        cells.append(f'<tr><td data-label="Ngày / Mã" class="news-date"><strong>{esc("Mã CK")}</strong><br><span>{esc("Ngày")}</span></td>'
                     f'<td data-label="Tiêu đề bài báo">{title}<br><span class="small-muted">{esc("Loại tin")}</span></td>'
                     f'<td data-label="Tóm tắt"><a class="summary-jump" href="#news-detail-{index}" target="_self" title="Xem tóm tắt" aria-label="Xem tóm tắt tin {index}">↓</a></td></tr>')
    return ('<div class="news-table-wrap"><table class="news-table"><caption>Bảng tổng hợp tin chứng khoán</caption>'
            '<colgroup><col style="width:155px"><col><col style="width:85px"></colgroup>'
            '<thead><tr><th scope="col">Ngày / Mã</th><th scope="col">Tiêu đề bài báo / Loại tin</th>'
            '<th scope="col">Tóm tắt</th></tr></thead>'
            '<tbody>' + ''.join(cells) + '</tbody></table></div>')
