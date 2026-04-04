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
import folium
from folium import CustomIcon

# --- 1. Page Configuration & Env ---
st.set_page_config(page_title="Integrated K-Beauty Tour Dashboard", layout="wide", initial_sidebar_state="expanded")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOUR_DATA_DIR = os.path.join(BASE_DIR, 'data')
TOUR_IMG_DIR = os.path.join(BASE_DIR, 'images')

SEOUL_CITY_DATA_API_KEY = st.secrets.get("SEOUL_CITY_DATA_API_KEY", os.getenv("SEOUL_CITY_DATA_API_KEY", ""))

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

PERSONA_PRODUCTS = {
    '중국': ["리쥬란 앰플", "메디큐브 뷰티 디바이스", "고기능 브라이트닝 세럼"],
    '일본': ["아누아 어성초 토너", "토리든 다이브인 세럼", "라운드랩 보습 크림"],
    '대만': ["마녀공장 클렌징 오일", "비플레인 녹두 클렌징폼", "쿨링 패드"],
    '미국': ["바이오던스 콜라겐 마스크", "넘버즈인 글루타치온 세럼", "브라이트닝 앰플"],
    '홍콩': ["에스트라 아토베리어 365 크림", "라로슈포제 선크림", "바이오더마 클렌징 제품"]
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
# A) Persona Map Renderer (with left List view) - Using Leaflet
def render_folium_map_persona(locations, stores=None, height=650, level=12, center_lat=37.5665, center_lng=126.9780):
    if not locations: return st.warning("지도에 표시할 추천 장소가 없습니다.")

    markers_js, list_items_html, stores_js = "", "", ""
    valid_locs = [l for l in locations if l['lat'] and l['lng']]
        
    for i, loc in enumerate(valid_locs):
        cong_lvl = loc.get('congestion_lvl', '정보없음')
        s_name = str(loc['name']).replace("'", "`")
        s_category = str(loc.get('category', '')).replace("'", "`")
        
        markers_js += f"{{ title: '{s_name}', pos: [{loc['lat']}, {loc['lng']}], congestion: '{cong_lvl}' }},"
        
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

    if stores:
        for s in stores:
            try:
                lat, lng = float(s['위도']), float(s['경도'])
                if pd.notna(lat) and pd.notna(lng):
                    brand = 'oliveyoung' if 'olive' in str(s['메이커명']).lower() else 'daiso'
                    name = str(s['매장명']).replace("'", "`")
                    stores_js += f"{{ title: '{name}', pos: [{lat}, {lng}], brand: '{brand}' }},"
            except: continue

    html_code = f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        .list-item:hover {{ background: #f8f9fa; }}
        .active-item {{ background: #e7f5ff !important; border-left: 4px solid #339af0; }}
        ::-webkit-scrollbar {{ width: 6px; }}
        ::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 10px; }}
    </style>
    
    <div style="display: flex; width: 100%; height: {height}px; font-family: 'Pretendard', sans-serif; border: 1px solid #ddd; border-radius: 12px; overflow: hidden; background: #fff;">
        <div style="width: 300px; height: 100%; overflow-y: auto; background: #fff; border-right: 1px solid #ddd;" id="sidebar">
            <div style="padding: 10px; background: #f1f3f5; font-size: 11px; color: #495057; font-weight: 700;">추천 관광지 ({len(valid_locs)})</div>
            {list_items_html}
        </div>
        <div id="map" style="flex: 1; height: 100%;"></div>
    </div>
    
    <script>
        var map, markers = [], popups = [];
        var ICON_URLS = {{ 
            '여유': 'https://maps.google.com/mapfiles/ms/icons/green-dot.png', 
            '보통': 'https://maps.google.com/mapfiles/ms/icons/yellow-dot.png', 
            '약간 붐빔': 'https://maps.google.com/mapfiles/ms/icons/orange-dot.png', 
            '붐빔': 'https://maps.google.com/mapfiles/ms/icons/red-dot.png', 
            '정보없음': 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
            'oliveyoung': 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
            'daiso': 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'
        }};

        function initMap() {{
            map = L.map('map').setView([{center_lat}, {center_lng}], {level});
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenStreetMap'
            }}).addTo(map);

            var positions = [{markers_js}];
            var group = new L.featureGroup();

            // 1. Tour Markers
            positions.forEach(function(p, i) {{
                var icon = L.icon({{ iconUrl: ICON_URLS[p.congestion] || ICON_URLS['정보없음'], iconSize: [32, 32], iconAnchor: [16, 32], popupAnchor: [0, -32] }});
                var marker = L.marker(p.pos, {{ icon: icon, title: p.title }}).addTo(map);
                var content = '<div style="padding:5px;min-width:150px;font-family:pretendard;"><b>' + p.title + '</b><br><span style="color:#e74c3c;font-size:11px;">여긴 어때? (추천 관광지)</span><br><span style="color:#666;font-size:11px;">혼잡도: ' + p.congestion + '</span></div>';
                marker.bindPopup(content);
                markers.push(marker);
                group.addLayer(marker);
                marker.on('mouseover', function(e) {{ this.openPopup(); }});
                marker.on('click', function(e) {{ focusMarker(i); }});
            }});

            // 2. Store Markers
            var stores = [{stores_js}];
            stores.forEach(function(s) {{
                var icon = L.icon({{ iconUrl: ICON_URLS[s.brand] || ICON_URLS['정보없음'], iconSize: [32, 32], iconAnchor: [16, 32], popupAnchor: [0, -32] }});
                var marker = L.marker(s.pos, {{ icon: icon, title: s.title }}).addTo(map);
                var content = '<div style="padding:5px;min-width:150px;font-family:pretendard;"><b>[' + s.brand.toUpperCase() + '] ' + s.title + '</b><br><span style="color:#00b894;font-size:11px;">K-뷰티 쇼핑은 여기서!</span></div>';
                marker.bindPopup(content);
                group.addLayer(marker);
                marker.on('mouseover', function(e) {{ this.openPopup(); }});
            }});

            if(positions.length > 0) {{ map.fitBounds(group.getBounds().pad(0.1)); }}
        }}

        function focusMarker(idx) {{
            markers.forEach((m, i) => {{
                document.getElementById('item-'+i).classList.remove('active-item');
            }});
            var m = markers[idx];
            map.setView(m.getLatLng(), 15);
            m.openPopup();
            var item = document.getElementById('item-'+idx);
            item.classList.add('active-item');
            item.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }}

        initMap();
    </script>
    """
    components.html(html_code, height=height + 20)

# B) Unified Map Renderer (General Tourist Map) - Using Folium
def render_map_unified(locations, stores=None, center=(37.5665, 126.9780), zoom=7, height=450):
    m = folium.Map(location=center, zoom_start=zoom, control_scale=True)
    icons = {
        'tour': 'https://maps.google.com/mapfiles/ms/icons/green-dot.png',
        'oliveyoung': 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
        'daiso': 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'
    }
    for loc in locations:
        try:
            lat, lng = float(loc['lat']), float(loc['lng'])
            if not pd.isna(lat) and not pd.isna(lng):
                title = f"{loc['name']} {f'[{loc.get('lvl', '정보없음')}]' if 'lvl' in loc else ''}"
                icon = CustomIcon(icons['tour'], icon_size=(32, 32), icon_anchor=(16, 32), popup_anchor=(0, -32))
                folium.Marker([lat, lng], tooltip=title, icon=icon, popup=folium.Popup(f'<div style="white-space:nowrap;">{title}</div>')).add_to(m)
        except: continue
    if stores:
        for s in stores:
            try:
                lat, lng = float(s['위도']), float(s['경도'])
                if not pd.isna(lat) and not pd.isna(lng):
                    ctype = 'oliveyoung' if 'olive' in str(s['메이커명']).lower() else 'daiso'
                    icon = CustomIcon(icons[ctype], icon_size=(32, 32), icon_anchor=(16, 32), popup_anchor=(0, -32))
                    folium.Marker([lat, lng], tooltip=s['매장명'], icon=icon, popup=folium.Popup(f'<div style="white-space:nowrap;">{s["매장명"]}</div>')).add_to(m)
            except: continue
    components.html(m._repr_html_(), height=height)


# --- MAIN APP LOGIC ---
def main():
    inject_custom_css()
    st.markdown("""<div style="margin-bottom: 20px;"><a href="/" style="text-decoration: none; color: #F93780; font-size: 26px; font-weight: 800;">Integrated K-Beauty MAP</a></div>""", unsafe_allow_html=True)
    
    if 'oy_more' not in st.session_state: st.session_state.oy_more = False
    if 'daiso_more' not in st.session_state: st.session_state.daiso_more = False
    if 'map_center' not in st.session_state: st.session_state['map_center'] = (37.5665, 126.9780)
    if 'map_zoom' not in st.session_state: st.session_state['map_zoom'] = 7
    if 'user_persona' not in st.session_state: st.session_state['user_persona'] = None
    if 'user_district' not in st.session_state: st.session_state['user_district'] = '전체 (All)'

    df_oy = load_data('oliveyoung_best_integrated_with_images.csv')
    df_daiso = load_data('daiso_march_best.csv')
    df_tour = load_data('last_tour_final_mapped.csv')
    df_stores = load_data('seoul_cosmetic.csv')

    t_quiz, t_my_tour, t_home, t_cosmo, t_tourist = st.tabs([
        "🧠 PERSONA QUIZ", "🗺️ MY PERSONA MAP", "🏠 TODAY BEST", "💄 COSMETICS", "📍 ALL TOURIST MAP"
    ])

    with t_quiz:
        st.markdown("<h2 class='quiz-title'>Find Your K-Beauty Persona & Area</h2>", unsafe_allow_html=True)
        st.markdown("<div class='quiz-card'>", unsafe_allow_html=True)
        with st.form("persona_quiz_form"):
            st.markdown("<div class='quiz-title' style='font-size:1.1em;'>Q1. K-뷰티 장품 선택 기준 (Purchase Priority)</div>", unsafe_allow_html=True)
            q1 = st.radio("", [
                "[A] 강력하고 확실한 프리미엄 기술력 / Premium technology",
                "[B] 데일리 수분 케어 / Daily moisture",
                "[C] 가벼운 모공 & 쿨링 / Pore & cooling",
                "[D] 성분이 확실한 기능성 / Scientifically proven",
                "[E] 멀티태스킹 / Multitasking care"
            ], label_visibility="collapsed")
            st.markdown("<hr><div class='quiz-title' style='font-size:1.1em;'>Q2. 이상적인 서울 여행 스타일 (Travel Style)</div>", unsafe_allow_html=True)
            q2 = st.radio("", [
                "[A] 럭셔리 실내 스팟 / Luxury indoor",
                "[B] 트렌디한 시장, 팝업 / Trendy pop-up",
                "[C] 고궁 & 액티비티 / Palaces & Activities",
                "[D] 한적한 갤러리 & 자연 / Quiet galleries & Nature"
            ], label_visibility="collapsed")
            st.markdown("<hr><div class='quiz-title' style='font-size:1.1em;'>Q3. 완성하고 싶은 피부 (Skin Goal)</div>", unsafe_allow_html=True)
            q3 = st.radio("", ["[A] 윤광", "[B] 물광", "[C] 보송", "[D] 건강", "[E] 톤업"], label_visibility="collapsed")
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
                    <p><b>🔍 [Must-buy Items for You]</b></p>
                </div>
            """, unsafe_allow_html=True)
            must_buy_items = PERSONA_PRODUCTS.get(best_persona, [])
            if must_buy_items:
                st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
                cols = st.columns(len(must_buy_items))
                for idx, item in enumerate(must_buy_items):
                    with cols[idx]:
                        # Check for local image first
                        img_path = find_image_path(item, 'oliveyoung') or find_image_path(item, 'daiso')
                        img_base64 = get_base64_img(img_path)
                        
                        # Fallback to online image from CSV if not found locally
                        online_url = None
                        if not img_base64:
                            search_df = df_oy[df_oy['상품명'].str.contains(item, na=False)] if not df_oy.empty else pd.DataFrame()
                            if search_df.empty and not df_daiso.empty:
                                search_df = df_daiso[df_daiso['goods_name'].str.contains(item, na=False)]
                                if not search_df.empty: online_url = search_df.iloc[0].get('image_url')
                            elif not search_df.empty:
                                online_url = search_df.iloc[0].get('image_url')
                        
                        img_tag = f'<img src="data:image/jpeg;base64,{img_base64}" class="product-img">' if img_base64 else \
                                  (f'<img src="{online_url}" class="product-img">' if online_url else \
                                   '<div class="product-img" style="background:#eee; line-height:100px; font-size:10px;">No Image</div>')
                        
                        st.markdown(f'<div class="product-card" style="height:200px;">{img_tag}<div class="product-title" style="margin-top:10px;font-size:0.8rem;">{item}</div></div>', unsafe_allow_html=True)
            st.markdown("<div style='margin-top:40px; text-align:center;'>", unsafe_allow_html=True)
            if st.button("🗺️ MY PERSONA MAP으로 이동", use_container_width=True):
                components.html('<script>window.parent.document.querySelectorAll(\'button[data-baseweb="tab"]\')[1].click();</script>', height=0)
            st.markdown("</div>", unsafe_allow_html=True)

    with t_my_tour:
        st.markdown("<h2>🗺️ MY PERSONA TOUR MAP</h2>", unsafe_allow_html=True)
        persona = st.session_state.get('user_persona')
        cur_district = st.session_state.get('user_district', '전체')
        if not persona:
            st.warning("⚠️ PERSONA QUIZ 탭에서 퀴즈를 완료해주세요!")
        else:
            st.info(f"페르소나: **{PERSONA_INFO[persona][0]}** | 지역: **{cur_district}**")
            df_rec = df_tour[df_tour['K뷰티_추천_페르소나'].astype(str).str.contains(persona, na=False)]
            if cur_district not in ['전체', '전체 (All)']:
                df_rec_gu = df_rec[df_rec['시/군/구'].astype(str).str.contains(cur_district, na=False)]
                if not df_rec_gu.empty: df_rec = df_rec_gu
            df_rec = df_rec.sort_values(by='검색건수', ascending=False, na_position='last').head(40)
            map_data = []
            for _, row in df_rec.iterrows():
                cong = get_seoul_city_data(row.get('area_cd'))
                map_data.append({
                    'name': row['관광지명'], 'category': row['소분류 카테고리'], 'district': row['시/군/구'],
                    'lat': row['lat'], 'lng': row['lng'], 'congestion_lvl': cong['lvl']
                })
            map_stores = df_stores.to_dict('records') if not df_stores.empty else []
            render_folium_map_persona(map_data, stores=map_stores)

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
        brand_params = [('oliveyoung', df_oy, '상품명', '할인 가격', c1), ('daiso', df_daiso, 'goods_name', 'price', c2)]
        for brand, df, name_col, price_col, col in brand_params:
            with col:
                st.markdown(f"<div class='glass-card'><h4>{brand.upper()} Bestsellers</h4>", unsafe_allow_html=True)
                if not df.empty:
                    cat_col = '카테고리 이름' if brand == 'oliveyoung' else 'category'
                    df_filtered = df[df[cat_col].str.contains(sel_cos_cat, na=False)] if sel_cos_cat != "All" else df
                    best_5 = df_filtered.head(5)
                    sub_cols = st.columns(5)
                    for i, (_, row) in enumerate(best_5.iterrows()):
                        with sub_cols[i % 5]:
                            name = row.get(name_col, 'Unknown')
                            price = int(row.get(price_col, 0)) if pd.notna(row.get(price_col)) else 0
                            img_path = find_image_path(name, brand)
                            img_base64 = get_base64_img(img_path)
                            img_tag = f'<img src="data:image/jpeg;base64,{img_base64}" class="product-img">' if img_base64 else \
                                      f'<img src="{row.get("image_url", "")}" class="product-img">'
                            st.markdown(f'<div class="product-card">{img_tag}<div class="product-title">{name}</div><div class="product-price">{price:,}원</div></div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    with t_cosmo:
        st.markdown("<h2 style='text-align:center;'>💄 K-Beauty Trend Search</h2>", unsafe_allow_html=True)
        bc1, bc2 = st.columns(2)
        for brand, df, bcol in [('oliveyoung', df_oy, bc1), ('daiso', df_daiso, bc2)]:
            with bcol:
                st.markdown(f"### {brand.upper()} Best 100")
                if not df.empty:
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
                                      f'<img src="{row.get("image_url", "")}" class="product-img">'
                            st.markdown(f'<div class="product-card"><div class="best-label">TOP {i+1}</div>{img_tag}<div class="product-title">{name}</div><div class="product-price">{price:,}원</div></div>', unsafe_allow_html=True)
                    if st.button(f"View All {brand.upper()}", key=f"btn_{brand}"):
                        st.session_state[f'{brand}_more'] = not show_full; st.rerun()

    with t_tourist:
        st.markdown("<h2>📍 Seoul Unified Tourist Map</h2>", unsafe_allow_html=True)
        col_f1, col_f2 = st.columns([1, 2.5])
        with col_f1:
            gu_list = sorted([str(x) for x in df_tour['시/군/구'].unique() if pd.notnull(x)])
            sel_gu = st.selectbox("Select District", ["All"] + gu_list, key="sel_all_gu")
            gu_data = df_tour[df_tour['시/군/구'] == sel_gu] if sel_gu != "All" else df_tour
            st.markdown(f"**{len(gu_data)} places found**")
            display_items = gu_data.sort_values(by='검색건수', ascending=False).head(15)
            for i, (_, row) in enumerate(display_items.iterrows()):
                if st.button(f"{i+1}. {row['관광지명']}", key=f"tour_{i}"):
                    st.session_state['map_center'] = (float(row['lat']), float(row['lng'])); st.rerun()
        with col_f2:
            map_stores = df_stores.to_dict('records') if not df_stores.empty else []
            map_tour_items = [{'lat': r['lat'], 'lng': r['lng'], 'name': r['관광지명']} for _, r in gu_data.head(50).iterrows()]
            render_map_unified(map_tour_items, stores=map_stores, height=650, center=st.session_state['map_center'])

if __name__ == "__main__":
    main()
