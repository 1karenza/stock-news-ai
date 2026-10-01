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
                    f'<td data-filter="{esc(recommend)}"><span class="broker-rating {tone}">{esc(recommend)}</span>'
                    f'<div class="broker-summary">{esc(row["title"])}</div></td><td>{link}</td></tr>')
    headers = ['CTCK', 'Loại báo cáo', 'Giá mục tiêu (Target Price)', 'Ngày', 'Nguồn', 'Khuyến nghị & Giả định', 'Nguồn gốc']
    heading = ''.join(f'<th><button type="button" data-column="{i}" aria-label="Lọc {h}" aria-expanded="false" title="Lọc giá trị trong cột">{h} <span>▾</span></button></th>' if i not in (4, 6) else f'<th>{h}</th>' for i, h in enumerate(headers))
    return '<div class="source-table-wrap"><table class="source-table broker-table"><thead><tr>' + heading + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'


def filterable_broker_document(rows):
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
    .filter-menu { position:fixed; z-index:10; width:270px; padding:12px; box-sizing:border-box; border:1px solid light-dark(#d8d0ca,#655d58); border-radius:10px; background:light-dark(#fffaf6,#302b29); box-shadow:0 6px 20px #0003; }
    .filter-menu input[type=search] { width:100%; box-sizing:border-box; padding:8px; margin:8px 0; }
    .filter-options { max-height:180px; overflow:auto; }
    .filter-menu label { display:flex; gap:8px; align-items:center; padding:6px 0; overflow-wrap:anywhere; }
    [hidden] { display:none !important; }
    .filter-actions { display:flex; gap:8px; margin-top:10px; }
    .filter-actions button { cursor:pointer; padding:7px 12px; }
    button.active { color:light-dark(#4361b5,#9db6ff); }
    .filter-status { padding:10px 0; font-size:12px; }
    body { min-height:390px; }
    </style></head><body>''' + broker_table(rows) + '''<script>
    const table = document.querySelector('table'), body = table.tBodies[0];
    const rows = Array.from(body.rows), filters = new Map();
    const status = document.createElement('div');
    status.className = 'filter-status'; table.parentElement.after(status);
    const value = (row, column) => row.cells[column].dataset.filter ?? row.cells[column].textContent.trim();
    let menu = null, trigger = null;
    function closeMenu() {
      if (menu) menu.remove();
      if (trigger) trigger.setAttribute('aria-expanded','false');
      menu = null; trigger = null;
    }
    function applyFilters() {
      let count = 0;
      rows.forEach(row => {
        row.hidden = !Array.from(filters).every(([column, selected]) => selected.has(value(row,column)));
        if (!row.hidden) count++;
      });
      table.querySelectorAll('button[data-column]').forEach(button => {
        const active = filters.has(Number(button.dataset.column));
        button.classList.toggle('active',active);
        button.querySelector('span').textContent = active ? '⏷ ●' : '▾';
      });
      status.textContent = `Hiển thị ${count}/${rows.length} báo cáo`;
      if (count === 0) status.textContent += ' — Không có báo cáo khớp các bộ lọc.';
    }
    table.querySelectorAll('button[data-column]').forEach(button => {
      button.addEventListener('click', () => {
        const wasOpen = trigger === button;
        closeMenu(); if (wasOpen) return;
        const column = Number(button.dataset.column);
        const values = [...new Set(rows.map(row => value(row,column)))];
        const selected = new Set(filters.get(column) ?? values);
        menu = document.createElement('div'); menu.className = 'filter-menu';
        menu.setAttribute('role','dialog'); menu.setAttribute('aria-label',button.getAttribute('aria-label'));
        menu.innerHTML = '<strong>Lọc giá trị</strong><input type="search" placeholder="Tìm trong cột…" aria-label="Tìm giá trị"><label><input type="checkbox" class="select-all">Chọn tất cả kết quả</label><div class="filter-options"></div><div class="filter-actions"><button class="apply">Áp dụng</button><button class="clear">Xóa lọc cột</button></div>';
        trigger = button; button.setAttribute('aria-expanded','true');
        const list = menu.querySelector('.filter-options'), search = menu.querySelector('input[type=search]');
        const all = menu.querySelector('.select-all');
        values.forEach(text => {
          const label = document.createElement('label'), input = document.createElement('input');
          input.type = 'checkbox'; input.checked = selected.has(text); input.dataset.value = text;
          label.append(input, document.createTextNode(text || '(Trống)')); list.append(label);
          input.addEventListener('change', () => {
            if (input.checked) selected.add(text); else selected.delete(text);
            updateAll();
          });
        });
        function matching() { return Array.from(list.querySelectorAll('input')).filter(input => !input.parentElement.hidden); }
        function updateAll() {
          const items = matching(), checked = items.filter(input => input.checked).length;
          all.checked = items.length > 0 && checked === items.length;
          all.indeterminate = checked > 0 && checked < items.length;
        }
        search.addEventListener('input', () => {
          list.querySelectorAll('label').forEach(label => { label.hidden = !label.textContent.toLocaleLowerCase('vi').includes(search.value.toLocaleLowerCase('vi')); });
          updateAll();
        });
        all.addEventListener('change', () => {
          matching().forEach(input => {
            input.checked = all.checked;
            if (all.checked) selected.add(input.dataset.value); else selected.delete(input.dataset.value);
          }); updateAll();
        });
        menu.querySelector('.apply').addEventListener('click', () => {
          if (selected.size === values.length) filters.delete(column); else filters.set(column,selected);
          applyFilters(); closeMenu(); button.focus();
        });
        menu.querySelector('.clear').addEventListener('click', () => {
          filters.delete(column); applyFilters(); closeMenu(); button.focus();
        });
        document.body.append(menu);
        const rect = button.getBoundingClientRect();
        menu.style.left = Math.max(0,Math.min(rect.left,window.innerWidth-270)) + 'px';
        menu.style.top = Math.max(0,Math.min(rect.bottom+6,window.innerHeight-menu.offsetHeight)) + 'px';
        updateAll(); search.focus();
      });
    });
    document.addEventListener('click',event => { if (menu && !menu.contains(event.target) && !trigger.contains(event.target)) closeMenu(); });
    document.addEventListener('keydown',event => { if (event.key === 'Escape') { const button=trigger; closeMenu(); if(button) button.focus(); } });
    applyFilters();
    </script></body></html>'''
