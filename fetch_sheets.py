import csv, json, os, urllib.parse, urllib.request

SHEET_ID = '12UIdXUSc0S6LZibwD_N2zJvDxlehZ_tvVWmrJLjA7E8'
KEY = os.environ['GS_KEY']
os.makedirs('datos', exist_ok=True)
for sheet in ['CORDENADAS', 'REFERENCIA']:
    qs = urllib.parse.urlencode({'key': KEY, 'valueRenderOption': 'FORMATTED_VALUE'})
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{urllib.parse.quote(sheet)}?{qs}"
    with urllib.request.urlopen(url, timeout=300) as r:
        rows = json.load(r).get('values', [])
    with open(f'datos/{sheet}.csv', 'w', encoding='utf-8', newline='') as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows(rows)
    print(f'{sheet}: {len(rows)} filas')
