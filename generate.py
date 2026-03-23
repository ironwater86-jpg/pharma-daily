import os, json, requests, re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

API_KEY = os.environ.get("NEWS_API_KEY", "")  # 영어 뉴스용 (선택)
KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
yesterday_dt = now_kst - timedelta(days=1)
yesterday = yesterday_dt.strftime("%Y-%m-%d")
update_str = now_kst.strftime("%Y.%m.%d %H:%M")

print(f"수집 시작: {update_str} KST / 대상: {yesterday}")

# ── 카테고리 키워드 ────────────────────────────────────────
CAT_KW = {
    "dermatology": ["탈모","두피","모발","헤어","피부과","alopecia","hair loss","hair growth","minoxidil","finasteride","DHT","헤어그로","클라스코테론"],
    "chronic":     ["당뇨","고혈압","고지혈증","비만","심혈관","혈당","인슐린","스타틴","GLP-1","SGLT","diabetes","hypertension","cholesterol","obesity","cardiovascular"],
    "probiotics":  ["프로바이오틱스","유산균","낙산균","효모균","당화균","장내미생물","마이크로바이옴","microbiome","probiotic","gut bacteria","butyrate","lactobacil"],
    "rifaximin":   ["rifaximin","리팍시민","SIBO","IBS","과민성장","간성뇌증","장내항생제","hepatic encephalopathy","irritable bowel"],
    "pediatrics":  ["소아과","소아청소년","소아","어린이","아동","신생아","영아","pediatric","children","infant","neonatal"],
    "pharma":      ["제약","바이오","기술이전","라이선스","M&A","인수합병","파이프라인","임상결과","실적","매출","pharmaceutical","biotech","licensing","pipeline"],
    "approval":    ["허가","승인","식약처","MFDS","FDA","EMA","품목허가","신약허가","approved","authorization"],
    "clinical":    ["임상","3상","2상","1상","임상시험","임상결과","phase 3","phase 2","clinical trial","randomized"],
    "policy":      ["급여","보험","건보","복지부","식약처","의료정책","수가","규제","reimbursement","healthcare policy"],
}

def categorize(title, desc=""):
    txt = (title + " " + desc).lower()
    scores = {cat: 0 for cat in CAT_KW}
    for cat, kws in CAT_KW.items():
        for kw in kws:
            if kw.lower() in txt:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

def is_important(title):
    hi = ["승인","허가","fda","phase 3","3상","신약","breakthrough","approved","급여","임상 성공","출시","판매허가"]
    return "high" if any(w in title.lower() for w in hi) else "medium"

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&nbsp;', ' ', text)
    return text.strip()

def parse_date(date_str):
    """다양한 날짜 형식 파싱 → (date_str, time_str)"""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_kst = dt.astimezone(KST)
            return dt_kst.strftime("%Y-%m-%d"), dt_kst.strftime("%H:%M")
        except:
            continue
    return yesterday, ""

# ── Google 뉴스 RSS (한국어) ───────────────────────────────
# 무료, 키 불필요, 국내 모든 언론사 커버
GOOGLE_NEWS_KO = [
    # 탈모·피부과
    ("탈모 치료 신약",          "dermatology"),
    ("탈모 임상 제약",           "dermatology"),
    ("피부과 신약",              "dermatology"),
    # 만성질환
    ("당뇨 고혈압 신약",         "chronic"),
    ("고지혈증 당뇨 치료",       "chronic"),
    ("GLP-1 비만 당뇨",          "chronic"),
    # 프로바이오틱스
    ("프로바이오틱스 장내미생물", "probiotics"),
    ("낙산균 유산균",            "probiotics"),
    ("마이크로바이옴",           "probiotics"),
    # 리팍시민
    ("리팍시민 rifaximin",       "rifaximin"),
    ("IBS 과민성장증후군 치료",   "rifaximin"),
    # 소아과 (중요!)
    ("소아과 의료 정책",          "pediatrics"),
    ("소아청소년 의료",           "pediatrics"),
    ("소아과 신약 치료",          "pediatrics"),
    ("어린이 의료 건강",          "pediatrics"),
    # 제약·승인·임상
    ("식약처 신약 허가 승인",     "approval"),
    ("임상시험 3상 결과",         "clinical"),
    ("제약사 기술이전 바이오",     "pharma"),
    ("건강보험 급여 의약품",       "policy"),
]

def fetch_google_news_rss(query, default_cat, max_items=8):
    """Google 뉴스 RSS로 한국어 기사 수집"""
    encoded = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=12)
        r.encoding = "utf-8"
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:max_items]
        results = []
        for item in items:
            title = clean_html(item.findtext("title", ""))
            link  = item.findtext("link", "")
            desc  = clean_html(item.findtext("description", ""))
            pub   = item.findtext("pubDate", "")
            src_el = item.find("source")
            source = src_el.text if src_el is not None else "Google 뉴스"

            if not title or len(title) < 5:
                continue

            date_str, time_str = parse_date(pub) if pub else (yesterday, "")

            # 어제 또는 오늘 기사만
            if date_str < yesterday:
                continue

            results.append({
                "title":   title,
                "summary": desc[:200] + "..." if len(desc) > 200 else desc,
                "url":     link,
                "source":  source,
                "date":    date_str,
                "time":    time_str,
                "cat":     categorize(title, desc) if categorize(title, desc) != "general" else default_cat,
                "imp":     is_important(title),
                "lang":    "ko",
            })
        print(f"  [구글RSS/ko] '{query}': {len(results)}건")
        return results
    except Exception as e:
        print(f"  [구글RSS/ko] '{query}' 오류: {e}")
        return []

# ── Google 뉴스 RSS (영어) ────────────────────────────────
GOOGLE_NEWS_EN = [
    ("alopecia hair loss new treatment 2026",       "dermatology"),
    ("rifaximin IBS SIBO clinical study",           "rifaximin"),
    ("probiotic microbiome gut health research",    "probiotics"),
    ("pediatric medicine children health drug",     "pediatrics"),
    ("FDA drug approval pharmaceutical 2026",       "approval"),
    ("GLP-1 diabetes obesity clinical trial",       "chronic"),
    ("Korea pharmaceutical biotech news",           "pharma"),
]

def fetch_google_news_rss_en(query, default_cat, max_items=6):
    """Google 뉴스 RSS 영어"""
    encoded = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=12)
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:max_items]
        results = []
        for item in items:
            title = clean_html(item.findtext("title", ""))
            link  = item.findtext("link", "")
            desc  = clean_html(item.findtext("description", ""))
            pub   = item.findtext("pubDate", "")
            src_el = item.find("source")
            source = (src_el.text if src_el is not None else "Google News") + " (EN)"

            if not title or len(title) < 5:
                continue

            date_str, time_str = parse_date(pub) if pub else (yesterday, "")
            if date_str < yesterday:
                continue

            results.append({
                "title":   title,
                "summary": desc[:200] + "..." if len(desc) > 200 else desc,
                "url":     link,
                "source":  source,
                "date":    date_str,
                "time":    time_str,
                "cat":     categorize(title, desc) if categorize(title, desc) != "general" else default_cat,
                "imp":     is_important(title),
                "lang":    "en",
            })
        print(f"  [구글RSS/en] '{query}': {len(results)}건")
        return results
    except Exception as e:
        print(f"  [구글RSS/en] '{query}' 오류: {e}")
        return []

# ── 수집 실행 ─────────────────────────────────────────────
all_articles = []
seen = set()

print("\n[한국어 뉴스 수집 - Google 뉴스 RSS]")
for query, cat in GOOGLE_NEWS_KO:
    items = fetch_google_news_rss(query, cat, max_items=6)
    for a in items:
        key = a["title"][:40].lower()
        if key not in seen and a["url"]:
            seen.add(key)
            all_articles.append(a)

print(f"\n[영어 뉴스 수집 - Google 뉴스 RSS]")
for query, cat in GOOGLE_NEWS_EN:
    items = fetch_google_news_rss_en(query, cat, max_items=4)
    for a in items:
        key = a["title"][:40].lower()
        if key not in seen and a["url"]:
            seen.add(key)
            all_articles.append(a)

# 정렬 (최신순), 최대 25건
all_articles.sort(key=lambda x: (x["date"], x.get("time", "")), reverse=True)
all_articles = all_articles[:25]

print(f"\n최종 수집: {len(all_articles)}건")
for a in all_articles:
    flag = "🇰🇷" if a["lang"] == "ko" else "🌐"
    print(f"  {flag} [{a['cat']}] {a['title'][:55]}")

# ── HTML 생성 ─────────────────────────────────────────────
articles_json = json.dumps(all_articles, ensure_ascii=False)

html = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#080d18">
<title>제약·의료 데일리 브리핑</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
:root{--bg:#080d18;--bg2:#0f1623;--bg3:#161e2e;--bg4:#1c2639;--border:rgba(255,255,255,0.07);--border2:rgba(255,255,255,0.13);--text:#f0f4ff;--text2:#8b93a8;--text3:#505a6e;--accent:#00c896;--adim:rgba(0,200,150,0.12);--red:#ff5c6a;--amber:#f5a623;--fn:'Noto Sans KR',sans-serif;--fs:'DM Serif Display',serif;--r:14px;--rs:8px}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{background:var(--bg);color:var(--text);font-family:var(--fn);font-size:15px;line-height:1.6;overflow-x:hidden}
.hdr{position:sticky;top:0;z-index:100;background:rgba(8,13,24,0.95);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-bottom:.5px solid var(--border);padding:13px 18px 11px}
.hdr-in{max-width:680px;margin:0 auto}
.hrow{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
.brand{display:flex;align-items:center;gap:9px}
.bico{width:33px;height:33px;background:linear-gradient(135deg,#00c896,#009e78);border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.bico svg{width:17px;height:17px}
.bname{font-size:15px;font-weight:600;letter-spacing:-.3px}
.bname em{font-style:normal;color:var(--accent)}
.updated{font-size:11px;color:var(--text3);background:var(--bg3);border:.5px solid var(--border2);border-radius:20px;padding:4px 10px;white-space:nowrap}
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
.sechead{font-size:10px;font-weight:600;letter-spacing:1.1px;color:var(--text3);text-transform:uppercase;padding:14px 0 7px}
.card{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--r);margin-bottom:8px;overflow:hidden}
.card.hi{border-left:3px solid var(--accent)}
.card.md{border-left:3px solid var(--bg4)}
.card-hd{padding:13px 15px 11px;cursor:pointer;-webkit-user-select:none;user-select:none}
.card-hd:active{background:var(--bg3)}
.ctop{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:7px;align-items:center}
.badge{font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;display:inline-flex;align-items:center}
.badge.dermatology{background:rgba(255,122,101,.14);color:#ff9a89}
.badge.clinical{background:rgba(245,166,35,.14);color:#f5c35a}
.badge.approval{background:rgba(74,158,255,.14);color:#6db3ff}
.badge.policy{background:rgba(155,127,255,.14);color:#b89fff}
.badge.pharma{background:rgba(0,200,150,.14);color:#00c896}
.badge.probiotics{background:rgba(0,200,150,.08);color:#4cd9b0;border:.5px solid rgba(0,200,150,.2)}
.badge.pediatrics{background:rgba(255,92,106,.12);color:#ff8a96}
.badge.chronic{background:rgba(245,166,35,.12);color:#e8a020}
.badge.rifaximin{background:rgba(74,158,255,.1);color:#7ab8ff;border:.5px solid rgba(74,158,255,.2)}
.badge.general{background:rgba(139,147,168,.12);color:#8b93a8}
.badge.imp{background:var(--adim);color:var(--accent)}
.badge.en{background:rgba(139,147,168,.1);color:var(--text3);font-size:9px}
.ctitle{font-size:14px;font-weight:500;line-height:1.5;color:var(--text)}
.cmeta{display:flex;align-items:center;gap:7px;margin-top:7px;flex-wrap:wrap}
.csrc{font-size:11px;color:var(--text3)}
.cdate{font-size:11px;color:var(--text3)}
/* 펼치기/접기 */
.cbody{display:none;border-top:.5px solid var(--border)}
.card.open .cbody{display:block}
.csummary{font-size:13px;color:var(--text2);line-height:1.75;padding:12px 15px 10px}
.cfooter{padding:0 15px 13px}
.clink{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--accent);text-decoration:none;background:var(--adim);padding:7px 14px;border-radius:20px;border:.5px solid rgba(0,200,150,.25)}
.clink:active{opacity:.7}
.clink svg{width:11px;height:11px;flex-shrink:0}
.ctoggle{display:flex;align-items:center;justify-content:center;gap:5px;padding:9px;cursor:pointer;border-top:.5px solid var(--border);user-select:none}
.ctoggle-txt{font-size:11px;color:var(--text3)}
.carr{font-size:12px;color:var(--text3);transition:transform .2s;display:inline-block}
.card.open .carr{transform:rotate(180deg)}
.cmsg{text-align:center;padding:50px 20px}
.ctit2{font-family:var(--fs);font-size:20px;margin-bottom:7px;color:var(--text)}
.cdesc{font-size:13px;color:var(--text3);line-height:1.8}
@media(min-width:480px){.hdr{padding-left:24px;padding-right:24px}.tabs{padding:0 24px}.cats{padding:0 24px}.awrap,.stats{padding-left:24px;padding-right:24px}}
</style>
</head>
<body>
<header class="hdr">
  <div class="hdr-in">
    <div class="hrow">
      <div class="brand">
        <div class="bico">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v2"/>
            <path d="M4 22a2 2 0 010-4h2v4"/>
            <path d="M9 9h8M9 13h8M9 17h4"/>
          </svg>
        </div>
        <div><div class="bname">제약·의료 <em>데일리</em></div></div>
      </div>
      <span class="updated" id="update-time">로딩 중...</span>
    </div>
    <div class="srow">
      <div class="dot"></div>
      <span class="stxt" id="stxt">기사 불러오는 중...</span>
    </div>
  </div>
</header>
<div class="tabbar"><div class="tabs" id="tabs"></div></div>
<div class="cwrap">
  <div class="cats">
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
  </div>
</div>
<div class="stats">
  <div class="sc"><div class="sn" id="st">0</div><div class="sl">전체 기사</div></div>
  <div class="sc"><div class="sn" id="sh">0</div><div class="sl">주요 기사</div></div>
  <div class="sc"><div class="sn" id="ss">0</div><div class="sl">카테고리</div></div>
</div>
<div class="awrap"><div id="alist"></div></div>
<script>
const CATS_LBL={dermatology:'탈모·피부과',clinical:'임상시험',approval:'신약 승인',policy:'정책·규제',pharma:'제약사 동향',probiotics:'프로바이오틱스',pediatrics:'소아과',chronic:'만성질환',rifaximin:'Rifaximin',general:'일반'};
""" + f"const ARTICLES={articles_json};\n" + f"const UPDATE_TIME='{update_str}';\n" + """
let curCat='all', curDate='all';

function tog(el){
  el.closest('.card').classList.toggle('open');
}

function cardHTML(a, idx){
  const cl=CATS_LBL[a.cat]||'일반';
  const impBadge=a.imp==='high'?'<span class="badge imp">★ 주요</span>':'';
  const enBadge=a.lang==='en'?'<span class="badge en">EN</span>':'';
  const ds=a.time ? a.date.replace(/-/g,'.')+' '+a.time : a.date.replace(/-/g,'.');
  const summary=a.summary
    ? '<div class="csummary">'+a.summary+'</div>'
    : '<div class="csummary" style="color:var(--text3);font-style:italic">요약 없음 — 원문을 확인해주세요.</div>';
  return '<div class="card '+(a.imp==='high'?'hi':'md')+'" id="card'+idx+'">'
    +'<div class="card-hd" onclick="tog(this)">'
    +'<div class="ctop"><span class="badge '+a.cat+'">'+cl+'</span>'+impBadge+enBadge+'</div>'
    +'<div class="ctitle">'+a.title+'</div>'
    +'<div class="cmeta"><span class="csrc">'+a.source+'</span><span style="color:var(--bg4)">·</span><span class="cdate">'+ds+'</span></div>'
    +'</div>'
    +'<div class="cbody">'
    +summary
    +'<div class="cfooter">'
    +'<a class="clink" href="'+a.url+'" target="_blank" rel="noopener">'
    +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'
    +'원문 기사 보기 ('+a.source+')'
    +'</a></div>'
    +'</div>'
    +'<div class="ctoggle" onclick="tog(this)">'
    +'<span class="ctoggle-txt">요약 · 원문 링크</span>'
    +'<span class="carr">∨</span>'
    +'</div>'
    +'</div>';
}

function buildTabs(){
  const dates=[...new Set(ARTICLES.map(a=>a.date))].sort().reverse();
  const tabs=document.getElementById('tabs');
  let html='<button class="tab '+(curDate==='all'?'on':'')+'" onclick="selDate(\'all\',this)">전체 <span style="font-size:10px;opacity:.6">'+ARTICLES.length+'</span></button>';
  dates.forEach(function(d){
    const cnt=ARTICLES.filter(function(a){return a.date===d;}).length;
    const dd=new Date(d+'T00:00:00+09:00');
    const today=new Date(); today.setHours(0,0,0,0);
    const diff=Math.round((today-dd)/86400000);
    const lbl=diff===0?'오늘':diff===1?'어제':diff<=7?diff+'일 전':dd.toLocaleDateString('ko-KR',{month:'short',day:'numeric'});
    html+='<button class="tab '+(curDate===d?'on':'')+'" onclick="selDate(\''+d+'\',this)">'+lbl+' <span style="font-size:10px;opacity:.6">'+cnt+'</span></button>';
  });
  tabs.innerHTML=html;
}

function selDate(d,btn){curDate=d;document.querySelectorAll('.tab').forEach(function(b){b.classList.remove('on');});btn.classList.add('on');render();}
function fCat(cat,btn){curCat=cat;document.querySelectorAll('.cat').forEach(function(b){b.classList.remove('on');});btn.classList.add('on');render();}

function render(){
  var list=ARTICLES;
  if(curDate!=='all') list=list.filter(function(a){return a.date===curDate;});
  if(curCat!=='all')  list=list.filter(function(a){return a.cat===curCat;});
  document.getElementById('st').textContent=ARTICLES.length;
  document.getElementById('sh').textContent=ARTICLES.filter(function(a){return a.imp==='high';}).length;
  document.getElementById('ss').textContent=[...new Set(ARTICLES.map(function(a){return a.cat;}))].length;
  document.getElementById('stxt').textContent=ARTICLES.length+'건 · 매일 오전 6시 자동 업데이트';
  document.getElementById('update-time').textContent='⚡ '+UPDATE_TIME+' 업데이트';
  var el=document.getElementById('alist');
  if(!list.length){el.innerHTML='<div class="cmsg"><div class="ctit2">해당 조건의 기사 없음</div><div class="cdesc">날짜나 카테고리를 바꿔보세요.</div></div>';return;}
  var groups={};
  list.forEach(function(a){if(!groups[a.date])groups[a.date]=[];groups[a.date].push(a);});
  var sortedDates=Object.keys(groups).sort().reverse();
  var html='';
  sortedDates.forEach(function(date){
    var dd=new Date(date+'T00:00:00+09:00');
    var today=new Date(); today.setHours(0,0,0,0);
    var diff=Math.round((today-dd)/86400000);
    var lbl=diff===0?'오늘':diff===1?'어제':diff<=7?diff+'일 전':dd.toLocaleDateString('ko-KR',{year:'numeric',month:'long',day:'numeric'});
    html+='<div class="sechead">'+lbl+' · '+groups[date].length+'건</div>';
    html+=groups[date].map(function(a,i){return cardHTML(a,date+i);}).join('');
  });
  el.innerHTML=html;
}

buildTabs(); render();
</script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nindex.html 생성 완료! ({len(all_articles)}건)")
