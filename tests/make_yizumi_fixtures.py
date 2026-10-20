"""Replicas of Allen's Yizumi-HPM UN540 A5-N (Machine 3) controller screens, rendered at the HMI's 1024x768 and turned into
phone-style photos (bezel, keypad below, perspective tilt, blur, uneven light, JPEG). Allen's real photos are not readable
from the box shell, so the reader is measured on these; values = Allen's photos of 10/20/26."""
import json, os, random, io
from playwright.sync_api import sync_playwright
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance
FIX = "/workspace/tooling-job-log-v2/tests/fixtures/"
CSS = """body{margin:0;width:1024px;height:768px;background:#5a5f66;font-family:Tahoma,'DejaVu Sans',Arial,sans-serif;font-size:13px;color:#1a1a1a;overflow:hidden;position:relative}
.top{position:absolute;left:4px;top:4px;width:1016px;height:52px;background:#eef0f2;border:1px solid #9aa}
.top .b{position:absolute;background:#fff;border:1px solid #889;text-align:right;padding:0 4px;height:18px;line-height:18px}
.main{position:absolute;left:4px;top:62px;width:930px;height:600px;background:#e6e9ec}
.side{position:absolute;left:938px;top:62px;width:82px;height:600px;background:#e1e4e8;border-left:1px solid #aab}
.pan{position:absolute;left:0;width:930px;border:1px solid #9aa;background:#e9ecef}
.pt{height:22px;line-height:22px;padding-left:6px;font-weight:bold;background:linear-gradient(#f4f5f6,#dfe2e5);border-bottom:1px solid #aab}
.l{position:absolute;white-space:nowrap}
.v{position:absolute;background:#fff;border:1px solid #7d8a96;box-shadow:inset 1px 1px 0 #ccd;text-align:right;padding:0 5px;height:21px;line-height:21px;box-sizing:border-box}
.g{color:#aaa}
.tabs{position:absolute;left:4px;top:668px;width:1016px;height:96px;background:#d8dbdf;display:flex}
.tab{flex:1;text-align:center;padding-top:52px;font-size:12px;border-right:1px solid #aab}
.tab.on{background:#7cc242;color:#fff}
.vd{position:absolute;top:22px;bottom:0;left:470px;border-left:1px solid #aab}
"""
TABS = ["Overvi...","Mold","Ejector","Core 1/2","Injection","Plastic...","Nozzle","Heating","Produ...","Alarm","Return"]
def frame(on, body, date="10/20/26 2:27 PM"):
    tb = "".join(f'<div class="tab{" on" if t==on else ""}">{t}</div>' for t in TABS)
    top = (f'<div class="b" style="left:40px;top:4px;width:60px">0.10</div><div class="l" style="left:106px;top:4px">in</div>'
           f'<div class="b" style="left:40px;top:28px;width:60px">0.00</div><div class="l" style="left:106px;top:28px">in</div>'
           f'<div class="b" style="left:170px;top:4px;width:60px">9.73</div><div class="l" style="left:236px;top:4px">in</div>'
           f'<div class="b" style="left:170px;top:28px;width:60px">0</div><div class="l" style="left:236px;top:28px">rpm</div>'
           f'<div class="b" style="left:290px;top:4px;width:54px">0.0</div><div class="l" style="left:348px;top:4px">psi</div>'
           f'<div class="l" style="left:540px;top:28px;color:#d33">Cooling</div>'
           f'<div class="l" style="left:720px;top:6px;font-size:14px">{date}</div><div class="l" style="left:705px;top:30px;font-size:14px">Administrator</div>'
           f'<div class="l" style="left:900px;top:16px;font-style:italic;font-weight:bold;color:#777">YIZUMI | HPM</div>')
    return f"<html><head><style>{CSS}</style></head><body><div class='top'>{top}</div><div class='main'>{body}</div><div class='side'></div><div class='tabs'>{tb}</div></body></html>"
def L(x,y,t,**k): return f'<div class="l" style="left:{x}px;top:{y}px">{t}</div>'
def V(x,y,t,w=56,g=False): return f'<div class="v{" g" if g else ""}" style="left:{x}px;top:{y}px;width:{w}px">{t}</div>'
def panel(top,h,title,inner,stages=None):
    st = (L(760,3,"Stages")+V(830,1,stages,50)) if stages else ""
    return f'<div class="pan" style="top:{top}px;height:{h}px"><div class="pt">{title}</div>{st}<div class="vd"></div>{inner}</div>'
def grid(x0,y0,heads,units,rows,cw=66,rh=26):
    s = "".join(L(x0+i*cw+6,y0,h) + L(x0+i*cw+18,y0+17,u) for i,(h,u) in enumerate(zip(heads,units)))
    for j,(lab,vals) in enumerate(rows):
        y=y0+44+j*rh; s+=L(x0-90 if len(lab)>1 else x0-40,y+3,lab)
        s+="".join(V(x0+i*cw,y,v,58) for i,v in enumerate(vals) if v is not None)
    return s
def kv(x,y,lab,vals,unit="",lw=170,w=56):
    s=L(x,y+3,lab); xx=x+lw
    for v in vals: s+=V(xx,y,v,w); xx+=w+6
    return s+(L(xx,y+3,unit) if unit else "")
SCREENS = {}
SCREENS["mold"] = ("Mold", panel(0,300,"Mold close", grid(130,20,["Pressure","Velocity","To"],["psi","%","in"],
    [("1",["580","50","12.00"]),("2",["580","55","3.15"]),("3",["580","55","0.59"]),("Protect",["500","40","0.31"]),("High pr...",["2520","50",None])])
    + kv(500,190,"Mold protect time",["0.11","3.00"],"s",150) + kv(500,216,"Protect from-to",["0.59","0.31"],"in",150) + kv(500,242,"Clamp force",["559.6","520.0"],"US ton",150),"5")
  + panel(305,290,"Mold open", grid(150,20,["Pressure","Velocity","To"],["psi","%","in"],[("1",["800","50","12.00"]),("2",["700","50","19.00"]),("End",["600","50","20.00"])]),"3"))
SCREENS["injection"] = ("Injection", panel(0,595,"Inject", grid(150,20,["Pressure","Velocity","To"],["psi","%","in"],[("1",["1700","21","2.50"]),("2",["1700","20","1.00"]),("End",["1700","19",None])])
    + kv(500,140,"Inject pressure",["0"],"psi",200) + kv(500,166,"Plasticize stroke",["9.70"],"in",200) + kv(500,260,"Allowable inject pressure",["2538"],"psi",200)
    + L(505,300,"Cut off") + kv(530,325,"Screw position",["1.10","1.10"],"in",130) + kv(530,351,"Inject time",["11.50","1.00"],"s",130) + kv(530,377,"Inject pressure",["1679","0"],"psi",130)
    + kv(505,403,"Cut off activation position",["2.00"],"in",217),"3"))
SCREENS["plasticize"] = ("Plastic...", panel(0,310,"Plasticize and backpressure", grid(150,20,["Backpr...","Charge","To"],["psi","rpm","in"],[("End",["75","50","9.40"])])
    + kv(520,170,"Screw position",["9.73"],"in",180) + kv(520,196,"Screw revolution",["0"],"rpm",180) + kv(520,222,"Pressure",["2150"],"psi",180) + kv(520,248,"Delay Plast",["0.80","0.80"],"s",118),"1")
  + panel(315,280,"Decompression", L(330,10,"Mode")+L(400,10,"Pressure")+L(470,10,"Velocity")+L(540,10,"Position")+L(620,10,"Time")
    + L(415,32,"psi")+L(490,32,"%")+L(555,32,"in")+L(625,32,"s")
    + L(10,60,"Decompression before plasticize")+V(310,57,"No",80)+V(400,57,"500",58)+V(468,57,"50",58)+V(536,57,"3.00",64)+V(610,57,"3.00",58)
    + L(10,86,"Decompression after plasticize")+V(310,83,"Position",80)+V(400,83,"500",58)+V(468,83,"50",58)+V(536,83,"0.30",64)+V(610,83,"3.00",58)))
SCREENS["heating"] = ("Heating", panel(0,250,"Heating zones",
    "".join(V(250+i*62,60,t,60) for i,t in enumerate(["398.5","400.1","401.5","412.0","402.1","402.1","404.8"])) + L(690,63,"°F")
    + L(185,107,"Set") + "".join(V(250+i*62,104,"400.0",60) for i in range(7)) + L(690,107,"°F")
    + L(140,133,"Tol. high") + "".join(V(250+i*62,130,"50.0",60) for i in range(7)) + L(690,133,"°F")
    + L(145,159,"Tol. low") + "".join(V(250+i*62,156,"50.0",60) for i in range(7)) + L(690,159,"°F"))
  + panel(255,340,"Auto heating", L(240,30,"Start") + "".join(L(40,52+i*23,d)+V(170,49+i*23,"12:00:00 AM",88,True) for i,d in enumerate(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]))
    + kv(330,50,"Standby temperature",["275"],"°F",260,48) + L(330,78,"Keep warm") + L(330,104,"Optimize nozzle heating") + L(330,130,"Undo change pid param") + L(330,156,"Group heating")
    + kv(330,180,"Oil",["90"],"°F",260,48)))
SCREENS["ejector"] = ("Ejector", panel(0,300,"Ejector forward", grid(150,20,["Force","Velocity","To"],["psi","%","in"],[("End",["500","20","4.20"])])
    + L(500,200,"Ejector mode") + V(650,197,"Continuous",100) + kv(500,226,"Shake counter",["1"],"",150,100),"1")
  + panel(305,290,"Ejector backward", grid(150,20,["Force","Velocity","To"],["psi","%","in"],[("End",["350","60","0.25"])]),"1"))
SCREENS["nozzle"] = ("Nozzle", panel(0,300,"Nozzle forward", L(260,30,"Force")+L(320,30,"Velocity")+L(410,30,"Time")+L(265,54,"psi")+L(335,54,"%")+L(420,54,"s")
    + kv(70,80,"Before limit switch",["750","25"],"",180) + kv(70,106,"After limit switch",["500","10","0.00","0.00"],"",180)
    + kv(30,160,"Contact force",["250","25"],"",220) + kv(30,186,"Force build up time",["0.00","0.10"],"s",220))
  + panel(305,290,"Nozzle backward", L(90,10,"Nozzle back mode")+V(260,7,"No",90) + L(270,40,"Force")+L(330,40,"Velocity")+L(410,40,"Time")+L(275,64,"psi")+L(345,64,"%")+L(420,64,"s")
    + kv(120,90,"Backward",["363","20","7.57","2.00"],"",142)))
TRUTH = {
 "mold": {"cl1P":"580","cl1V":"50","cl1X":"12.00","cl2P":"580","cl2V":"55","cl2X":"3.15","cl3P":"580","cl3V":"55","cl3X":"0.59","prP":"500","prV":"40","prX":"0.31","hpP":"2520","hpV":"50",
   "protT1":"0.11","protT2":"3.00","protF":"0.59","protTo":"0.31","force1":"559.6","force2":"520.0","op1P":"800","op1V":"50","op1X":"12.00","op2P":"700","op2V":"50","op2X":"19.00","opEP":"600","opEV":"50","opEX":"20.00"},
 "injection": {"in1P":"1700","in1V":"21","in1X":"2.50","in2P":"1700","in2V":"20","in2X":"1.00","inEP":"1700","inEV":"19","stroke":"9.70","allow":"2538","coPos":"1.10","coTime":"11.50","coPress":"1679","coAct":"2.00"},
 "plasticize": {"bp":"75","rpm":"50","to":"9.40","dly1":"0.80","dly2":"0.80","decP":"500","decV":"50","decX":"0.30"},
 "heating": {"z1":"400.0","z2":"400.0","z3":"400.0","z4":"400.0","z5":"400.0","z6":"400.0","z7":"400.0","tolH":"50.0","tolL":"50.0","standby":"275","oil":"90"},
 "ejector": {"fP":"500","fV":"20","fX":"4.20","shake":"1","bP":"350","bV":"60","bX":"0.25"},
 "nozzle": {"bfP":"750","bfV":"25","afP":"500","afV":"10","afT1":"0.00","afT2":"0.00","cfP":"250","cfV":"25","bu1":"0.00","bu2":"0.10","bkP":"363","bkV":"20","bkT1":"7.57","bkT2":"2.00"}}
def photo(png, seed, hard=False):
    R = random.Random(seed); scr = Image.open(io.BytesIO(png)).convert("RGB")
    W, H = 1700, 2266; ph = Image.new("RGB", (W, H), (70, 72, 76)); d = ImageDraw.Draw(ph)
    d.rectangle([0, 0, W, 220], fill=(188, 184, 176)); d.rectangle([60, 260, W-40, 1600], fill=(28, 30, 33))
    for r in range(4):
        for c in range(4): d.rectangle([90+c*150, 1780+r*110, 200+c*150, 1840+r*110], fill=(120, 122, 126))
        for c in range(3): d.rectangle([1250+c*130, 1780+r*110, 1340+c*130, 1840+r*110], fill=(120, 122, 126))
    big = scr.resize((1460, 1095), Image.LANCZOS)
    # perspective: paste with a slight keystone via QUAD (top a bit wider than bottom, small rotation)
    dx, dy = (R.uniform(40, 70), R.uniform(-35, 35)) if hard else (R.uniform(10, 30), R.uniform(-15, 15)); src = Image.new("RGB", (W, H), (28, 30, 33)); src.paste(big, (120, 420))
    quad = (0+dx, 0+dy, 0-dx*0.3, H, W+dx*0.3, H, W-dx, 0-dy)
    ph2 = src.transform((W, H), Image.QUAD, quad, Image.BICUBIC)
    mask = Image.new("L", (W, H), 0); ImageDraw.Draw(mask).rectangle([110, 410, 1590, 1525], fill=255)
    mask = mask.transform((W, H), Image.QUAD, quad, Image.BICUBIC)
    ph.paste(ph2, (0, 0), mask)
    ph = ph.filter(ImageFilter.GaussianBlur(R.uniform(1.0, 1.25) if hard else R.uniform(0.55, 0.8)))
    grad = Image.linear_gradient("L").resize((W, H)).rotate(R.choice([0, 90, 180]))
    ph = Image.composite(ImageEnhance.Brightness(ph).enhance(0.86), ph, grad)
    ph = ImageEnhance.Color(ph).enhance(0.9)
    buf = io.BytesIO(); ph.save(buf, "JPEG", quality=82); return buf.getvalue()
if __name__ == "__main__":
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"]); pg = b.new_page(viewport={"width":1024,"height":768})
        for i, (k, (tab, body)) in enumerate(SCREENS.items()):
            pg.set_content(frame(tab, body)); png = pg.screenshot()
            open(FIX + f"yizumi-{k}.png", "wb").write(png)
            open(FIX + f"yizumi-{k}.jpg", "wb").write(photo(png, i + 7))
            open(FIX + f"yizumi-{k}-hard.jpg", "wb").write(photo(png, i + 70, True))
        b.close()
    json.dump(TRUTH, open(FIX + "yizumi.truth.json", "w"), indent=1); print("ok")
