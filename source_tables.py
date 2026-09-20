"""Readable public-source links, including multiple providers in one cell."""
import html
from urllib.parse import urlparse
from investor_events import safe_url


def source_link(url):
    url = safe_url(url)
    if not url:
        return ''
    host = (urlparse(url).hostname or '').removeprefix('www.')
    labels = {'cafef.vn':'CafeF', 'simplize.vn':'Simplize', 'vietnambiz.vn':'Vietnambiz',
              'vietstock.vn':'Vietstock', 'finance.vietstock.vn':'Vietstock',
              'finance.yahoo.com':'Yahoo Finance'}
    label = labels.get(host, host)
    return f'<a class="source-link" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(label)} ↗</a>'


def source_table(rows):
    hidden = {'Nguồn','Nguồn bổ sung','Chỉ số bổ sung','Kỳ số liệu bổ sung'}
    columns = [key for key in rows[0] if key not in hidden]
    labels = {'EPS (TTM, đ/CP)':'EPS (đ/CP)'}
    header = ''.join(f'<th>{html.escape(labels.get(k,k))}</th>' for k in columns) + '<th>Mở nguồn</th>'
    body = []
    for row in rows:
        cells=[]
        for key in columns:
            value=row.get(key)
            if value is None: value='—'
            elif isinstance(value, float): value=f'{value:,.2f}'
            cells.append(f'<td>{html.escape(str(value))}</td>')
        urls = dict.fromkeys(safe_url(row.get(k,'')) for k in ('Nguồn','Nguồn bổ sung'))
        links = '<br>'.join(source_link(u) for u in urls if u)
        body.append('<tr>'+''.join(cells)+f'<td class="source-cell">{links or "—"}</td></tr>')
    return '<div class="source-table-wrap"><table class="source-table"><thead><tr>'+header+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div>'
