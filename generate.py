import os, json, requests, re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
yesterday = (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")
update_str = now_kst.strftime("%Y.%m.%d %H:%M")

print(f"수집 시작: {update_str} KST / 대상: {yesterday}")

# ── 카테고리 키워드 ────────────────────────────────────────
CAT_KW = {
    "dermatology": ["탈모","두피","모발","헤어","피부과","alopecia","hair loss","hair growth","minoxidil","finasteride","DHT","헤어그로"],
    "chronic":     ["당뇨","고혈압","고지혈증","비만","혈당","인슐린","GLP-1","SGLT","diabetes","hypertension","cholesterol","obesity","cardiovascular"],
    "probiotics":  ["프로바이오틱스","유산균","낙산균","효모균","당화균","장내미생물","마이크로바이옴","microbiome","probiotic","butyrate"],
    "rifaximin":   ["rifaximin","리팍시민","SIBO","IBS","과민성장","간성뇌증"],
    "pediatrics":  ["소아과","소아청소년","소아","어린이","아동","신생아","pediatric","children","infant"],
    "pharma":      ["제약","바이오","기술이전","라이선스","파이프라인","실적","매출","pharmaceutical","biotech","licensing"],
    "approval":    ["허가","승인","식약처","MFDS","FDA","EMA","품목허가","approved","authorization"],
    "clinical":    ["임상","3상","2상","1상","임상시험","phase 3","phase 2","clinical trial"],
    "policy":      ["급여","건보","복지부","의료정책","수가","규제","reimbursement","healthcare policy"],
}

def categorize(title, desc=""):
    txt = (title + " " + desc).lower()
    scores = {c: sum(1 for k in kws if k.lower() in txt) for c, kws in CAT_KW.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

def is_important(title):
    hi = ["승인","허가","fda","3상","신약","approved","급여","출시","breakthrough","phase 3"]
    return "high" if any(w in title.lower() for w in hi) else "medium"

def clean(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    for e, r in [("&amp;","&"),("&lt;","<"),("&gt;",">"),("&quot;",'"'),("&#39;","'"),("&nbsp;"," ")]:
        text = text.replace(e, r)
    return text.strip()

def parse_date(s):
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"]:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            kdt = dt.astimezone(KST)
            return kdt.strftime("%Y-%m-%d"), kdt.strftime("%H:%M")
        except:
            continue
    return yesterday, ""

def fetch_rss(query, lang="ko", cat="general", max_items=6):
    if lang == "ko":
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    else:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en&gl=US&ceid=US:en"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        root = ET.fromstring(r.content)
        results = []
        for item in root.findall(".//item")[:max_items]:
            title = clean(item.findtext("title", ""))
            link  = item.findtext("link", "") or ""
            desc  = clean(item.findtext("description", ""))
            pub   = item.findtext("pubDate", "")
            src   = item.find("source")
            source = (src.text if src is not None else ("Google 뉴스" if lang == "ko" else "Google News"))
            if lang == "en":
                source = source + " (EN)"
            if not title or len(title) < 5:
                continue
            d, t = parse_date(pub) if pub else (yesterday, "")
            if d < yesterday:
                continue
            guessed = categorize(title, desc)
            results.append({
                "title":   title,
                "summary": (desc[:200] + "...") if len(desc) > 200 else desc,
                "url":     link,
                "source":  source,
                "date":    d,
                "time":    t,
                "cat":     guessed if guessed != "general" else cat,
                "imp":     is_important(title),
                "lang":    lang,
            })
        print(f"  [{lang}] '{query}': {len(results)}건")
        return results
    except Exception as e:
        print(f"  [{lang}] '{query}' 오류: {e}")
        return []

# ── 검색 쿼리 ─────────────────────────────────────────────
KO_QUERIES = [
    ("탈모 치료 신약 제약",        "dermatology", 6),
    ("피부과 의약품",              "dermatology", 4),
    ("당뇨 고혈압 신약 치료",      "chronic",     6),
    ("고지혈증 비만 치료제",        "chronic",     4),
    ("프로바이오틱스 장내미생물",   "probiotics",  6),
    ("낙산균 유산균 효모균",        "probiotics",  4),
    ("리팍시민 IBS 과민성장",       "rifaximin",   5),
    ("소아과 소아청소년 의료",      "pediatrics",  6),
    ("어린이 소아 건강 의료",       "pediatrics",  5),
    ("소아과 정책 수가",            "pediatrics",  4),
    ("식약처 신약 허가 승인",       "approval",    6),
    ("임상시험 3상 결과",          "clinical",    5),
    ("제약사 기술이전 바이오",      "pharma",      5),
    ("건강보험 급여 의약품 정책",   "policy",      4),
]

EN_QUERIES = [
    ("alopecia hair loss new drug 2026",        "dermatology", 4),
    ("rifaximin SIBO IBS study",                "rifaximin",   4),
    ("probiotic microbiome gut health",         "probiotics",  4),
    ("pediatric children medicine health",      "pediatrics",  4),
    ("FDA drug approval 2026",                  "approval",    4),
    ("GLP-1 diabetes obesity drug",             "chronic",     4),
]

# ── 수집 ─────────────────────────────────────────────────
all_articles = []
seen = set()

print("\n[한국어 뉴스]")
for q, c, n in KO_QUERIES:
    for a in fetch_rss(q, "ko", c, n):
        k = a["title"][:40].lower()
        if k not in seen and a["url"]:
            seen.add(k)
            all_articles.append(a)

print("\n[영어 뉴스]")
for q, c, n in EN_QUERIES:
    for a in fetch_rss(q, "en", c, n):
        k = a["title"][:40].lower()
        if k not in seen and a["url"]:
            seen.add(k)
            all_articles.append(a)

all_articles.sort(key=lambda x: (x["date"], x.get("time","")), reverse=True)
all_articles = all_articles[:25]

print(f"\n최종: {len(all_articles)}건")
for a in all_articles:
    flag = "🇰🇷" if a["lang"]=="ko" else "🌐"
    print(f"  {flag}[{a['cat']}] {a['title'][:55]}")

# ── HTML 작성 ─────────────────────────────────────────────
def make_html(articles, update_time):
    data = json.dumps(articles, ensure_ascii=False)
    return '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#080d18">
<title>제약·의료 데일리 브리핑</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
:root{--bg:#080d18;--bg2:#0f1623;--bg3:#161e2e;--bg4:#1c2639;--border:rgba(255,255,255,.07);--border2:rgba(255,255,255,.13);--text:#f0f4ff;--text2:#8b93a8;--text3:#505a6e;--accent:#00c896;--adim:rgba(0,200,150,.12);--fn:"Noto Sans KR",sans-serif;--fs:"DM Serif Display",serif;--r:14px;--rs:8px}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);font-family:var(--fn);font-size:15px;line-height:1.6;overflow-x:hidden}
.hdr{position:sticky;top:0;z-index:100;background:rgba(8,13,24,.95);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-bottom:.5px solid var(--border);padding:13px 18px 11px}
.hdr-in{max-width:680px;margin:0 auto}
.hrow{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
.brand{display:flex;align-items:center;gap:9px}
.bico{width:33px;height:33px;background:linear-gradient(135deg,#00c896,#009e78);border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.bico svg{width:17px;height:17px}
.bname{font-size:15px;font-weight:600;letter-spacing:-.3px}
.bname em{font-style:normal;color:var(--accent)}
.upd{font-size:11px;color:var(--text3);background:var(--bg3);border:.5px solid var(--border2);border-radius:20px;padding:4px 10px;white-space:nowrap}
.srow{display:flex;align-items:center;gap:6px;margin-top:5px}
.dot{width:5px;height:5px;border-radius:50%;background:var(--accent);box-shadow:0 0 5px var(--accent);flex-shrink:0}
.stxt{font-size:11.5px;color:var(--text3)}
.tabbar{background:var(--bg2);border-bottom:.5px solid var(--border);overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.tabbar::-webkit-scrollbar{display:none}
.tabs{display:flex;padding:0 18px;width:max-content}
.tab{font-size:12.5px;font-family:var(--fn);font-weight:500;padding:10px 14px;border-bottom:2px solid transparent;color:var(--text3);cursor:pointer;white-space:nowrap;transition:.15s;user-select:none}
.tab.on{color:var(--accent);border-bottom-color:var(--accent)}
.cwrap{padding:10px 0;border-bottom:.5px solid var(--border);overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.cwrap::-webkit-scrollbar{display:none}
.cats{display:flex;gap:6px;padding:0 18px;width:max-content}
.cat{font-size:12px;font-family:var(--fn);font-weight:500;padding:4px 12px;border-radius:20px;border:.5px solid var(--border2);background:transparent;color:var(--text2);cursor:pointer;white-space:nowrap;transition:.15s;user-select:none}
.cat:active{transform:scale(.95)}
.cat.on{background:var(--adim);border-color:var(--accent);color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px 18px;max-width:680px;margin:0 auto}
.sc{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--rs);padding:9px 12px;text-align:center}
.sn{font-size:20px;font-weight:700;font-family:var(--fs);color:var(--accent);line-height:1.1;margin-bottom:2px}
.sl{font-size:10px;color:var(--text3);letter-spacing:.3px}
.awrap{padding:0 18px 80px;max-width:680px;margin:0 auto}
.sec{font-size:10px;font-weight:600;letter-spacing:1.1px;color:var(--text3);text-transform:uppercase;padding:14px 0 7px}
.card{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--r);margin-bottom:8px;overflow:hidden}
.card.hi{border-left:3px solid var(--accent)}
.card.md{border-left:3px solid var(--bg4)}
.card-hd{padding:13px 15px 11px;cursor:pointer;user-select:none;-webkit-user-select:none}
.card-hd:active{background:var(--bg3)}
.ctop{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:7px;align-items:center}
.bdg{font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;display:inline-flex;align-items:center}
.bdg.dermatology{background:rgba(255,122,101,.14);color:#ff9a89}
.bdg.clinical{background:rgba(245,166,35,.14);color:#f5c35a}
.bdg.approval{background:rgba(74,158,255,.14);color:#6db3ff}
.bdg.policy{background:rgba(155,127,255,.14);color:#b89fff}
.bdg.pharma{background:rgba(0,200,150,.14);color:#00c896}
.bdg.probiotics{background:rgba(0,200,150,.08);color:#4cd9b0;border:.5px solid rgba(0,200,150,.2)}
.bdg.pediatrics{background:rgba(255,92,106,.12);color:#ff8a96}
.bdg.chronic{background:rgba(245,166,35,.12);color:#e8a020}
.bdg.rifaximin{background:rgba(74,158,255,.1);color:#7ab8ff;border:.5px solid rgba(74,158,255,.2)}
.bdg.general{background:rgba(139,147,168,.12);color:#8b93a8}
.bdg.imp{background:var(--adim);color:var(--accent)}
.bdg.en{background:rgba(139,147,168,.1);color:var(--text3);font-size:9px}
.ctit{font-size:14px;font-weight:500;line-height:1.5;color:var(--text)}
.cmeta{display:flex;align-items:center;gap:7px;margin-top:7px;flex-wrap:wrap}
.csrc{font-size:11px;color:var(--text3)}
.cdt{font-size:11px;color:var(--text3)}
.cbody{display:none;border-top:.5px solid var(--border)}
.card.open .cbody{display:block}
.csum{font-size:13px;color:var(--text2);line-height:1.75;padding:12px 15px 10px}
.cfoot{padding:0 15px 13px}
.clink{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--accent);text-decoration:none;background:var(--adim);padding:7px 14px;border-radius:20px;border:.5px solid rgba(0,200,150,.25)}
.clink:active{opacity:.7}
.clink svg{width:11px;height:11px;flex-shrink:0}
.ctog{display:flex;align-items:center;justify-content:center;gap:5px;padding:9px;cursor:pointer;border-top:.5px solid var(--border);user-select:none;-webkit-user-select:none}
.ctog span{font-size:11px;color:var(--text3)}
.arr{display:inline-block;transition:transform .2s;font-size:12px;color:var(--text3)}
.card.open .arr{transform:rotate(180deg)}
.empty{text-align:center;padding:50px 20px}
.etit{font-family:var(--fs);font-size:20px;margin-bottom:7px;color:var(--text)}
.edsc{font-size:13px;color:var(--text3);line-height:1.8}
@media(min-width:480px){.hdr,.tabbar{padding-left:24px;padding-right:24px}.tabs,.cats{padding-left:24px;padding-right:24px}.awrap,.stats{padding-left:24px;padding-right:24px}}
</style>
</head>
<body>
<header class="hdr"><div class="hdr-in">
  <div class="hrow">
    <div class="brand">
      <div class="bico"><svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v2"/><path d="M4 22a2 2 0 010-4h2v4"/><path d="M9 9h8M9 13h8M9 17h4"/></svg></div>
      <div class="bname">제약·의료 <em>데일리</em></div>
    </div>
    <span class="upd">⚡ ''' + update_time + ''' 업데이트</span>
  </div>
  <div class="srow"><div class="dot"></div><span class="stxt" id="stxt">기사 로딩 중...</span></div>
</div></header>
<div class="tabbar"><div class="tabs" id="tabs"></div></div>
<div class="cwrap"><div class="cats">
  <button class="cat on" onclick="fCat('all',this)">전체</button>
  <button class="cat" onclick="fCat('dermatology',this)">탈모·피부과</button>
  <button class="cat" onclick="fCat('chronic',this)">만성질환</button>
  <button class="cat" onclick="fCat('probiotics',this)">프로바이오틱스</button>
  <button class="cat" onclick="fCat('rifaximin',this)">Rifaximin</button>
  <button class="cat" onclick="fCat('pediatrics',this)">소아과</button>
  <button class="cat" onclick="fCat('pharma',this)">제약사 동향</button>
  <button class="cat" onclick="fCat('clinical',this)">임상시험</button>
  <button class="cat" onclick="fCat('approval',this)">신약 승인</button>
  <button class="cat" onclick="fCat('policy',this)">정책·규제</button>
</div></div>
<div class="stats">
  <div class="sc"><div class="sn" id="stt">0</div><div class="sl">전체 기사</div></div>
  <div class="sc"><div class="sn" id="shi">0</div><div class="sl">주요 기사</div></div>
  <div class="sc"><div class="sn" id="sca">0</div><div class="sl">카테고리</div></div>
</div>
<div class="awrap"><div id="alist"></div></div>
<script>
var CL={dermatology:"탈모·피부과",clinical:"임상시험",approval:"신약 승인",policy:"정책·규제",pharma:"제약사 동향",probiotics:"프로바이오틱스",pediatrics:"소아과",chronic:"만성질환",rifaximin:"Rifaximin",general:"일반"};
var D=''' + data + ''';
var curCat="all",curDate="all";
function tog(card){card.classList.toggle("open");}
function card(a,i){
  var cl=CL[a.cat]||"일반";
  var imp=a.imp==="high"?"<span class='bdg imp'>★ 주요</span>":"";
  var en=a.lang==="en"?"<span class='bdg en'>EN</span>":"";
  var ds=a.time?a.date.replace(/-/g,".")+' '+a.time:a.date.replace(/-/g,".");
  var sm=a.summary?a.summary:"원문을 확인해주세요.";
  return "<div class='card "+(a.imp==="high"?"hi":"md")+"'>"
    +"<div class='card-hd' onclick='tog(this.closest(\".card\"))'>"
    +"<div class='ctop'><span class='bdg "+a.cat+"'>"+cl+"</span>"+imp+en+"</div>"
    +"<div class='ctit'>"+a.title+"</div>"
    +"<div class='cmeta'><span class='csrc'>"+a.source+"</span><span style='color:var(--bg4)'>·</span><span class='cdt'>"+ds+"</span></div>"
    +"</div>"
    +"<div class='cbody'>"
    +"<div class='csum'>"+sm+"</div>"
    +"<div class='cfoot'><a class='clink' href='"+a.url+"' target='_blank' rel='noopener'>"
    +"<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><path d='M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6'/><polyline points='15 3 21 3 21 9'/><line x1='10' y1='14' x2='21' y2='3'/></svg>"
    +"원문 기사 보기 ("+a.source+")</a></div>"
    +"</div>"
    +"<div class='ctog' onclick='tog(this.closest(\".card\"))'><span>요약 · 원문 링크</span><span class='arr'>∨</span></div>"
    +"</div>";
}
function tabs(){
  var dates=[...new Set(D.map(function(a){return a.date;}))].sort().reverse();
  var h="<button class='tab on' onclick='selD(\"all\",this)'>전체 <span style='font-size:10px;opacity:.6'>"+D.length+"</span></button>";
  dates.forEach(function(d){
    var n=D.filter(function(a){return a.date===d;}).length;
    var dd=new Date(d+"T00:00:00+09:00"),t=new Date();t.setHours(0,0,0,0);
    var df=Math.round((t-dd)/86400000);
    var lb=df===0?"오늘":df===1?"어제":df+"일 전";
    h+="<button class='tab' onclick='selD(\""+d+"\",this)'>"+lb+" <span style='font-size:10px;opacity:.6'>"+n+"</span></button>";
  });
  document.getElementById("tabs").innerHTML=h;
}
function selD(d,b){curDate=d;document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("on");});b.classList.add("on");render();}
function fCat(c,b){curCat=c;document.querySelectorAll(".cat").forEach(function(x){x.classList.remove("on");});b.classList.add("on");render();}
function render(){
  var list=D.filter(function(a){return(curDate==="all"||a.date===curDate)&&(curCat==="all"||a.cat===curCat);});
  document.getElementById("stt").textContent=D.length;
  document.getElementById("shi").textContent=D.filter(function(a){return a.imp==="high";}).length;
  document.getElementById("sca").textContent=[...new Set(D.map(function(a){return a.cat;}))].length;
  document.getElementById("stxt").textContent=D.length+"건 · 매일 오전 6시 자동 업데이트";
  var el=document.getElementById("alist");
  if(!list.length){el.innerHTML="<div class='empty'><div class='etit'>해당 기사 없음</div><div class='edsc'>날짜나 카테고리를 바꿔보세요.</div></div>";return;}
  var g={};list.forEach(function(a){if(!g[a.date])g[a.date]=[];g[a.date].push(a);});
  var h="";
  Object.keys(g).sort().reverse().forEach(function(d){
    var dd=new Date(d+"T00:00:00+09:00"),t=new Date();t.setHours(0,0,0,0);
    var df=Math.round((t-dd)/86400000);
    var lb=df===0?"오늘":df===1?"어제":df+"일 전";
    h+="<div class='sec'>"+lb+" · "+g[d].length+"건</div>";
    h+=g[d].map(function(a,i){return card(a,d+i);}).join("");
  });
  el.innerHTML=h;
}
tabs();render();
</script>
</body>
</html>'''

with open("index.html", "w", encoding="utf-8") as f:
    f.write(make_html(all_articles, update_str))

print("index.html 생성 완료!")
