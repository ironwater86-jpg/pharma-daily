#!/usr/bin/env python3
"""
제약·의료 데일리 뉴스 수집기
- 한국 제약 전문 언론사 RSS 직접 수집 (서버사이드 → CORS 없음)
- 영어 글로벌 뉴스 RSS 추가
- 키워드 기반 카테고리 분류
- index.html 자동 생성
"""
import json, re, requests
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
YESTERDAY = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")
UPDATE_STR = NOW.strftime("%Y.%m.%d %H:%M")

print(f"=== 뉴스 수집 시작: {UPDATE_STR} KST ===")
print(f"수집 대상 날짜: {YESTERDAY} ~ {NOW.strftime('%Y-%m-%d')}")

# ── 한국 제약·의료 전문 언론사 RSS ──────────────────────────
KO_FEEDS = [
    ("https://www.yakup.com/rss/index.php",             "약업신문"),
    ("https://www.medipana.com/rss/rss.php",            "메디파나뉴스"),
    ("https://www.pharmnews.com/rss/allArticle.xml",    "팜뉴스"),
    ("https://www.hitnews.co.kr/rss/allArticle.xml",    "히트뉴스"),
    ("https://www.dailypharm.com/rss/",                 "데일리팜"),
    ("https://www.medicaltimes.com/rss/allArticle.xml", "메디컬타임스"),
    ("https://www.bosa.co.kr/rss/allArticle.xml",       "보건신문"),
    ("https://www.docdocdoc.co.kr/rss/allArticle.xml",  "청년의사"),
]

# ── 글로벌 영문 RSS ───────────────────────────────────────
EN_FEEDS = [
    ("https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml", "FDA"),
    ("https://www.fiercepharma.com/rss/xml",            "FiercePharma"),
    ("https://www.healio.com/rss/gastroenterology",     "Healio GI"),
    ("https://www.healio.com/rss/pediatrics",           "Healio Pediatrics"),
]

# ── 카테고리 키워드 ───────────────────────────────────────
CAT_KW = {
    "dermatology": [
        "탈모","두피","모발","헤어","피부과","헤어그로","헤어덤","아다모","두타스테리드","피나스테리드","미녹시딜",
        "alopecia","hair loss","hair growth","minoxidil","finasteride","DHT","scalp","dermatol"
    ],
    "chronic": [
        "당뇨","고혈압","고지혈증","비만","혈당","인슐린","스타틴","GLP-1","SGLT","심혈관","심장","뇌졸중",
        "diabetes","hypertension","cholesterol","obesity","cardiovascular","insulin","statin"
    ],
    "probiotics": [
        "프로바이오틱스","유산균","낙산균","효모균","당화균","장내미생물","마이크로바이옴","유익균","장건강",
        "probiotic","microbiome","gut bacteria","butyrate","lactobacil","bifidobacter","gut health"
    ],
    "rifaximin": [
        "rifaximin","리팍시민","SIBO","IBS","과민성장증후군","간성뇌증","장내세균과증식",
        "irritable bowel","hepatic encephalopathy","small intestinal bacterial"
    ],
    "pediatrics": [
        "소아과","소아청소년","소아","어린이","아동","신생아","영아","소아병원","소아전문","소아의","소아 ",
        "pediatric","children","infant","neonatal","child health","kids"
    ],
    "pharma": [
        "기술이전","라이선스아웃","라이선스 계약","M&A","인수합병","파이프라인","매출","영업이익","수출","계약","제약사",
        "licensing","acquisition","merger","pipeline","revenue","pharma deal","biotech"
    ],
    "approval": [
        "식약처 허가","품목허가","신약 허가","승인","허가 취득","FDA 승인","EMA 승인","의약품 허가",
        "FDA approved","EMA approved","drug approval","market authorization","NDA","BLA"
    ],
    "clinical": [
        "임상시험","임상 3상","임상 2상","임상 1상","임상결과","임상 완료","IND","임상계획",
        "phase 3","phase 2","phase 1","clinical trial","randomized","placebo"
    ],
    "policy": [
        "건강보험","보험급여","급여 등재","수가","약가","복지부","보건부","식약처 정책","의료정책","의약품 정책",
        "reimbursement","healthcare policy","insurance coverage","drug pricing","NHIS"
    ],
}

def categorize(title, desc=""):
    txt = (title + " " + desc).lower()
    scores = {}
    for cat, kws in CAT_KW.items():
        scores[cat] = sum(2 if len(k) >= 4 else 1 for k in kws if k.lower() in txt)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

def is_important(title):
    hi = ["허가","승인","fda","3상","신약","임상 성공","출시","급여","approved","breakthrough","phase 3","신규"]
    return "high" if any(w in title.lower() for w in hi) else "medium"

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    for e, r in [("&amp;","&"),("&lt;","<"),("&gt;",">"),("&quot;",'"'),("&#39;","'"),("&nbsp;"," "),("&#35;","#")]:
        text = text.replace(e, r)
    return re.sub(r'\s+', ' ', text).strip()

def parse_date(s):
    if not s:
        return YESTERDAY, ""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            kdt = dt.astimezone(KST)
            return kdt.strftime("%Y-%m-%d"), kdt.strftime("%H:%M")
        except:
            continue
    return YESTERDAY, ""

def fetch_feed(url, source_name, lang="ko", max_items=20):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        # 인코딩 처리
        if "euc-kr" in r.headers.get("content-type","").lower():
            r.encoding = "euc-kr"
        elif "charset=euc-kr" in r.text.lower()[:200]:
            r.encoding = "euc-kr"
        else:
            r.encoding = r.apparent_encoding or "utf-8"

        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        results = []

        for item in items[:max_items]:
            title = clean_html(item.findtext("title", ""))
            link  = item.findtext("link", "") or item.findtext("{http://www.w3.org/2005/Atom}link", "")
            desc  = clean_html(item.findtext("description", ""))
            pub   = item.findtext("pubDate", "") or item.findtext("pubdate", "")

            if not title or len(title) < 5:
                continue
            # 광고성 제목 필터
            if any(w in title for w in ["광고","AD ","[광고]","이벤트 당첨"]):
                continue

            d, t = parse_date(pub)

            # 최근 2일치만 (오늘 + 어제)
            today_str = NOW.strftime("%Y-%m-%d")
            if d < YESTERDAY:
                continue

            results.append({
                "title":   title,
                "summary": (desc[:250] + "...") if len(desc) > 250 else desc,
                "url":     link.strip(),
                "source":  source_name + (" (EN)" if lang == "en" else ""),
                "date":    d,
                "time":    t,
                "cat":     categorize(title, desc),
                "imp":     is_important(title),
                "lang":    lang,
            })

        ok = len(results)
        total = len(items)
        print(f"  ✅ {source_name}: {ok}건 수집 / {total}건 중 (최근 2일)")
        return results

    except requests.exceptions.Timeout:
        print(f"  ⏱ {source_name}: 타임아웃")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ {source_name}: HTTP {e.response.status_code}")
        return []
    except ET.ParseError as e:
        print(f"  ❌ {source_name}: XML 파싱 오류 - {e}")
        return []
    except Exception as e:
        print(f"  ❌ {source_name}: {e}")
        return []

# ── 수집 실행 ─────────────────────────────────────────────
all_articles = []
seen = set()

print("\n[한국 제약·의료 전문지 RSS]")
for url, name in KO_FEEDS:
    for a in fetch_feed(url, name, "ko"):
        key = a["title"][:35].lower()
        if key not in seen and a["url"]:
            seen.add(key)
            all_articles.append(a)

print("\n[글로벌 영문 RSS]")
for url, name in EN_FEEDS:
    for a in fetch_feed(url, name, "en"):
        key = a["title"][:35].lower()
        if key not in seen and a["url"]:
            seen.add(key)
            all_articles.append(a)

# 정렬: 날짜↓ → 중요도↓
all_articles.sort(key=lambda x: (x["date"], x.get("time",""), x["imp"]=="high"), reverse=True)
all_articles = all_articles[:30]

print(f"\n=== 최종 수집: {len(all_articles)}건 ===")
cat_count = {}
for a in all_articles:
    cat_count[a["cat"]] = cat_count.get(a["cat"], 0) + 1
    flag = "🇰🇷" if a["lang"] == "ko" else "🌐"
    print(f"  {flag} [{a['cat']:12}] {a['title'][:50]}")
print("\n카테고리별:", {k:v for k,v in sorted(cat_count.items())})

# ── HTML 생성 ─────────────────────────────────────────────
DATA_JSON = json.dumps(all_articles, ensure_ascii=False)

HTML = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#080d18">
<title>제약·의료 데일리 브리핑</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
:root{{--bg:#080d18;--bg2:#0f1623;--bg3:#161e2e;--bg4:#1c2639;--border:rgba(255,255,255,.07);--border2:rgba(255,255,255,.13);--text:#f0f4ff;--text2:#8b93a8;--text3:#505a6e;--accent:#00c896;--adim:rgba(0,200,150,.12);--fn:"Noto Sans KR",sans-serif;--fs:"DM Serif Display",serif;--r:14px;--rs:8px}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
html,body{{background:var(--bg);color:var(--text);font-family:var(--fn);font-size:15px;line-height:1.6;overflow-x:hidden}}
.hdr{{position:sticky;top:0;z-index:100;background:rgba(8,13,24,.95);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-bottom:.5px solid var(--border);padding:13px 18px 11px}}
.hi{{max-width:680px;margin:0 auto}}
.hr{{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}}
.brand{{display:flex;align-items:center;gap:9px}}
.bico{{width:33px;height:33px;background:linear-gradient(135deg,#00c896,#009e78);border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.bico svg{{width:17px;height:17px}}
.bname{{font-size:15px;font-weight:600;letter-spacing:-.3px}}
.bname em{{font-style:normal;color:var(--accent)}}
.upd{{font-size:11px;color:var(--text3);background:var(--bg3);border:.5px solid var(--border2);border-radius:20px;padding:4px 10px;white-space:nowrap}}
.sr{{display:flex;align-items:center;gap:6px;margin-top:5px}}
.dot{{width:5px;height:5px;border-radius:50%;background:var(--accent);box-shadow:0 0 5px var(--accent);flex-shrink:0}}
.stx{{font-size:11.5px;color:var(--text3)}}
.tbr{{background:var(--bg2);border-bottom:.5px solid var(--border);overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}}
.tbr::-webkit-scrollbar{{display:none}}
.tbs{{display:flex;padding:0 18px;width:max-content}}
.tb{{font-size:12.5px;font-family:var(--fn);font-weight:500;padding:10px 14px;border-bottom:2px solid transparent;color:var(--text3);cursor:pointer;white-space:nowrap;transition:.15s;user-select:none}}
.tb.on{{color:var(--accent);border-bottom-color:var(--accent)}}
.cwr{{padding:10px 0;border-bottom:.5px solid var(--border);overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}}
.cwr::-webkit-scrollbar{{display:none}}
.cts{{display:flex;gap:6px;padding:0 18px;width:max-content}}
.ct{{font-size:12px;font-family:var(--fn);font-weight:500;padding:4px 12px;border-radius:20px;border:.5px solid var(--border2);background:transparent;color:var(--text2);cursor:pointer;white-space:nowrap;transition:.15s;user-select:none}}
.ct:active{{transform:scale(.95)}}
.ct.on{{background:var(--adim);border-color:var(--accent);color:var(--accent)}}
.sts{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px 18px;max-width:680px;margin:0 auto}}
.sc{{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--rs);padding:9px 12px;text-align:center}}
.sn{{font-size:20px;font-weight:700;font-family:var(--fs);color:var(--accent);line-height:1.1;margin-bottom:2px}}
.sl{{font-size:10px;color:var(--text3);letter-spacing:.3px}}
.aw{{padding:0 18px 80px;max-width:680px;margin:0 auto}}
.sh{{font-size:10px;font-weight:600;letter-spacing:1.1px;color:var(--text3);text-transform:uppercase;padding:14px 0 7px}}
.card{{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--r);margin-bottom:8px;overflow:hidden}}
.card.hi2{{border-left:3px solid var(--accent)}}
.card.md{{border-left:3px solid var(--bg4)}}
.chd{{padding:13px 15px 11px;cursor:pointer;user-select:none;-webkit-user-select:none}}
.chd:active{{background:var(--bg3)}}
.ctp{{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:7px;align-items:center}}
.bdg{{font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;display:inline-flex;align-items:center}}
.bdg.dermatology{{background:rgba(255,122,101,.14);color:#ff9a89}}
.bdg.clinical{{background:rgba(245,166,35,.14);color:#f5c35a}}
.bdg.approval{{background:rgba(74,158,255,.14);color:#6db3ff}}
.bdg.policy{{background:rgba(155,127,255,.14);color:#b89fff}}
.bdg.pharma{{background:rgba(0,200,150,.14);color:#00c896}}
.bdg.probiotics{{background:rgba(0,200,150,.08);color:#4cd9b0;border:.5px solid rgba(0,200,150,.2)}}
.bdg.pediatrics{{background:rgba(255,92,106,.12);color:#ff8a96}}
.bdg.chronic{{background:rgba(245,166,35,.12);color:#e8a020}}
.bdg.rifaximin{{background:rgba(74,158,255,.1);color:#7ab8ff;border:.5px solid rgba(74,158,255,.2)}}
.bdg.general{{background:rgba(139,147,168,.12);color:#8b93a8}}
.bdg.imp{{background:var(--adim);color:var(--accent)}}
.bdg.en{{background:rgba(139,147,168,.1);color:var(--text3);font-size:9px}}
.cti{{font-size:14px;font-weight:500;line-height:1.5;color:var(--text)}}
.cme{{display:flex;align-items:center;gap:7px;margin-top:7px;flex-wrap:wrap}}
.cso{{font-size:11px;color:var(--text3)}}
.cda{{font-size:11px;color:var(--text3)}}
.cbd{{display:none;border-top:.5px solid var(--border)}}
.card.open .cbd{{display:block}}
.csu{{font-size:13px;color:var(--text2);line-height:1.75;padding:12px 15px 10px}}
.cfo{{padding:0 15px 13px}}
.clk{{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--accent);text-decoration:none;background:var(--adim);padding:7px 14px;border-radius:20px;border:.5px solid rgba(0,200,150,.25)}}
.clk:active{{opacity:.7}}
.clk svg{{width:11px;height:11px;flex-shrink:0}}
.ctg{{display:flex;align-items:center;justify-content:center;gap:5px;padding:9px;cursor:pointer;border-top:.5px solid var(--border);user-select:none;-webkit-user-select:none}}
.ctg span{{font-size:11px;color:var(--text3)}}
.arr{{display:inline-block;transition:transform .2s;font-size:12px;color:var(--text3)}}
.card.open .arr{{transform:rotate(180deg)}}
.emp{{text-align:center;padding:50px 20px}}
.eti{{font-family:var(--fs);font-size:20px;margin-bottom:7px;color:var(--text)}}
.ede{{font-size:13px;color:var(--text3);line-height:1.8}}
@media(min-width:480px){{.hdr,.tbr{{padding-left:24px;padding-right:24px}}.tbs,.cts{{padding-left:24px;padding-right:24px}}.aw,.sts{{padding-left:24px;padding-right:24px}}}}
</style>
</head>
<body>
<header class="hdr"><div class="hi">
  <div class="hr">
    <div class="brand">
      <div class="bico"><svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v2"/><path d="M4 22a2 2 0 010-4h2v4"/><path d="M9 9h8M9 13h8M9 17h4"/></svg></div>
      <div class="bname">제약·의료 <em>데일리</em></div>
    </div>
    <span class="upd">⚡ {UPDATE_STR} 업데이트</span>
  </div>
  <div class="sr"><div class="dot"></div><span class="stx" id="stx">기사 로딩 중...</span></div>
</div></header>

<div class="tbr"><div class="tbs" id="tabs"></div></div>

<div class="cwr"><div class="cts">
  <button class="ct on" onclick="fC('all',this)">전체</button>
  <button class="ct" onclick="fC('dermatology',this)">탈모·피부과</button>
  <button class="ct" onclick="fC('chronic',this)">만성질환</button>
  <button class="ct" onclick="fC('probiotics',this)">프로바이오틱스</button>
  <button class="ct" onclick="fC('rifaximin',this)">Rifaximin</button>
  <button class="ct" onclick="fC('pediatrics',this)">소아과</button>
  <button class="ct" onclick="fC('pharma',this)">제약사 동향</button>
  <button class="ct" onclick="fC('clinical',this)">임상시험</button>
  <button class="ct" onclick="fC('approval',this)">신약 승인</button>
  <button class="ct" onclick="fC('policy',this)">정책·규제</button>
</div></div>

<div class="sts">
  <div class="sc"><div class="sn" id="s1">0</div><div class="sl">전체 기사</div></div>
  <div class="sc"><div class="sn" id="s2">0</div><div class="sl">주요 기사</div></div>
  <div class="sc"><div class="sn" id="s3">0</div><div class="sl">카테고리</div></div>
</div>

<div class="aw"><div id="al"></div></div>

<script>
var CL={{dermatology:"탈모·피부과",clinical:"임상시험",approval:"신약 승인",policy:"정책·규제",pharma:"제약사 동향",probiotics:"프로바이오틱스",pediatrics:"소아과",chronic:"만성질환",rifaximin:"Rifaximin",general:"일반"}};
var D={DATA_JSON};
var curC="all",curD="all";

function tog(card){{card.classList.toggle("open");}}

function mkCard(a){{
  var cl=CL[a.cat]||"일반";
  var imp=a.imp==="high"?"<span class='bdg imp'>★ 주요</span>":"";
  var en=a.lang==="en"?"<span class='bdg en'>EN</span>":"";
  var ds=a.time?a.date.replace(/-/g,".")+" "+a.time:a.date.replace(/-/g,".");
  var sm=a.summary||"원문을 확인해주세요.";
  return "<div class='card "+(a.imp==="high"?"hi2":"md")+"'>"
    +"<div class='chd' onclick='tog(this.closest(\".card\"))'>"
    +"<div class='ctp'><span class='bdg "+a.cat+"'>"+cl+"</span>"+imp+en+"</div>"
    +"<div class='cti'>"+a.title+"</div>"
    +"<div class='cme'><span class='cso'>"+a.source+"</span><span style='color:var(--bg4)'>·</span><span class='cda'>"+ds+"</span></div>"
    +"</div>"
    +"<div class='cbd'>"
    +"<div class='csu'>"+sm+"</div>"
    +"<div class='cfo'><a class='clk' href='"+a.url+"' target='_blank' rel='noopener'>"
    +"<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><path d='M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6'/><polyline points='15 3 21 3 21 9'/><line x1='10' y1='14' x2='21' y2='3'/></svg>"
    +"원문 기사 보기 ("+a.source+")</a></div>"
    +"</div>"
    +"<div class='ctg' onclick='tog(this.closest(\".card\"))'>"
    +"<span>요약 · 원문 링크</span><span class='arr'>∨</span>"
    +"</div></div>";
}}

function bldTabs(){{
  var dates=[...new Set(D.map(function(a){{return a.date;}}))] .sort().reverse();
  var h="<button class='tb on' onclick='sD(\"all\",this)'>전체 <span style='font-size:10px;opacity:.6'>"+D.length+"</span></button>";
  dates.forEach(function(d){{
    var n=D.filter(function(a){{return a.date===d;}}).length;
    var dd=new Date(d+"T00:00:00+09:00"),t=new Date();t.setHours(0,0,0,0);
    var df=Math.round((t-dd)/86400000);
    var lb=df===0?"오늘":df===1?"어제":df+"일 전";
    h+="<button class='tb' onclick='sD(\""+d+"\",this)'>"+lb+" <span style='font-size:10px;opacity:.6'>"+n+"</span></button>";
  }});
  document.getElementById("tabs").innerHTML=h;
}}

function sD(d,b){{curD=d;document.querySelectorAll(".tb").forEach(function(x){{x.classList.remove("on");}});b.classList.add("on");render();}}
function fC(c,b){{curC=c;document.querySelectorAll(".ct").forEach(function(x){{x.classList.remove("on");}});b.classList.add("on");render();}}

function render(){{
  var list=D.filter(function(a){{return(curD==="all"||a.date===curD)&&(curC==="all"||a.cat===curC);}});
  document.getElementById("s1").textContent=D.length;
  document.getElementById("s2").textContent=D.filter(function(a){{return a.imp==="high";}}).length;
  document.getElementById("s3").textContent=[...new Set(D.map(function(a){{return a.cat;}}))].length;
  document.getElementById("stx").textContent=D.length+"건 · 매일 오전 6시 자동 업데이트";
  var el=document.getElementById("al");
  if(!list.length){{
    el.innerHTML="<div class='emp'><div class='eti'>해당 기사 없음</div><div class='ede'>날짜나 카테고리를 바꿔보세요.</div></div>";
    return;
  }}
  var g={{}};
  list.forEach(function(a){{if(!g[a.date])g[a.date]=[];g[a.date].push(a);}});
  var h="";
  Object.keys(g).sort().reverse().forEach(function(d){{
    var dd=new Date(d+"T00:00:00+09:00"),t=new Date();t.setHours(0,0,0,0);
    var df=Math.round((t-dd)/86400000);
    var lb=df===0?"오늘":df===1?"어제":df+"일 전";
    h+="<div class='sh'>"+lb+" · "+g[d].length+"건</div>";
    h+=g[d].map(mkCard).join("");
  }});
  el.innerHTML=h;
}}

bldTabs();render();
</script>
</body>
</html>"""

# {DATA_JSON} 치환
HTML = HTML.replace("{DATA_JSON}", DATA_JSON)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"\n✅ index.html 생성 완료! ({len(all_articles)}건)")
