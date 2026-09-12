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
    for selector in ("[itemprop='articleBody']", ".article-body", ".article-content",
                     ".detail-content", ".content-detail", ".fck_detail", ".entry-content",
                     ".post-content", ".detail__content", "article"):
        for node in soup.select(selector):
            paras = [p.get_text(" ", strip=True) for p in node.select("p")]
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
    source = item.get("article_text") or item.get("summary") or title
    source = BeautifulSoup(source, "html.parser").get_text(" ", strip=True)
    source = re.sub(r"\s+", " ", source).strip()
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ỹ0-9\"“])", source)
    unique, seen = [], set()
    for sentence in sentences:
        sentence = sentence.strip()
        key = re.sub(r"\W+", "", sentence.lower())
        if len(sentence) < 30 or key in seen:
            continue
        seen.add(key)
        unique.append(sentence)
    if not unique:
        return [title] if title else []

    # Keep the lead for context, then favour facts, dates and explanations.
    terms = ("doanh thu", "lợi nhuận", "cổ tức", "phát hành", "kỳ hạn", "lãi suất",
             "mục đích", "dự kiến", "so với", "do", "nhằm", "rủi ro", "ngày")
    ranked = sorted(range(1, len(unique)), key=lambda i: (
        -(2 * bool(re.search(r"\d", unique[i])) + sum(t in unique[i].lower() for t in terms)), i))
    limit, budget = (6, 220) if detail else (4, 140)
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
    for row in rows:
        url = row["Đọc tin gốc"]
        link = (f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">Mở bài ↗</a>'
                if urlparse(url).scheme in ("http", "https") else "—")
        esc = lambda key: html.escape(str(row[key]))
        source_note = ('<div class="small-muted">Chưa tải được bài gốc</div>'
                       if row.get("Tình trạng nguồn") == "Chưa tải được bài gốc" else '')
        bond = row.get("Định giá trái phiếu", "-")
        bond_note = (f'<div class="table-bond"><strong>Trái phiếu</strong> · {html.escape(str(bond))}</div>'
                     if bond and bond != "-" else '')
        cells.append(f'<tr><td data-label="Ngày / Mã"><strong>{esc("Mã CK")}</strong><br>{esc("Ngày")}</td>'
                     f'<td data-label="Tóm tắt thông tin" class="news-summary">{esc("Tóm tắt thông tin")}{bond_note}</td>'
                     f'<td data-label="Nguồn / Loại tin">{esc("Source")}<br><span class="small-muted">{esc("Loại tin")}</span><br>{link}{source_note}</td></tr>')
    return ('<div class="news-table-wrap"><table class="news-table"><caption>Bảng tổng hợp tin chứng khoán</caption>'
            '<colgroup><col style="width:12%"><col style="width:68%"><col style="width:20%"></colgroup>'
            '<thead><tr><th scope="col">Ngày / Mã</th><th scope="col">Tóm tắt thông tin</th>'
            '<th scope="col">Nguồn / Loại tin</th></tr></thead>'
            '<tbody>' + ''.join(cells) + '</tbody></table></div>')
