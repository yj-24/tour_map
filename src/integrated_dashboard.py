import streamlit as st
import pandas as pd
import json
import requests
import os
import unicodedata
import base64
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs
import streamlit.components.v1 as components
import re

# --- 1. Page Configuration & Env ---
st.set_page_config(page_title="Integrated K-Beauty Tour Dashboard", layout="wide", initial_sidebar_state="expanded")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOUR_DATA_DIR = os.path.join(BASE_DIR, 'data')
TOUR_IMG_DIR = os.path.join(BASE_DIR, 'images')

KAKAO_JS_API_KEY = st.secrets.get("KAKAO_JS_API_KEY", os.getenv("KAKAO_JS_API_KEY", ""))
SEOUL_CITY_DATA_API_KEY = st.secrets.get("SEOUL_CITY_DATA_API_KEY", os.getenv("SEOUL_CITY_DATA_API_KEY", ""))

if not KAKAO_JS_API_KEY:
    st.error("🔑 KAKAO_JS_API_KEY is missing! Please add it to your Streamlit Secrets.")

# --- 2. Styling (Unified) ---
def inject_custom_css():
    st.markdown("""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        
        html, body, [class*="css"] {
            font-family: 'Pretendard', -apple-system, sans-serif !important;
            background-color: #F8F9FD !important;
            color: #2D3436 !important;
        }
        [data-testid="stAppViewContainer"] { background-color: transparent !important; }
        .block-container { padding: 1.5rem 2.5rem !important; }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.6);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.4);
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.05);
            margin-bottom: 20px;
        }
        
        /* Product Card */
        .best-label { background: linear-gradient(135deg, #F93780 0%, #FF6B6B 100%); color: white; padding: 4px 12px; border-radius: 30px; font-weight: 700; font-size: 0.8rem; display: inline-block; margin-bottom: 10px; }
        .product-card { background: white; border-radius: 15px; padding: 12px; text-align: center; border: 1px solid #EEF1F6; transition: all 0.3s ease; height: 100%; display: flex; flex-direction: column; justify-content: space-between; max-width: 160px; margin: 0 auto; }
        .product-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.05); border-color: #F9378022; }
        .product-img { width: 100%; height: 110px; object-fit: contain; border-radius: 10px; margin-bottom: 10px; background-color: #f9f9f9; }
        .product-title { font-size: 0.8rem; font-weight: 600; color: #333; height: 2.8em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.4; }
        .product-price { font-size: 0.9rem; color: #F93780; font-weight: 700; margin-top: 5px; }

        /* Rankings Table */
        .ranking-row { display: flex; align-items: center; padding: 12px 15px; background: white; border-radius: 12px; margin-bottom: 8px; border: 1px solid #EEF1F6; }
        .rank-num { width: 30px; font-weight: 800; color: #F93780; font-size: 1.1rem; }

        /* Custom Tabs Styling */
        .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: transparent; }
        .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; border-radius: 10px 10px 0 0; font-weight: 700; padding: 15px; border: 1px solid rgba(255, 255, 255, 0.3); box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        
        /* Quiz specific */
        .quiz-card { background: #ffffff; border-radius: 20px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .quiz-title { font-size: 1.3em; font-weight: 800; margin-bottom: 20px; color: #1e272e; }
        .persona-result { background: linear-gradient(135deg, #FF9A9E 0%, #FECFEF 99%, #FECFEF 100%); border-radius: 20px; padding: 40px; color: #000; text-align: center; box-shadow: 0 10px 20px rgba(255, 154, 158, 0.3); margin-top: 20px; }

        /* Streamlit Focus Buttons */
        div.stButton > button { width: 100%; text-align: left; background: transparent; border: none; padding: 2px 0px; font-size: 0.7rem !important; height: auto; min-height: 0; line-height: 1.2; }
        div.stButton > button:hover { color: #6C5CE7; background: rgba(0,0,0,0.02); }
        </style>
    """, unsafe_allow_html=True)


# --- 3. Data Utilities ---
def safe_read_csv(path, **kwargs):
    for enc in ['utf-8-sig', 'utf-8', 'cp949']:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except: continue
    return pd.DataFrame()

@st.cache_data
def load_data(filename):
    path = os.path.join(TOUR_DATA_DIR, filename)
    return safe_read_csv(path)

# Image Utils
def get_base64_img(path):
    if not path or not os.path.exists(path): return None
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def get_oy_image_url(product_url):
    if not isinstance(product_url, str): return None
    parsed_url = urlparse(product_url)
    params = parse_qs(parsed_url.query)
    goods_no = params.get('goodsNo', [None])[0]
    if not goods_no:
        match = re.search(r'goodsNo=([A-Z0-9]+)', product_url)
        if match: goods_no = match.group(1)
    if goods_no:
        return f"https://image.oliveyoung.co.kr/uploads/images/goods/10/0000/00{goods_no[7:9]}/{goods_no}.jpg"
    return None

def find_image_path(product_name, brand):
    folder = 'oliveyoung_best' if brand == 'oliveyoung' else 'daiso_beauty_best'
    target_dir = os.path.join(TOUR_IMG_DIR, folder)
    if not os.path.exists(target_dir): return None
    name_norm = unicodedata.normalize('NFC', str(product_name).strip()).replace(' ', '')
    for f in os.listdir(target_dir):
        if name_norm in unicodedata.normalize('NFC', f).replace(' ', ''):
            return os.path.join(target_dir, f)
    return None

@st.cache_data(ttl=600)
def get_seoul_city_data(location_id):
    if not location_id or not SEOUL_CITY_DATA_API_KEY: return {"lvl": "정보없음", "color": "#B2BEC3", "msg":""}
    url = f"http://openapi.seoul.go.kr:8088/{SEOUL_CITY_DATA_API_KEY}/xml/citydata/1/5/{str(location_id).strip()}"
    try:
        res = requests.get(url)
        root = ET.fromstring(res.content)
        stts = root.find(".//LIVE_PPLTN_STTS/LIVE_PPLTN_STTS")
        if stts is not None:
            lvl = stts.findtext("AREA_CONGEST_LVL")
            msg = stts.findtext("AREA_CONGEST_MSG")
            colors = {"여유": "#00B894", "보통": "#6C5CE7", "약간 붐빔": "#E17055", "붐빔": "#D63031"}
            return {"lvl": lvl, "color": colors.get(lvl, "#B2BEC3"), "msg": msg}
    except: pass
    return {"lvl": "정보없음", "color": "#B2BEC3", "msg": ""}


# --- 4. Globals for Persona ---
PERSONA_INFO = {
    '중국': ('효능 중심 프리미엄 케어파 (Efficacy-Focused Premium Care) 👑', '한국 클리닉의 리프팅 효과를 그대로, 집에서 완성하는 고밀도 광채.'),
    '일본': ('저자극 장벽 케어파 (Low-Irritant Barrier Care) 🌿', '자극 없이 맑게 차오르는 수분감, 내일이 더 기대되는 투명한 결 케어.'),
    '대만': ('모공·쿨링 밸런스파 (Pore & Cooling Balance) 🧊', '피부 온도는 낮추고 모공은 촘촘하게, 번들거림 없는 클리어 스킨.'),
    '미국': ('즉각적 광채 추구미 (Immediate Glow-Chasing) ✨', '성분으로 증명하고 결과를 빨리 보는 가장 완벽한 인스턴트 글로우 루틴.'),
    '홍콩': ('멀티태스킹 케어파 (Multitasking Care) ⚡', '단 하나로 장벽/톤업/자외선 차단을 마스터하는 극강의 효율.')
}

SEOUL_DISTRICTS = [
    "전체 (All)", "강남구 (Gangnam-gu)", "강동구 (Gangdong-gu)", "강북구 (Gangbuk-gu)", "강서구 (Gangseo-gu)",
    "관악구 (Gwanak-gu)", "광진구 (Gwangjin-gu)", "구로구 (Guro-gu)", "금천구 (Geumcheon-gu)",
    "노원구 (Nowon-gu)", "도봉구 (Dobong-gu)", "동대문구 (Dongdaemun-gu)", "동작구 (Dongjak-gu)",
    "마포구 (Mapo-gu)", "서대문구 (Seodaemun-gu)", "서초구 (Seocho-gu)", "성동구 (Seongdong-gu)",
    "성북구 (Seongbuk-gu)", "송파구 (Songpa-gu)", "양천구 (Yangcheon-gu)", "영등포구 (Yeongdeungpo-gu)",
    "용산구 (Yongsan-gu)", "은평구 (Eunpyeong-gu)", "종로구 (Jongno-gu)", "중구 (Jung-gu)", "중랑구 (Jungnang-gu)"
]


# --- 5. Map Renderers ---
# A) Persona Map Renderer (with left List view)
def render_kakao_map_persona(locations, height=650, level=8, center_lat=37.5665, center_lng=126.9780):
    if not locations: return st.warning("지도에 표시할 추천 장소가 없습니다.")

    markers_js, list_items_html = "", ""
    valid_locs = [l for l in locations if l['lat'] and l['lng']]
        
    for i, loc in enumerate(valid_locs):
        cong_lvl = loc.get('congestion_lvl', '정보없음')
        s_name = str(loc['name']).replace("'", "`")
        s_category = str(loc.get('category', '')).replace("'", "`")
        s_district = str(loc.get('district', '')).replace("'", "`")
        
        markers_js += f"{{ title: '{s_name}', latlng: new kakao.maps.LatLng({loc['lat']}, {loc['lng']}), category: '{s_category}', district: '{s_district}', congestion: '{cong_lvl}' }},"
        
        cong_colors = {"여유": "#2ecc71", "보통": "#f1c40f", "약간 붐빔": "#e67e22", "붐빔": "#e74c3c", "정보없음": "#95a5a6"}
        badge_color = cong_colors.get(cong_lvl, "#95a5a6")
        
        list_items_html += f"""
            <div class="list-item" onclick="focusMarker({i})" id="item-{i}" style="padding: 12px 15px; border-bottom: 1px solid #eee; cursor:pointer;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 14px; font-weight: 600;">{loc['name']}</div>
                    <span style="font-size: 10px; padding: 2px 6px; background: {badge_color}; color: white; border-radius: 10px;">{cong_lvl}</span>
                </div>
                <div style="font-size: 12px; color: #888; margin-top: 4px;">[{loc.get('district', '')}] {loc.get('category', '')}</div>
            </div>"""

    html_code = f"""
    <head><meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests"></head>
    <div style="display: flex; width: 100%; height: {height}px; font-family: 'Pretendard', sans-serif; border: 1px solid #ddd; border-radius: 12px; overflow: hidden; background: #fff;">
        <div style="width: 300px; height: 100%; overflow-y: auto; background: #fff; border-right: 1px solid #ddd;">
            {list_items_html}
        </div>
        <div id="map" style="flex: 1; height: 100%;"></div>
    </div>
    
    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_API_KEY}&autoload=false"></script>
    <script>
        var map, markers = [], infowindows = [];
        var ICON_URLS = {{ '여유': 'http://maps.google.com/mapfiles/ms/icons/green-dot.png', '보통': 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png', '약간 붐빔': 'http://maps.google.com/mapfiles/ms/icons/orange-dot.png', '붐빔': 'http://maps.google.com/mapfiles/ms/icons/red-dot.png', '정보없음': 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png' }};

        function initMap() {{
            var mapContainer = document.getElementById('map');
            var mapOption = {{ center: new kakao.maps.LatLng({center_lat}, {center_lng}), level: {level} }};
            map = new kakao.maps.Map(mapContainer, mapOption); 
            var positions = [{markers_js}];

            var bounds = new kakao.maps.LatLngBounds();
            for (var i = 0; i < positions.length; i++) {{
                var marker = new kakao.maps.Marker({{ map: map, position: positions[i].latlng, title: positions[i].title, image: new kakao.maps.MarkerImage(ICON_URLS[positions[i].congestion] || ICON_URLS['정보없음'], new kakao.maps.Size(32, 32)) }});
                var content = '<div style="padding:10px;min-width:180px;font-size:12px;border:none;"><b>' + positions[i].title + '</b><br><span style="color:#e74c3c;">혼잡도: ' + positions[i].congestion + '</span></div>';
                var infowindow = new kakao.maps.InfoWindow({{ content: content }});
                markers.push(marker); infowindows.push(infowindow);
                bounds.extend(positions[i].latlng);
                
                (function(m, info, idx) {{
                    kakao.maps.event.addListener(m, 'click', function() {{ focusMarker(idx); }});
                    kakao.maps.event.addListener(m, 'mouseover', function() {{ info.open(map, m); }});
                    kakao.maps.event.addListener(m, 'mouseout', function() {{ info.close(); }});
                }})(marker, infowindow, i);
            }}
            if(positions.length > 0) {{ map.setBounds(bounds); }}
        }}

        function focusMarker(idx) {{
            for (var i = 0; i < markers.length; i++) {{ infowindows[i].close(); document.getElementById('item-'+i).style.background = '#fff'; }}
            infowindows[idx].open(map, markers[idx]);
            map.setCenter(markers[idx].getPosition());
            map.setLevel(4);
            document.getElementById('item-'+idx).style.background = '#e7f5ff';
            document.getElementById('item-'+idx).scrollIntoView({{behavior:'smooth', block:'nearest'}});
        }}

        if (typeof kakao !== 'undefined') kakao.maps.load(initMap);
    </script>
    """
    components.html(html_code, height=height + 20)

# B) Unified Map Renderer (General Tourist Map)
def render_map_unified(locations, stores=None, center=(37.5665, 126.9780), zoom=7, height=450):
    if not KAKAO_JS_API_KEY: return
    markers = []
    for loc in locations:
        try:
            lat, lng = float(loc['lat']), float(loc['lng'])
            if not pd.isna(lat) and not pd.isna(lng):
                markers.append({'lat': lat, 'lng': lng, 'title': f"{loc['name']} {f'[{loc.get('lvl', '정보없음')}]' if 'lvl' in loc else ''}", 'type': 'tour'})
        except: continue

    if stores:
        for s in stores:
            try:
                lat, lng = float(s['위도']), float(s['경도'])
                if not pd.isna(lat) and not pd.isna(lng):
                    markers.append({'lat': lat, 'lng': lng, 'title': s['매장명'], 'type': str(s['메이커명']).lower()})
            except: continue

    positions_json = json.dumps(markers, ensure_ascii=False)

    html = f"""
    <head><meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests"></head>
    <div id="map" style="width: 100%; height: {height}px; border-radius: 15px; border: 1px solid #ddd;"></div>
    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_API_KEY}&autoload=false"></script>
    <script>
        (function() {{
            const POSITIONS = {positions_json};
            const icons = {{
                tour: 'https://maps.google.com/mapfiles/ms/icons/green-dot.png',
                oliveyoung: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
                daiso: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'
            }};
            function initHandler() {{
                const map = new kakao.maps.Map(document.getElementById('map'), {{ center: new kakao.maps.LatLng({center[0]}, {center[1]}), level: {zoom} }});
                POSITIONS.forEach(p => {{
                    let ctype = 'tour';
                    if (p.type.includes('oliveyoung')) ctype = 'oliveyoung'; else if (p.type.includes('daiso')) ctype = 'daiso';
                    const marker = new kakao.maps.Marker({{ map: map, position: new kakao.maps.LatLng(p.lat, p.lng), image: new kakao.maps.MarkerImage(icons[ctype] || icons.tour, new kakao.maps.Size(32, 32)) }});
                    const iw = new kakao.maps.InfoWindow({{ content: `<div style="padding:5px;font-size:12px;white-space:nowrap;">${{p.title}}</div>` }});
                    kakao.maps.event.addListener(marker, 'click', () => {{ map.setCenter(marker.getPosition()); map.setLevel(4); }});
                    kakao.maps.event.addListener(marker, 'mouseover', () => iw.open(map, marker));
                    kakao.maps.event.addListener(marker, 'mouseout', () => iw.close());
                }});
            }}
            if (typeof kakao !== 'undefined') kakao.maps.load(initHandler);
        }})();
    </script>
    """
    components.html(html, height=height)


# --- MAIN APP LOGIC ---
def main():
    inject_custom_css()
    
    st.markdown("""<div style="margin-bottom: 20px;"><a href="/" style="text-decoration: none; color: #F93780; font-size: 26px; font-weight: 800;">Integrated K-Beauty MAP</a></div>""", unsafe_allow_html=True)
    
    # Session State Init
    if 'oy_more' not in st.session_state: st.session_state.oy_more = False
    if 'daiso_more' not in st.session_state: st.session_state.daiso_more = False
    if 'map_center' not in st.session_state: st.session_state['map_center'] = (37.5665, 126.9780)
    if 'map_zoom' not in st.session_state: st.session_state['map_zoom'] = 7
    if 'user_persona' not in st.session_state: st.session_state['user_persona'] = None
    if 'user_district' not in st.session_state: st.session_state['user_district'] = '전체 (All)'

    # Load Data
    df_oy = load_data('oliveyoung_best_integrated.csv')
    df_daiso = load_data('daiso_march_best.csv')
    df_tour = load_data('last_tour_final_mapped.csv')  # Super dataset for everything!
    df_stores = load_data('seoul_cosmetic.csv')

    # Create 5 TABS
    t_quiz, t_my_tour, t_home, t_cosmo, t_tourist = st.tabs([
        "🧠 PERSONA QUIZ", "🗺️ MY PERSONA MAP", "🏠 TODAY BEST", "💄 COSMETICS", "📍 ALL TOURIST MAP"
    ])

    # ---------------- TAB 1: PERSONA QUIZ ----------------
    with t_quiz:
        st.markdown("<h2 class='quiz-title'>Find Your K-Beauty Persona & Area</h2>", unsafe_allow_html=True)
        
        st.markdown("<div class='quiz-card'>", unsafe_allow_html=True)
        with st.form("persona_quiz_form"):
            st.markdown("<div class='quiz-title' style='font-size:1.1em;'>Q1. K-뷰티 장품 선택 기준 (Purchase Priority)</div>", unsafe_allow_html=True)
            q1 = st.radio("", [
                "[A] 강력하고 확실한 프리미엄 기술력 (확실한 효과) / Premium technology",
                "[B] 매일 발라도 자극 없이 편안하고 순한 데일리 수분 / Daily moisture",
                "[C] 가볍고 산뜻하게 모공과 열감을 잡아주는 제품 / Pore & cooling",
                "[D] 성분이 증명되고 체계적인 기능과 루틴 / Scientifically proven",
                "[E] 장벽부터 톤업까지 하나로 끝내는 고효율 솔루션 / Multitasking care"
            ], label_visibility="collapsed")
            
            st.markdown("<hr><div class='quiz-title' style='font-size:1.1em;'>Q2. 이상적인 서울 여행 스타일 (Travel Style)</div>", unsafe_allow_html=True)
            q2 = st.radio("", [
                "[A] 화려한 백화점 쇼핑 & 럭셔리 실내 스팟 / Luxury indoor",
                "[B] 트렌디한 시장, 팝업스토어 / Trendy pop-up stores",
                "[C] 고궁과 활기찬 야외 액티비티 / Palaces & Activities",
                "[D] 전시관이나 자연 속 한적한 시간 / Quiet galleries & Nature"
            ], label_visibility="collapsed")
            
            st.markdown("<hr><div class='quiz-title' style='font-size:1.1em;'>Q3. 완성하고 싶은 피부 (Skin Goal)</div>", unsafe_allow_html=True)
            q3 = st.radio("", [
                "[A] 늘어짐 없이 탱탱한 밀도 [고밀도 윤광 피부]",
                "[B] 속부터 편안하고 맑은 [투명 물광 피부]",
                "[C] 번들거림 없이 매끄러운 [클리어 보송 피부]",
                "[D] 잡티 없이 튼튼하게 빛나는 [건강 브라이트닝 피부]",
                "[E] 단숨에 만들어내는 [단기 효율 톤업 피부]"
            ], label_visibility="collapsed")

            st.markdown("<hr><div class='quiz-title' style='font-size:1.1em;'>Q4. 선호 자치구 (District)</div>", unsafe_allow_html=True)
            user_district_choice = st.selectbox("", SEOUL_DISTRICTS, label_visibility="collapsed")            
            submitted = st.form_submit_button("✨ 진단결과 확인 (Analyze Persona)")
            
        st.markdown("</div>", unsafe_allow_html=True)

        if submitted:
            st.session_state['user_district'] = user_district_choice.split(" (")[0]
            scores = {'중국':0, '일본':0, '대만':0, '미국':0, '홍콩':0}
            
            if "[A]" in q1: scores['중국'] += 2
            elif "[B]" in q1: scores['일본'] += 2
            elif "[C]" in q1: scores['대만'] += 2
            elif "[D]" in q1: scores['미국'] += 2
            elif "[E]" in q1: scores['홍콩'] += 2
            
            if "[A]" in q2: scores['중국'] += 1; scores['홍콩'] += 1
            elif "[B]" in q2: scores['대만'] += 1
            elif "[C]" in q2: scores['미국'] += 1
            elif "[D]" in q2: scores['일본'] += 1

            if "[A]" in q3: scores['중국'] += 1
            elif "[B]" in q3: scores['일본'] += 1
            elif "[C]" in q3: scores['대만'] += 1
            elif "[D]" in q3: scores['미국'] += 1
            elif "[E]" in q3: scores['홍콩'] += 1
            
            best_persona = max(scores, key=scores.get)
            st.session_state['user_persona'] = best_persona
            
            st.markdown(f"""
                <div class='persona-result'>
                    <h1>당신의 K-뷰티 페르소나 (Your Persona)</h1>
                    <h2 style='font-size:35px; margin:20px 0;'>{PERSONA_INFO[best_persona][0]}</h2>
                    <p style='font-size:18px;'><i>"{PERSONA_INFO[best_persona][1]}"</i></p>
                    <p style="margin-top:20px; font-weight: 700;">추천 자치구: {st.session_state['user_district']}</p>
                    <p><b>[MY PERSONA MAP] 탭을 클릭하여 추천 관광지 및 맞춤 일정을 확인하세요!</b></p>
                </div>
            """, unsafe_allow_html=True)

    # ---------------- TAB 2: MY PERSONA MAP ----------------
    with t_my_tour:
        st.markdown("<h2>🗺️ MY PERSONA TOUR MAP</h2>", unsafe_allow_html=True)
        persona = st.session_state.get('user_persona')
        cur_district = st.session_state.get('user_district', '전체')

        if not persona:
            st.warning("⚠️ PERSONA QUIZ 탭에서 퀴즈를 완료해주세요! (Complete the quiz first!)")
        else:
            st.info(f"선택된 페르소나: **{PERSONA_INFO[persona][0]}** | 추천 지역: **{cur_district}**")
            
            if df_tour.empty:
                st.error("관광지 데이터가 없습니다.")
            else:
                df_rec = df_tour[df_tour['K뷰티_추천_페르소나'].astype(str).str.contains(persona, na=False)]
                if cur_district != '전체' and cur_district != '전체 (All)':
                    df_rec_gu = df_rec[df_rec['시/군/구'].astype(str).str.contains(cur_district, na=False)]
                    if len(df_rec_gu) > 0:
                        df_rec = df_rec_gu
                    else:
                        st.info("선택하신 자치구에 맞춤 관광지가 조금 부족하여 서울 전역에서 추천합니다.")
                        
                df_rec = df_rec.sort_values(by='검색건수', ascending=False, na_position='last').head(40)
                
                map_data = []
                for _, row in df_rec.iterrows():
                    cd = row.get('area_cd')
                    cong_info = get_seoul_city_data(cd)
                    map_data.append({
                        'name': row['관광지명'],
                        'category': row['소분류 카테고리'],
                        'district': row['시/군/구'],
                        'lat': row['lat'],
                        'lng': row['lng'],
                        'congestion_lvl': cong_info['lvl']
                    })
                
                st.markdown(f"**라이프스타일 맞춤 관광지 {len(map_data)}곳**")
                render_kakao_map_persona(map_data)

            # Itinerary
            st.markdown("<br><h3>🗓️ Recommended Half-Day Itinerary</h3>", unsafe_allow_html=True)
            with st.expander("✨ 지금 바로 떠날 수 있는 '반나절 맞춤 여행 코스' 보기 (Recommended Half-Day Course)", expanded=True):
                itinerary_data = {
                    '중국': [
                        "📍 오전 11:00 - 명동역 인근 올리브영 타운 방문 (프리미엄 앰플 & 기기 쇼핑) <br> (11:00 AM - Visit Olive Young Town Myeongdong for premium care shopping)",
                        "📍 오후 13:00 - 더현대 서울 혹은 백화점 내 '무료 전시' 감상하며 인파 피하기 <br> (1:00 PM - Enjoy free exhibitions at The Hyundai Seoul or department stores)",
                        "📍 오후 16:00 - 한강 공원이 보이는 카페에서 럭셔리한 시티뷰 즐기기 <br> (4:00 PM - Enjoy luxury city view at a Han River view cafe)"
                    ],
                    '일본': [
                        "📍 오전 11:00 - 명동역 올리브영 방문 (텍스 리펀 챙기기 & 추천 마스크팩 구매) 🌿 <br> (11:00 AM - Visit Myeongdong Olive Young for tax refund & mask packs)",
                        "📍 오후 13:00 - 햇빛과 인파를 피할 수 있는 '근처 실내 전시관(여유 상태)'에서 문화생활 ☕ <br> (1:00 PM - Cultural life at a nearby quiet indoor gallery)",
                        "📍 오후 16:00 - 자극받은 피부를 쉬게 해주는 한적한 도심 공원 산책하기 🌳 <br> (4:00 PM - Rest your skin with a peaceful walk in a city park)"
                    ],
                    '대만': [
                        "📍 오전 11:00 - 트렌디한 시장(광장시장 등)에서 가벼운 로컬 푸드 체험 <br> (11:00 AM - Local food experience at trendy markets like Gwangjang Market)",
                        "📍 오후 13:00 - 쿨링이 필요한 피부를 위해 시원한 실내 팝업스토어 탐방 <br> (1:00 PM - Explore cool indoor pop-up stores for skin cooling)",
                        "📍 오후 16:00 - 모공 케어 아이템 장착 후 남산공원의 선선한 바람 쐬기 <br> (4:00 PM - Enjoy cool breeze at Namsan Park after pore care shopping)"
                    ],
                    '미국': [
                        "📍 오전 11:00 - 성수동 팝업스토어에서 가장 핫한 신상 글로우 제품 테스트 <br> (11:00 AM - Test hot new glow products at Seongsu-dong pop-ups)",
                        "📍 오후 13:00 - 힙한 대형 카페나 쇼핑 센터에서 숏폼 촬영하기 <br> (1:00 PM - Film short-form videos at hip grand cafes or malls)",
                        "📍 오후 16:00 - 액티비티가 어우러진 복합 문화 공간에서 에너지 충전 <br> (4:00 PM - Recharge energy at complex cultural spaces with activities)"
                    ],
                    '홍콩': [
                        "📍 오전 11:00 - 올인원 멀티밤 구매 후 동대문 복합 쇼핑 타워 정복 <br> (11:00 AM - Conquer Dongdaemun shopping towers with all-in-one balm)",
                        "📍 오후 13:00 - 짧은 시간 내에 고효율로 즐기는 공연 혹은 미디어 아트 관람 <br> (1:00 PM - Enjoy high-efficiency performances or media art)",
                        "📍 오후 16:00 - 환급 키오스크에서 세금 환급 후 청계천 밤도깨비 야시장 산책 <br> (4:00 PM - Walk along Cheonggyecheon after tax refund at a kiosk)"
                    ]
                }
                
                selected_itinerary = itinerary_data.get(persona, itinerary_data['일본'])
                for step in selected_itinerary:
                    st.markdown(f"**{step}**", unsafe_allow_html=True)

    # ---------------- TAB 3: TODAY BEST (HOME) ----------------
    with t_home:
        f1, f2 = st.columns(2)
        with f1:
            oy_cats = df_oy['카테고리 이름'].unique() if not df_oy.empty else []
            sel_cos_cat = st.selectbox("💄 Favorite Cosmetic Category", ["All"] + list(oy_cats))
        with f2:
            tour_cats = df_tour['중분류 카테고리'].unique() if not df_tour.empty else []
            sel_tour_cat = st.selectbox("🏙️ Favorite Attraction Category", ["All"] + list(tour_cats))

        st.markdown("<h3 style='margin-bottom:20px;'>🔥 Brand Best 5</h3>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        
        brand_params = [
            ('oliveyoung', df_oy, '상품명', '할인 가격', c1),
            ('daiso', df_daiso, 'goods_name', 'price', c2)
        ]
        
        for brand, df, name_col, price_col, col in brand_params:
            with col:
                st.markdown(f"<div class='glass-card'><h4>{brand.upper()} Bestsellers</h4>", unsafe_allow_html=True)
                if df.empty:
                    st.warning("No data")
                else:
                    if sel_cos_cat != "All":
                        cat_col = '카테고리 이름' if brand == 'oliveyoung' else 'category'
                        if cat_col in df.columns:
                            df_filtered = df[df[cat_col].str.contains(sel_cos_cat, na=False)]
                        else:
                            df_filtered = df # Fallback
                    else: 
                        df_filtered = df
                    
                    best_5 = df_filtered.head(5)
                    sub_cols = st.columns(5)
                    for i, (_, row) in enumerate(best_5.iterrows()):
                        with sub_cols[i % 5]:
                            name = row.get(name_col, 'Unknown')
                            price = int(row.get(price_col, 0)) if pd.notna(row.get(price_col)) else 0
                            img_path = find_image_path(name, brand)
                            img_base64 = get_base64_img(img_path)
                            
                            if img_base64:
                                img_tag = f'<img src="data:image/jpeg;base64,{img_base64}" class="product-img">'
                            else:
                                remote_url = get_oy_image_url(row.get('url', '')) if brand == 'oliveyoung' else row.get('image_url', '')
                                if remote_url:
                                    img_tag = f'<img src="{remote_url}" class="product-img">'
                                else:
                                    img_tag = '<div class="product-img" style="background:#eee; line-height:100px; font-size:10px;">No Image</div>'
                            
                            st.markdown(f'<div class="product-card">{img_tag}<div class="product-title">{name}</div><div class="product-price">{price:,}원</div></div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        # Tourist Best 10 Summary
        st.markdown("<h3 style='margin-top:40px;'>📍 Tourist Best 10 Shortcuts</h3>", unsafe_allow_html=True)
        if not df_tour.empty:
            tour_filtered = df_tour.copy()
            if sel_tour_cat != "All":
                tour_filtered = tour_filtered[tour_filtered['중분류 카테고리'] == sel_tour_cat]
            top_10 = tour_filtered.head(10)
            
            t_subcols = st.columns(5)
            for i, (_, r) in enumerate(top_10.iterrows()):
                congest = get_seoul_city_data(r.get('area_cd'))['lvl']
                with t_subcols[i % 5]:
                    st.markdown(f'<div class="glass-card" style="padding:10px;text-align:center;"><div style="font-weight:700;font-size:13px;">{r["관광지명"]}</div><div style="font-size:11px;color:#F93780;">{congest}</div></div>', unsafe_allow_html=True)


    # ---------------- TAB 4: COSMETICS ----------------
    with t_cosmo:
        st.markdown("<h2 style='text-align:center;'>💄 K-Beauty Trend Search</h2>", unsafe_allow_html=True)
        bc1, bc2 = st.columns(2)
        brand_info = [('oliveyoung', df_oy, bc1), ('daiso', df_daiso, bc2)]
        
        for brand, df, bcol in brand_info:
            with bcol:
                st.markdown(f"### {brand.upper()} March Best 100")
                if df.empty:
                    st.warning("Data not available.")
                    continue
                name_col, price_col = ('상품명', '할인 가격') if brand == 'oliveyoung' else ('goods_name', 'price')
                show_full = st.session_state.get(f'{brand}_more', False)
                items = df.head(100 if show_full else 3)
                grid_cols = st.columns(3) 
                for i, (_, row) in enumerate(items.iterrows()):
                    with grid_cols[i % 3]:
                        name = row.get(name_col, 'Unknown')
                        price = int(row.get(price_col, 0)) if pd.notna(row.get(price_col)) else 0
                        img_path = find_image_path(name, brand)
                        img_base64 = get_base64_img(img_path)
                        img_tag = f'<img src="data:image/jpeg;base64,{img_base64}" class="product-img">' if img_base64 else \
                                f'<img src="{get_oy_image_url(row.get("url", "")) if brand=="oliveyoung" else row.get("image_url", "")}" class="product-img">'
                        
                        st.markdown(f'<div class="product-card"><div class="best-label">TOP {i+1}</div>{img_tag}<div class="product-title" style="font-size:0.7rem;">{name}</div><div class="product-price" style="font-size:0.8rem;">{price:,}원</div></div>', unsafe_allow_html=True)
                
                if not show_full:
                    if st.button(f"View All {brand.upper()} List", key=f"btn_{brand}"):
                        st.session_state[f'{brand}_more'] = True
                        st.rerun()
                else:
                    if st.button("Hide Full List", key=f"hide_{brand}"): st.session_state[f'{brand}_more'] = False; st.rerun()

    # ---------------- TAB 5: ALL TOURIST MAP ----------------
    with t_tourist:
        st.markdown("<h2>📍 All Seoul Unified Tourist Map</h2>", unsafe_allow_html=True)
        if df_tour.empty:
            st.error("No Tourist Data.")
        else:
            col_f1, col_f2 = st.columns([1, 2.5])
            with col_f1:
                st.markdown("#### 🔍 Search by District")
                gu_col = next((c for c in df_tour.columns if '시/군/구' in c), '시/군/구')
                gu_list = sorted([str(x) for x in df_tour[gu_col].unique() if pd.notnull(x)])
                sel_gu = st.selectbox("Select District", ["All"] + gu_list, key="sel_gu_all")
                
                cat_col = next((c for c in df_tour.columns if '중분류' in c), '중분류 카테고리')
                cat_list = sorted([str(x) for x in df_tour[cat_col].unique() if pd.notnull(x)])
                sel_cat = st.multiselect("Category Filter", cat_list, key="sel_cat_all")
                
                gu_data = df_tour.copy()
                if sel_gu != "All": gu_data = gu_data[gu_data[gu_col] == sel_gu]
                if sel_cat: gu_data = gu_data[gu_data[cat_col].isin(sel_cat)]

                st.markdown("---")
                st.markdown(f"#### 🏆 Ranked Places ({len(gu_data)} places found)")
                st.info("💡 Click name in the left to focus on Map.")
                
                display_items = gu_data.sort_values(by='검색건수', ascending=False, na_position='last').head(15)
                for i, (_, row) in enumerate(display_items.iterrows()):
                    congest = get_seoul_city_data(row.get('area_cd'))['lvl']
                    btn_lbl = f"{i+1}. {row['관광지명']} | {congest} | {row['소분류 카테고리']}"
                    if st.button(btn_lbl, key=f"btn_all_{row['관광지명']}_{i}"):
                        if pd.notna(row['lat']) and pd.notna(row['lng']):
                            st.session_state['map_center'] = (float(row['lat']), float(row['lng']))
                            st.session_state['map_zoom'] = 4
                        st.rerun()

            with col_f2:
                map_stores = df_stores.to_dict('records') if not df_stores.empty else []
                map_tour_items = []
                for _, r in gu_data.head(50).iterrows():
                    congest = get_seoul_city_data(r.get('area_cd'))['lvl']
                    map_tour_items.append({'lat': r['lat'], 'lng': r['lng'], 'name': r['관광지명'], 'lvl': congest})
                render_map_unified(map_tour_items, stores=map_stores, height=650, zoom=st.session_state['map_zoom'], center=st.session_state['map_center'])


if __name__ == "__main__":
    main()
