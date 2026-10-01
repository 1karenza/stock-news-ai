"""Ticker-bound public broker reports, retaining source provenance."""
import html
import json
import math
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from equity_data import EquityUnavailable, valid_ticker, text_only
from investor_events import safe_url


def parse_reports(data, ticker, latest_only=True):
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
    if not latest_only:
        return sorted(rows, key=lambda r: r['date'], reverse=True)
    return latest_reports(rows)


def latest_reports(rows, year=None):
    latest = {}
    for row in sorted(rows, key=lambda r: r['date'], reverse=True):
        if year is not None and row['date'].year != year:
            continue
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
        return parse_reports(data, ticker, latest_only=False)
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
                    f'<td class="broker-price" data-sort="{row["price"] if row["price"] is not None else ""}">{price}</td><td data-sort="{row["date"]:%Y-%m-%d}">{row["date"]:%d/%m/%Y}</td>'
                    f'<td>{esc(row["broker"])} — đăng trên Simplize</td>'
                    f'<td><span class="broker-rating {tone}">{esc(recommend)}</span>'
                    f'<div class="broker-summary">{esc(row["title"])}</div></td><td>{link}</td></tr>')
    headers = ['CTCK', 'Loại báo cáo', 'Giá mục tiêu (Target Price)', 'Ngày', 'Nguồn', 'Khuyến nghị & Giả định', 'Nguồn gốc']
    heading = ''.join(f'<th><button type="button" data-column="{i}" aria-label="Sắp xếp theo {h}" title="Bấm để đổi chiều sắp xếp">{h} <span>↕</span></button></th>' if i not in (4, 6) else f'<th>{h}</th>' for i, h in enumerate(headers))
    return '<div class="source-table-wrap"><table class="source-table broker-table"><thead><tr>' + heading + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'


def sortable_broker_document(rows):
    return '''<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>
    :root { color-scheme: light dark; }
    body { margin:0; font:14px Arial,sans-serif; color:light-dark(#292524,#e8e3e0); background:transparent; }
    .source-table-wrap { overflow-x:auto; border:1px solid light-dark(#ded8d4,#494341); border-radius:12px; }
    table { width:100%; min-width:1050px; border-collapse:collapse; }
    th,td { padding:14px 12px; text-align:left; border-bottom:1px solid light-dark(#e8e2de,#494341); vertical-align:top; }
    th { font-size:11px; text-transform:uppercase; background:light-dark(#f3eeea,#302b29); }
    th button { font:inherit; text-transform:inherit; text-align:left; cursor:pointer; border:0; padding:0; color:inherit; background:transparent; }
    th button:focus-visible { outline:2px solid #6384db; outline-offset:4px; }
    .broker-price { color:light-dark(#4361b5,#9db6ff); font-weight:700; white-space:nowrap; }
    .broker-kind,.broker-rating { display:inline-block; padding:3px 9px; border-radius:12px; font-size:12px; background:rgba(90,120,200,.12); }
    .broker-rating.buy { color:light-dark(#227451,#8de1ba); background:rgba(60,180,120,.15); }
    .broker-summary { max-width:320px; margin-top:8px; font-size:12px; line-height:1.5; opacity:.8; }
    a { color:light-dark(#4361b5,#9db6ff); text-decoration:none; }
    </style></head><body>''' + broker_table(rows) + '''<script>
    const table = document.querySelector('table'), body = table.tBodies[0];
    table.querySelectorAll('button[data-column]').forEach(button => {
      button.addEventListener('click', () => {
        const column = Number(button.dataset.column);
        const direction = button.dataset.direction === 'asc' ? 'desc' : 'asc';
        const factor = direction === 'asc' ? 1 : -1;
        const rows = Array.from(body.rows);
        rows.sort((a,b) => {
          const ac = a.cells[column], bc = b.cells[column];
          const av = ac.dataset.sort ?? ac.textContent.trim();
          const bv = bc.dataset.sort ?? bc.textContent.trim();
          // Unpublished prices stay last in both directions.
          if (column === 2) {
            if (av === '' || bv === '') return (av === '') - (bv === '');
            return (Number(av) - Number(bv)) * factor;
          }
          return av.localeCompare(bv, 'vi', {numeric:true}) * factor;
        });
        rows.forEach(row => body.appendChild(row));
        table.querySelectorAll('button[data-column]').forEach(other => {
          delete other.dataset.direction;
          other.querySelector('span').textContent = '↕';
          other.parentElement.removeAttribute('aria-sort');
        });
        button.dataset.direction = direction;
        button.querySelector('span').textContent = direction === 'asc' ? '↑' : '↓';
        button.parentElement.setAttribute('aria-sort', direction === 'asc' ? 'ascending' : 'descending');
      });
    });
    </script></body></html>'''
