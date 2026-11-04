import csv, json, os, sys, urllib.error, urllib.parse, urllib.request

SHEET_ID = '12UIdXUSc0S6LZibwD_N2zJvDxlehZ_tvVWmrJLjA7E8'
KEY = os.environ.get('GS_KEY', '').strip()
if not KEY:
    sys.exit('GS_KEY está vacío: revisá el secreto en Settings > Secrets and variables > Actions.')
os.makedirs('datos', exist_ok=True)
for sheet in ['CORDENADAS', 'REFERENCIA', 'V L']:
    qs = urllib.parse.urlencode({'key': KEY, 'valueRenderOption': 'FORMATTED_VALUE'})
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{urllib.parse.quote(sheet)}?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=300) as r:
            rows = json.load(r).get('values', [])
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try:
            msg = json.loads(body)['error']['message']
        except Exception:
            msg = body[:300]
        sys.exit(f'{sheet}: HTTP {e.code} de Google: {msg.replace(KEY, "***")}')
    with open(f'datos/{sheet}.csv', 'w', encoding='utf-8', newline='') as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows(rows)
    print(f'{sheet}: {len(rows)} filas')
