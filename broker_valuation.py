"""Ticker-bound public broker reports, retaining source provenance."""
import html
import json
import math
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from equity_data import EquityUnavailable, valid_ticker, text_only
from investor_events import safe_url


def parse_reports(data, ticker):
    ticker = valid_ticker(ticker)
    if data.get('ticker') != ticker:
        raise EquityUnavailable('Mã báo cáo không khớp mã đang tra.')
    rows = []
    for report in data.get('analysisReports') or []:
        if report.get('ticker') != ticker or not report.get('source'):
            continue
        try:
            published = datetime.strptime(report.get('issueDate', ''), '%d/%m/%Y')
        except (ValueError, TypeError):
            continue
        price = report.get('targetPrice')
        if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price <= 0:
            price = None
        rows.append({'broker': text_only(report['source']), 'date': published,
                     'price': price, 'recommend': text_only(report.get('recommend') or ''),
                     'title': text_only(report.get('title') or ''),
                     'url': safe_url(report.get('attachedLink') or '')})
    latest = {}
    for row in sorted(rows, key=lambda r: r['date'], reverse=True):
        latest.setdefault(row['broker'].casefold(), row)
    return list(latest.values())


def fetch_broker_reports(ticker):
    ticker = valid_ticker(ticker)
    try:
        response = requests.get(f'https://simplize.vn/co-phieu/{ticker}/bao-cao',
                                headers={'User-Agent': 'Mozilla/5.0'}, timeout=(5, 20))
        response.raise_for_status()
        node = BeautifulSoup(response.text, 'html.parser').find('script', id='__NEXT_DATA__')
        data = json.loads(node.string)['props']['pageProps']
        return parse_reports(data, ticker)
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise EquityUnavailable(f'Chưa tải được báo cáo định giá {ticker} từ Simplize.') from exc


def broker_table(rows):
    esc = lambda value: html.escape(str(value), quote=True)
    body = []
    for row in rows:
        price = f"{row['price']:,.0f}".replace(',', '.') + ' VND' if row['price'] is not None else 'N/A'
        recommend = row['recommend'] or 'Chưa công bố'
        tone = 'buy' if recommend.upper() == 'MUA' else 'other'
        url = safe_url(row['url'])
        link = f'<a class="source-link" href="{esc(url)}" target="_blank" rel="noopener noreferrer" title="{esc(row["title"])}">Mở báo cáo ↗</a>' if url else '—'
        kind = 'Valuation Report' if row['price'] is not None else 'Recommendation'
        body.append(f'<tr><td><strong>{esc(row["broker"])}</strong></td>'
                    f'<td><span class="broker-kind">{kind}</span></td>'
                    f'<td class="broker-price">{price}</td><td>{row["date"]:%d/%m/%Y}</td>'
                    f'<td>{esc(row["broker"])} — đăng trên Simplize</td>'
                    f'<td><span class="broker-rating {tone}">{esc(recommend)}</span>'
                    f'<div class="broker-summary">{esc(row["title"])}</div></td><td>{link}</td></tr>')
    headers = ['CTCK', 'Loại báo cáo', 'Giá mục tiêu (Target Price)', 'Ngày', 'Nguồn', 'Khuyến nghị & Giả định', 'Nguồn gốc']
    return '<div class="source-table-wrap"><table class="source-table broker-table"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
