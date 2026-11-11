import csv, json, re, sys, os, datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(HERE, 'datos')
FECHA = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()

def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    return [h.strip() for h in rows[0]], rows[1:]

def col(H, *names):
    low = [n.lower() for n in names]
    for i, h in enumerate(H):
        if h.lower() in low:
            return i
    return -1

def get(r, i):
    return r[i].strip() if 0 <= i < len(r) else ''

def pnum(s):
    s = str(s or '').strip()
    if not s:
        return None
    s = re.sub(r'[.,](?=\d{3}(\D|$))', '', s).replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None

def is_one(v):
    return re.sub(r'\.0+$', '', v.strip()) == '1'

def is_yes(v):
    return bool(re.match(r'^(true|1|verdadero|si|sí|x)$', v.strip(), re.I))

def excl(z):
    return bool(re.search(r'MRM|COMBI|BIN|CNC', z.upper()))

def difer(z, u):
    return 'DIFEREN' in (z + ' ' + u).upper()

def pool(tp):
    tp = tp.upper()
    return 'CON' if tp == 'CONMFC' else tp

# 1) Coordenadas: picking (Piso = 1), libres (E) por pool
H, rows = read_csv(os.path.join(DATOS, 'CORDENADAS.csv'))
iu, itp, ip = col(H, 'Ubicacion'), col(H, 'TipoProducto'), col(H, 'Piso')
isel, iz = col(H, 'Seleccion'), col(H, 'Zona piso')
if min(iu, itp, ip) < 0:
    sys.exit('Faltan columnas en CORDENADAS (Ubicacion, TipoProducto, Piso)')
picks, E = {}, defaultdict(int)
for r in rows:
    u = get(r, iu)
    if not u or not is_one(get(r, ip)):
        continue
    z = get(r, iz)
    if excl(z) or difer(z, u):
        continue
    tp = get(r, itp).upper()
    picks[u] = tp
    if not is_yes(get(r, isel)):
        E[pool(tp)] += 1

# 1b) Diagnostico de volumetria de ubicaciones (solo imprime, no cambia nada)
try:
    from collections import Counter
    icc, ipm, ioc, itip, icant = col(H, 'Capacidad Cubica'), col(H, 'Peso Max'), col(H, 'Ocupacion'), col(H, 'Tipo'), col(H, 'CANT SKUS')
    cc_all, cc_pick, cc_tp, tipos = Counter(), Counter(), defaultdict(Counter), Counter()
    for r in rows:
        v = get(r, icc)
        cc_all[v] += 1
        tipos[get(r, itip)] += 1
        if is_one(get(r, ip)) and get(r, iu) in picks:
            cc_pick[v] += 1
            cc_tp[get(r, itp).upper()][v] += 1
    print('DIAG Capacidad Cubica (todas):', cc_all.most_common(12))
    print('DIAG Capacidad Cubica (picking):', cc_pick.most_common(12))
    print('DIAG Tipo:', tipos.most_common(8))
    print('DIAG Peso Max:', Counter(get(r, ipm) for r in rows).most_common(8))
    for tp, c in sorted(cc_tp.items(), key=lambda x: -sum(x[1].values()))[:40]:
        print('DIAG CC por grupo', tp, sum(c.values()), c.most_common(4))
except Exception as e:
    print('DIAG error', e)

# 2) Inventario: stock picking por SKU y posiciones ocupadas (F) por pool
H, rows = read_csv(os.path.join(DATOS, 'REFERENCIA.csv'))
ie, isa, iu = col(H, 'EAN'), col(H, 'Saldo'), col(H, 'Ubicacion')
iz, ia = col(H, 'Zona', 'Zona piso'), col(H, 'Area')
if min(ie, isa, iu) < 0:
    sys.exit('Faltan columnas en REFERENCIA (EAN, Saldo, Ubicacion)')
STK, occ = defaultdict(float), defaultdict(float)
for r in rows:
    sku = int(re.sub(r'\D', '', get(r, ie)) or 0)
    if not sku:
        continue
    u, z = get(r, iu), get(r, iz)
    if excl(z) or difer(z, u):
        continue
    sal = pnum(get(r, isa))
    if sal is None or u not in picks:
        continue
    STK[sku] += sal
    occ[u] += sal
F = defaultdict(int)
for u, s in occ.items():
    if s > 0:
        F[pool(picks[u])] += 1

# 2b) Almacenamiento (Area = almacenamiento) y cruce sync_id -> SKU para la solapa de reabasto
ALM, SYNC = defaultdict(float), {}
isync, ia2 = col(H, 'sync_id'), ia
for r in rows:
    sku = int(re.sub(r'\D', '', get(r, ie)) or 0)
    if not sku:
        continue
    sal = pnum(get(r, isa))
    if sal is not None and get(r, ia2).strip().lower() == 'almacenamiento':
        ALM[sku] += sal
    sy = re.sub(r'\D', '', get(r, isync))
    if sy and int(sy) not in SYNC:
        SYNC[int(sy)] = sku
print('ALM SKUs: %d · cruce sync->SKU: %d' % (len(ALM), len(SYNC)))

# 3) Grupos de la plantilla y ocupación por grupo
tpl = open(os.path.join(HERE, 'tpl3.html'), encoding='utf-8').read()
m = re.search(r'^const GROUPS=(\{.*\});$', tpl, re.M)
if not m:
    sys.exit('No encontré const GROUPS en tpl3.html')
GROUPS = json.loads(m.group(1))
OCC, OCUP = {}, {}
for g in GROUPS:
    p = pool(g)
    e, f = E.get(p, 0), F.get(p, 0)
    OCC[g] = {'E': e, 'F': f}
    OCUP[g] = (f / e) if e > 0 else None

def as_json(v):
    return json.dumps(v, ensure_ascii=False, separators=(',', ':'))

def patch(txt, name, obj):
    new = 'let %s=%s;' % (name, as_json(obj))
    txt, n = re.subn(r'^let ' + name + r'=.*$', lambda _: new, txt, count=1, flags=re.M)
    if n != 1:
        sys.exit('No encontré let %s en tpl3.html' % name)
    return txt

stk_out = {str(k): (int(v) if float(v).is_integer() else v) for k, v in STK.items() if v > 0}
tpl = patch(tpl, 'STK', stk_out)
tpl = patch(tpl, 'OCC', OCC)
tpl = patch(tpl, 'OCUP', OCUP)
alm_out = {str(k): (int(v) if float(v).is_integer() else v) for k, v in ALM.items() if v > 0}
tpl = patch(tpl, 'ALM', alm_out)
tpl = patch(tpl, 'SYNC', {str(k): v for k, v in SYNC.items()})
tpl, n = re.subn(r'id="invFecha" value="\d{4}-\d{2}-\d{2}"', 'id="invFecha" value="%s"' % FECHA, tpl, count=1)
if n != 1:
    sys.exit('No encontré el campo de fecha')

def build_vl():
    H, rows = read_csv(os.path.join(DATOS, 'V L.csv'))
    isku, igrp, ivol = col(H, 'productoEAN'), col(H, 'Codigo Grupo'), col(H, 'volumen')
    imin, imax, iemp, inm = col(H, 'Stock Min'), col(H, 'Stock Max'), col(H, 'Cantidad Empaque'), col(H, 'descripcion')
    miss = [n for n, i in [('productoEAN', isku), ('Codigo Grupo', igrp), ('Stock Min', imin), ('Stock Max', imax)] if i < 0]
    if miss:
        sys.exit('Faltan columnas en V L: ' + ', '.join(miss))
    def num(r, i):
        v = pnum(get(r, i)) if i >= 0 else None
        if v is None:
            return None
        return int(v) if float(v).is_integer() else v
    out = {}
    for r in rows:
        sku = int(re.sub(r'\D', '', get(r, isku)) or 0)
        if not sku or sku in out:
            continue
        out[sku] = [get(r, igrp) or 'SIN GRUPO', num(r, ivol), num(r, imin), num(r, imax), num(r, iemp), get(r, inm)]
    if not out:
        sys.exit('La pestaña V L no tiene SKUs')
    return out

base = open(os.path.join(HERE, 'base.json'), encoding='utf-8').read()
if os.path.exists(os.path.join(DATOS, 'V L.csv')):
    vl = as_json(build_vl())
    print('V L: %d SKUs' % len(json.loads(vl)))
else:
    vl = open(os.path.join(HERE, 'vl.json'), encoding='utf-8').read()
from datetime import datetime
from zoneinfo import ZoneInfo
RUN_AT = datetime.now(ZoneInfo('America/Argentina/Buenos_Aires')).strftime('%d/%m/%Y %H:%M')
tpl = tpl.replace('__RUN_AT__', RUN_AT)
out = tpl.replace('__BASE__', base).replace('__VL__', vl)
with open(os.path.join(HERE, 'volumen_futuro.html'), 'w', encoding='utf-8') as f:
    f.write(out)

con_stock = len(stk_out)
print('Fecha: %s' % FECHA)
print('SKUs con stock picking > 0: %d' % con_stock)
print('Posiciones picking libres (E): %d · ocupadas (F): %d' % (sum(E.values()), sum(F.values())))
print('Archivo generado: volumen_futuro.html')
