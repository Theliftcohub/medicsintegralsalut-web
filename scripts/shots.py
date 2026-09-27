import asyncio, sys, json
from playwright.async_api import async_playwright
B="https://www.medicsintegralsalut.com"
PAGES={"home":"/","unidades":"/unidades/","unidad-categoria":"/unidades/cirugia-estetica-facial/","unidad-detalle":"/unidades/cirugia-estetica-facial/rinoplastia-girona/","post":"/descubre-la-diferencia-entre-lipo-vaser-y-liposuccion/","blog":"/blog/","equipo":"/cirugia-plastica-girona-equipo-medico/","medico":"/team/dr-mike-dewever/","contacto":"/contacto/","financiacion":"/financiacion/","legal":"/aviso-legal/","home-ca":"/ca/","categoria":"/category/cirugia-estetica/"}
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium' if False else None, args=["--ignore-certificate-errors"])
        tokens={}
        for vp,(w,h) in {"desktop":(1440,900),"mobile":(390,844)}.items():
            ctx=await b.new_context(viewport={"width":w,"height":h}, ignore_https_errors=True)
            pg=await ctx.new_page()
            for name,path in PAGES.items():
                for att in range(3):
                    try:
                        r=await pg.goto(B+path, wait_until="networkidle", timeout=60000)
                        await pg.wait_for_timeout(1500)
                        await pg.screenshot(path=f"migracion/screenshots/{name}-{vp}.png", full_page=True)
                        print(vp,name,r.status if r else None); break
                    except Exception as e:
                        print("retry",name,e.__class__.__name__); await asyncio.sleep(5)
                if vp=="desktop" and name=="home":
                    tokens=await pg.evaluate("""()=>{const g=(s,p)=>{const e=document.querySelector(s);return e?getComputedStyle(e)[p]:null};
                    const cols={};document.querySelectorAll('a,button,h1,h2,h3,.elementor-button,header,footer,body').forEach(e=>{const c=getComputedStyle(e);[c.color,c.backgroundColor].forEach(v=>{if(v&&v!=='rgba(0, 0, 0, 0)')cols[v]=(cols[v]||0)+1})});
                    const fonts={};document.querySelectorAll('h1,h2,h3,p,a,button').forEach(e=>{const f=getComputedStyle(e).fontFamily;fonts[f]=(fonts[f]||0)+1});
                    const root=getComputedStyle(document.documentElement);const vars={};for(const s of document.styleSheets){try{for(const r of s.cssRules){if(r.selectorText===':root'||r.selectorText&&r.selectorText.includes('elementor-kit')){for(const k of r.style){if(k.startsWith('--e-global'))vars[k]=r.style.getPropertyValue(k).trim()}}}}catch(e){}}
                    return {body_font:g('body','fontFamily'),h1_font:g('h1','fontFamily'),h1_size:g('h1','fontSize'),colores:Object.entries(cols).sort((a,b)=>b[1]-a[1]).slice(0,15),fuentes:fonts,elementor_vars:vars}}""")
            await ctx.close()
        json.dump(tokens,open("migracion/brand_tokens.json","w"),indent=1,ensure_ascii=False)
        await b.close()
asyncio.run(main())
