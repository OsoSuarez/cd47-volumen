import json,sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(viewport={'width':1400,'height':900});errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('file://'+sys.argv[1]);pg.wait_for_timeout(6000)
    pg.evaluate("document.querySelector('[data-t=t4]').click()");pg.wait_for_timeout(5000)
    rows=pg.evaluate("[...document.querySelectorAll('#simDet tr')].map(r=>[...r.children].map(c=>c.innerText.replace(/\\s+/g,' ').trim()))")
    out={'rows':rows,'kpis':pg.evaluate("document.querySelector('#simKpis')?.innerText"),'warn':pg.evaluate("document.querySelector('#simWarn')?.innerText"),'note':pg.evaluate("document.querySelector('#simDetNote')?.innerText"),'errs':errs}
    json.dump(out,open('diag_out.json','w'),ensure_ascii=False,indent=1);b.close()
