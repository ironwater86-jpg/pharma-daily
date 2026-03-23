import os, json, requests
from datetime import datetime, timedelta, timezone

API_KEY = os.environ.get("NEWS_API_KEY", "")
KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST)
yesterday = (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")
today_str = now_kst.strftime("%Y년 %m월 %d일")
update_str = now_kst.strftime("%Y.%m.%d %H:%M")

# 검색 키워드 → 카테고리 매핑
QUERIES = [
    ("탈모 치료 신약",        "dermatology"),
    ("피부과 의료",           "dermatology"),
    ("당뇨 고혈압 고지혈증",   "chronic"),
    ("만성질환 신약",          "chronic"),
    ("프로바이오틱스 장내미생물", "probiotics"),
    ("낙산균 유산균",          "probiotics"),
    ("rifaximin",             "rifaximin"),
    ("소아과 소아청소년",       "pediatrics"),
    ("제약사 신약 임상",        "pharma"),
    ("식약처 FDA 허가 승인",    "approval"),
]

CAT_KW = {
    "dermatology": ["탈모","피부","두피","헤어","모발","alopecia","hair loss","dermatol","finasteride","minoxidil"],
    "chronic":     ["당뇨","고혈압","고지혈증","비만","심혈관","만성","diabetes","hypertension","cholesterol","cardiovascular","GLP-1","SGLT"],
    "probiotics":  ["프로바이오틱스","유산균","장내미생물","낙산균","효모균","microbiome","probiotics","gut","butyrate","lactobacil"],
    "rifaximin":   ["rifaximin","리팍시민","SIBO","IBS","간성뇌증","hepatic encephalopathy"],
    "pediatrics":  ["소아","어린이","아동","신생아","영아","pediatric","children","infant","소아과","소아청소년"],
    "pharma":      ["제약","인수","합병","기술이전","라이선스","파이프라인","매출","실적","pharma","acquisition","merger","licensing"],
    "approval":    ["승인","허가","식약처","FDA","EMA","MFDS","approved","authorized","cleared","품목허가"],
    "clinical":    ["임상","3상","2상","1상","clinical trial","phase","임상시험"],
    "policy":      ["정책","규제","보험","급여","복지부","건보","보건부","guideline","regulation","reimbursement"],
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

def fetch_query(query, cat):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": yesterday,
        "sortBy": "publishedAt",
        "language": "ko",
        "pageSize": 10,
        "apiKey": API_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        articles = []
        for item in data.get("articles", []):
            if not item.get("title") or "[Removed]" in item.get("title",""):
                continue
            pub = item.get("publishedAt","")
            try:
                dt = datetime.fromisoformat(pub.replace("Z","+00:00")).astimezone(KST)
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M")
            except:
                date_str = yesterday
                time_str = ""
            title = item.get("title","").split(" - ")[0].strip()
            articles.append({
                "title": title,
                "summary": item.get("description") or "",
                "url": item.get("url",""),
                "source": item.get("source",{}).get("name",""),
                "date": date_str,
                "time": time_str,
                "cat": categorize(title, item.get("description","")),
                "imp": "high" if any(w in title.lower() for w in ["승인","허가","fda","급여","임상 3상","신약","major","approved","breakthrough"]) else "medium",
            })
        return articles
    except Exception as e:
        print(f"Error fetching '{query}': {e}")
        return []

# 영어 검색도 추가
EN_QUERIES = [
    ("rifaximin microbiome 2025 2026", "rifaximin"),
    ("probiotics gut health clinical 2025 2026", "probiotics"),
    ("pediatrics children medicine Korea 2025 2026", "pediatrics"),
    ("diabetes hypertension new drug approved 2025 2026", "chronic"),
    ("alopecia hair loss treatment clinical trial 2025 2026", "dermatology"),
]

def fetch_en(query, cat):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": yesterday,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 5,
        "apiKey": API_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        articles = []
        for item in data.get("articles", []):
            if not item.get("title") or "[Removed]" in item.get("title",""):
                continue
            pub = item.get("publishedAt","")
            try:
                dt = datetime.fromisoformat(pub.replace("Z","+00:00")).astimezone(KST)
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M")
            except:
                date_str = yesterday
                time_str = ""
            title = item.get("title","").split(" - ")[0].strip()
            articles.append({
                "title": title,
                "summary": item.get("description") or "",
                "url": item.get("url",""),
                "source": item.get("source",{}).get("name","") + " (EN)",
                "date": date_str,
                "time": time_str,
                "cat": categorize(title, item.get("description","")),
                "imp": "high" if any(w in title.lower() for w in ["approved","fda","breakthrough","major","phase 3"]) else "medium",
                "lang": "en",
            })
        return articles
    except Exception as e:
        print(f"Error fetching EN '{query}': {e}")
        return []

# 수집
all_articles = []
seen_titles = set()

for query, cat in QUERIES:
    items = fetch_query(query, cat)
    for a in items:
        key = a["title"][:40]
        if key not in seen_titles:
            seen_titles.add(key)
            all_articles.append(a)

for query, cat in EN_QUERIES:
    items = fetch_en(query, cat)
    for a in items:
        key = a["title"][:40]
        if key not in seen_titles:
            seen_titles.add(key)
            all_articles.append(a)

# 날짜순 정렬 (최신 먼저), 최대 30건
all_articles.sort(key=lambda x: (x["date"], x.get("time","")), reverse=True)
all_articles = all_articles[:30]

print(f"수집된 기사: {len(all_articles)}건")

# HTML 생성
articles_json = json.dumps(all_articles, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#080d18">
<title>제약·의료 데일리 브리핑</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#080d18;--bg2:#0f1623;--bg3:#161e2e;--bg4:#1c2639;
  --border:rgba(255,255,255,0.07);--border2:rgba(255,255,255,0.13);
  --text:#f0f4ff;--text2:#8b93a8;--text3:#505a6e;
  --accent:#00c896;--adim:rgba(0,200,150,0.12);
  --red:#ff5c6a;--amber:#f5a623;
  --fn:'Noto Sans KR',sans-serif;--fs:'DM Serif Display',serif;
  --r:14px;--rs:8px;
}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
html,body{{background:var(--bg);color:var(--text);font-family:var(--fn);font-size:15px;line-height:1.6;overflow-x:hidden}}
.hdr{{position:sticky;top:0;z-index:100;background:rgba(8,13,24,0.95);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-bottom:.5px solid var(--border);padding:13px 18px 11px}}
.hdr-in{{max-width:680px;margin:0 auto}}
.hrow{{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}}
.brand{{display:flex;align-items:center;gap:9px}}
.bico{{width:33px;height:33px;background:linear-gradient(135deg,#00c896,#009e78);border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.bico svg{{width:17px;height:17px}}
.bname{{font-size:15px;font-weight:600;letter-spacing:-.3px}}
.bname em{{font-style:normal;color:var(--accent)}}
.updated{{font-size:11px;color:var(--text3);background:var(--bg3);border:.5px solid var(--border2);border-radius:20px;padding:4px 10px;white-space:nowrap}}
.srow{{display:flex;align-items:center;gap:6px}}
.dot{{width:5px;height:5px;border-radius:50%;background:var(--accent);box-shadow:0 0 5px var(--accent);flex-shrink:0}}
.stxt{{font-size:11.5px;color:var(--text3)}}
.tabbar{{background:var(--bg2);border-bottom:.5px solid var(--border);overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}}
.tabbar::-webkit-scrollbar{{display:none}}
.tabs{{display:flex;padding:0 18px;width:max-content}}
.tab{{font-size:12.5px;font-family:var(--fn);font-weight:500;padding:10px 14px;border-bottom:2px solid transparent;color:var(--text3);cursor:pointer;white-space:nowrap;transition:.15s;user-select:none}}
.tab.on{{color:var(--accent);border-bottom-color:var(--accent)}}
.cwrap{{padding:10px 0;border-bottom:.5px solid var(--border);overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}}
.cwrap::-webkit-scrollbar{{display:none}}
.cats{{display:flex;gap:6px;padding:0 18px;width:max-content}}
.cat{{font-size:12px;font-family:var(--fn);font-weight:500;padding:4px 12px;border-radius:20px;border:.5px solid var(--border2);background:transparent;color:var(--text2);cursor:pointer;white-space:nowrap;transition:.15s;user-select:none}}
.cat:active{{transform:scale(.95)}}
.cat.on{{background:var(--adim);border-color:var(--accent);color:var(--accent)}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px 18px;max-width:680px;margin:0 auto}}
.sc{{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--rs);padding:9px 12px;text-align:center}}
.sn{{font-size:20px;font-weight:700;font-family:var(--fs);color:var(--accent);line-height:1.1;margin-bottom:2px}}
.sl{{font-size:10px;color:var(--text3);letter-spacing:.3px}}
.awrap{{padding:0 18px 80px;max-width:680px;margin:0 auto}}
.sechead{{font-size:10px;font-weight:600;letter-spacing:1.1px;color:var(--text3);text-transform:uppercase;padding:14px 0 7px}}
.card{{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--r);margin-bottom:8px;overflow:hidden}}
.card.hi{{border-left:3px solid var(--accent)}}
.card.md{{border-left:3px solid var(--bg4)}}
.card-hd{{padding:13px 15px 11px;cursor:pointer;-webkit-user-select:none;user-select:none}}
.card-hd:active{{background:var(--bg3)}}
.ctop{{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:7px;align-items:center}}
.badge{{font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;display:inline-flex;align-items:center}}
.badge.dermatology{{background:rgba(255,122,101,.14);color:#ff9a89}}
.badge.clinical{{background:rgba(245,166,35,.14);color:#f5c35a}}
.badge.approval{{background:rgba(74,158,255,.14);color:#6db3ff}}
.badge.policy{{background:rgba(155,127,255,.14);color:#b89fff}}
.badge.pharma{{background:rgba(0,200,150,.14);color:#00c896}}
.badge.probiotics{{background:rgba(0,200,150,.08);color:#4cd9b0;border:.5px solid rgba(0,200,150,.2)}}
.badge.pediatrics{{background:rgba(255,92,106,.12);color:#ff8a96}}
.badge.chronic{{background:rgba(245,166,35,.12);color:#e8a020}}
.badge.rifaximin{{background:rgba(74,158,255,.1);color:#7ab8ff;border:.5px solid rgba(74,158,255,.2)}}
.badge.general{{background:rgba(139,147,168,.12);color:#8b93a8}}
.badge.new-tag{{background:var(--adim);color:var(--accent)}}
.badge.en-tag{{background:rgba(139,147,168,.1);color:var(--text3);font-size:9px}}
.ctitle{{font-size:14px;font-weight:500;line-height:1.5;color:var(--text)}}
.cmeta{{display:flex;align-items:center;gap:7px;margin-top:7px;flex-wrap:wrap}}
.csrc{{font-size:11px;color:var(--text3)}}
.cdate{{font-size:11px;color:var(--text3)}}
.cbody{{display:none;border-top:.5px solid var(--border)}}
.card.open .cbody{{display:block}}
.csummary{{font-size:13px;color:var(--text2);line-height:1.75;padding:12px 15px 10px}}
.cfooter{{padding:0 15px 12px}}
.clink{{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--accent);text-decoration:none;background:var(--adim);padding:6px 13px;border-radius:20px;border:.5px solid rgba(0,200,150,.25)}}
.clink:active{{opacity:.7}}
.clink svg{{width:11px;height:11px;flex-shrink:0}}
.ctoggle{{display:flex;align-items:center;justify-content:center;padding:7px;cursor:pointer;border-top:.5px solid var(--border)}}
.ctoggle span{{font-size:11px;color:var(--text3);user-select:none}}
.carr{{display:inline-block;margin-left:3px;transition:transform .18s}}
.card.open .carr{{transform:rotate(180deg)}}
.cmsg{{text-align:center;padding:50px 20px}}
.ctit2{{font-family:var(--fs);font-size:20px;margin-bottom:7px;color:var(--text)}}
.cdesc{{font-size:13px;color:var(--text3);line-height:1.8}}
.empty-box{{background:var(--bg2);border:.5px solid var(--border);border-radius:var(--r);padding:20px;text-align:center;margin-top:8px}}
.empty-box p{{font-size:13px;color:var(--text3);line-height:1.8}}
@media(min-width:480px){{
  .hdr{{padding-left:24px;padding-right:24px}}
  .tabs{{padding:0 24px}}
  .cats{{padding:0 24px}}
  .awrap,.stats{{padding-left:24px;padding-right:24px}}
}}
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
      <span class="updated">⚡ {update_str} 자동업데이트</span>
    </div>
    <div class="srow">
      <div class="dot"></div>
      <span class="stxt" id="stxt">기사 로딩 중...</span>
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
const ARTICLES = {articles_json};
const CATS_LBL = {{dermatology:'탈모·피부과',clinical:'임상시험',approval:'신약 승인',policy:'정책·규제',pharma:'제약사 동향',probiotics:'프로바이오틱스',pediatrics:'소아과',chronic:'만성질환',rifaximin:'Rifaximin',general:'일반'}};
let curCat='all', curDate='all';
function tog(id){{ const el=document.getElementById('c'+id); if(el) el.classList.toggle('open'); }}
function cardHTML(a,idx){{
  const cl=CATS_LBL[a.cat]||'일반';
  const newTag=a.imp==='high'?'<span class="badge new-tag">★ 주요</span>':'';
  const enTag=a.lang==='en'?'<span class="badge en-tag">EN</span>':'';
  const summary=a.summary?`<div class="csummary">${{a.summary}}</div>`:'<div class="csummary" style="color:var(--text3);font-style:italic">요약 없음 — 원문을 확인해주세요.</div>';
  const ds=a.time?a.date.replace(/-/g,'.')+' '+a.time:a.date.replace(/-/g,'.');
  return `<div class="card ${{a.imp==='high'?'hi':'md'}}" id="c${{idx}}">
    <div class="card-hd" onclick="tog(${{idx}})">
      <div class="ctop"><span class="badge ${{a.cat}}">${{cl}}</span>${{newTag}}${{enTag}}</div>
      <div class="ctitle">${{a.title}}</div>
      <div class="cmeta"><span class="csrc">${{a.source}}</span><span style="color:var(--bg4)">·</span><span class="cdate">${{ds}}</span></div>
    </div>
    <div class="cbody">
      ${{summary}}
      <div class="cfooter">
        <a class="clink" href="${{a.url}}" target="_blank" rel="noopener">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          원문 기사 보기 (${{a.source}})
        </a>
      </div>
    </div>
    <div class="ctoggle" onclick="tog(${{idx}})"><span>요약 · 원문 링크 <span class="carr">∨</span></span></div>
  </div>`;
}}
function buildTabs(){{
  const dates=[...new Set(ARTICLES.map(a=>a.date))].sort().reverse();
  const tabs=document.getElementById('tabs');
  const allCnt=ARTICLES.length;
  let html=`<button class="tab ${{curDate==='all'?'on':''}}" onclick="selDate('all',this)">전체 <span style="font-size:10px;opacity:.6">${{allCnt}}</span></button>`;
  dates.forEach(d=>{{
    const cnt=ARTICLES.filter(a=>a.date===d).length;
    const dd=new Date(d+'T00:00:00+09:00');
    const today=new Date(); today.setHours(0,0,0,0);
    const diff=Math.round((today-dd)/86400000);
    const lbl=diff===0?'오늘':diff===1?'어제':dd.toLocaleDateString('ko-KR',{{month:'short',day:'numeric'}});
    html+=`<button class="tab ${{curDate===d?'on':''}}" onclick="selDate('${{d}}',this)">${{lbl}} <span style="font-size:10px;opacity:.6">${{cnt}}</span></button>`;
  }});
  tabs.innerHTML=html;
}}
function selDate(d,btn){{ curDate=d; document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on')); btn.classList.add('on'); render(); }}
function fCat(cat,btn){{ curCat=cat; document.querySelectorAll('.cat').forEach(b=>b.classList.remove('on')); btn.classList.add('on'); render(); }}
function render(){{
  let list=ARTICLES;
  if(curDate!=='all') list=list.filter(a=>a.date===curDate);
  if(curCat!=='all')  list=list.filter(a=>a.cat===curCat);
  document.getElementById('st').textContent=ARTICLES.length;
  document.getElementById('sh').textContent=ARTICLES.filter(a=>a.imp==='high').length;
  document.getElementById('ss').textContent=[...new Set(ARTICLES.map(a=>a.cat))].length;
  document.getElementById('stxt').textContent=ARTICLES.length+'건 · 매일 오전 6시 자동 업데이트';
  const el=document.getElementById('alist');
  if(!list.length){{ el.innerHTML=`<div class="cmsg"><div class="ctit2">해당 조건의 기사 없음</div><div class="cdesc">날짜나 카테고리를 바꿔보세요.</div></div>`; return; }}
  const groups={{}};
  list.forEach(a=>{{ (groups[a.date]=groups[a.date]||[]).push(a); }});
  const sortedDates=Object.keys(groups).sort().reverse();
  let html='';
  sortedDates.forEach(date=>{{
    const dd=new Date(date+'T00:00:00+09:00');
    const today=new Date(); today.setHours(0,0,0,0);
    const diff=Math.round((today-dd)/86400000);
    const lbl=diff===0?'오늘':diff===1?'어제':diff<=7?diff+'일 전':dd.toLocaleDateString('ko-KR',{{year:'numeric',month:'long',day:'numeric'}});
    html+=`<div class="sechead">${{lbl}} · ${{groups[date].length}}건</div>`;
    html+=groups[date].map((a,i)=>cardHTML(a,date+i)).join('');
  }});
  if(!html) html=`<div class="empty-box"><p>오늘 수집된 기사가 없습니다.<br>내일 오전 6시에 자동으로 업데이트됩니다.</p></div>`;
  el.innerHTML=html;
}}
buildTabs(); render();
</script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("index.html 생성 완료!")
