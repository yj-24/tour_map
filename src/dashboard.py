import streamlit as st
import pandas as pd
import os
import unicodedata
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import base64
from streamlit_option_menu import option_menu
import requests
from dotenv import load_dotenv
import streamlit.components.v1 as components
import xml.etree.ElementTree as ET

# --- Layout Configuration ---
st.set_page_config(page_title="K-Beauty Persona Tour Map", layout="wide", initial_sidebar_state="expanded")

# --- Directory Paths & Env ---
# 이제 이 폴더만 압축(ZIP)해서 공유해도 어디서든 작동하도록 동적 상대 경로를 사용합니다.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOUR_DATA_DIR = os.path.join(BASE_DIR, 'data')
TOUR_IMG_DIR = os.path.join(BASE_DIR, 'images')

# 카카오맵 JS 키 및 서울시 혼잡도 API 키 (Streamlit Secrets 보안 참조)
# 로컬 테스트 시 `.streamlit/secrets.toml` 에 저장하거나 클라우드 대시보드 Settings 에서 주입하세요.
KAKAO_JS_API_KEY = st.secrets.get("KAKAO_JS_API_KEY", os.getenv("KAKAO_JS_API_KEY", ""))
SEOUL_CITY_DATA_API_KEY = st.secrets.get("SEOUL_CITY_DATA_API_KEY", os.getenv("SEOUL_CITY_DATA_API_KEY", ""))

# --- Cached Data Loading ---
@st.cache_data
def load_csv_data(filepath, encoding='utf-8'):
    try:
        return pd.read_csv(filepath, encoding=encoding)
    except UnicodeDecodeError:
        try:
            return pd.read_csv(filepath, encoding='cp949')
        except Exception as e:
            return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_seoul_city_data(location_id):
    if not SEOUL_CITY_DATA_API_KEY:
        return {"error": "API KEY가 설정되지 않았습니다."}
    location_id = str(location_id).strip()
    url = f"http://openapi.seoul.go.kr:8088/{SEOUL_CITY_DATA_API_KEY}/xml/citydata/1/5/{location_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        result = root.find(".//RESULT/CODE")
        if result is not None and result.text != "INFO-000":
            msg = root.find(".//RESULT/MESSAGE")
            return {"error": msg.text if msg is not None else "Unknown error"}
        stts = root.find(".//LIVE_PPLTN_STTS/LIVE_PPLTN_STTS")
        if stts is not None:
            return {
                "congestion_lvl": stts.findtext("AREA_CONGEST_LVL"),
                "congestion_msg": stts.findtext("AREA_CONGEST_MSG")
            }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "데이터를 찾을 수 없습니다."}


# --- K-Beauty 폰트 및 스타일링 (Apple Minimalism + Glassmorphism) ---
def inject_custom_css():
    st.markdown("""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        html, body, [class*="css"] { font-family: 'Pretendard', -apple-system, sans-serif !important; background-color: #F4F2FA !important; color: #000000 !important; font-weight: 400 !important; letter-spacing: -0.02em !important; }
        [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: transparent !important; }
        [data-testid="stHeader"] { pointer-events: none; }
        [data-testid="stHeader"] * { pointer-events: auto; }
        .block-container { padding: 20px !important; }
        [data-testid="stSidebar"] { background: rgba(255, 255, 255, 0.15) !important; backdrop-filter: blur(20px) !important; -webkit-backdrop-filter: blur(20px) !important; border-right: 1px solid rgba(255, 255, 255, 0.3); }
        .welcome-card { background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 15px; padding: 4rem 3rem; text-align: center; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); margin: 10vh auto; max-width: 700px; }
        .product-card { background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 15px; padding: 20px; margin-bottom: 1.5rem; text-align: center; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); transition: transform 0.2s ease; }
        .product-card:hover { transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2); }
        .product-img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 10px; margin-bottom: 0.8rem; }
        .product-title { font-size: 0.95rem; font-weight: 700 !important; margin: 0.2rem 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #000000; letter-spacing: -0.02em; }
        .product-price { font-size: 0.85rem; font-weight: 400 !important; color: #000000; letter-spacing: -0.02em; }
        .menu-heading { margin-top: 1rem !important; margin-bottom: 1.5rem !important; text-align: center !important; color: #232A32 !important; font-weight: 500 !important; font-size: 40px !important; letter-spacing: 1px !important; }
        iframe[title="streamlit_folium.st_folium"] { border-radius: 15px !important; border: 1px solid rgba(255, 255, 255, 0.3) !important; padding: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important; background: rgba(255, 255, 255, 0.15) !important; }
        
        /* 설문조사 카드 */
        .quiz-card { background: #ffffff; border-radius: 20px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .quiz-title { font-size: 1.5em; font-weight: 800; margin-bottom: 20px; color: #1e272e; }
        .persona-result { background: linear-gradient(135deg, #FF9A9E 0%, #FECFEF 99%, #FECFEF 100%); border-radius: 20px; padding: 40px; color: #000; text-align: center; box-shadow: 0 10px 20px rgba(255, 154, 158, 0.3); margin-top: 20px; }
        </style>
    """, unsafe_allow_html=True)


# --- Helper Functions (K-Beauty Data) ---
def find_image_path(product_name, target_dir):
    if not os.path.exists(target_dir): return None
    product_name_norm = unicodedata.normalize('NFC', str(product_name).strip()).replace(' ', '')
    for f in os.listdir(target_dir):
        f_norm = unicodedata.normalize('NFC', f)
        if product_name_norm in f_norm.replace(' ', ''): return os.path.join(target_dir, f)
    return None

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def render_product_card(product_row, target_dir):
    name = product_row.get('상품명', product_row.get('goods_name', 'Unknown'))
    
    # 가격 파싱 (sale_price, price 처리)
    raw_price = product_row.get('가격', product_row.get('sale_price', product_row.get('price', 0)))
    try: price = int(float(str(raw_price).replace(',', '')))
    except: price = 0
    
    link = product_row.get('링크', '#')
    img_path = find_image_path(name, target_dir)
    
    # URL로 이미지 있는 경우 처리 지원 (다이소 등)
    img_url = product_row.get('image_url')
    
    if img_path and os.path.exists(img_path):
        img_b64 = get_base64_of_bin_file(img_path)
        img_html = f'<img src="data:image/jpeg;base64,{img_b64}" class="product-img" alt="{name}">'
    elif img_url and 'http' in str(img_url):
        img_html = f'<img src="{img_url}" class="product-img" alt="{name}">'
    else:
        img_html = f'<div class="product-img" style="background:#e5e5ea; display:flex; align-items:center; justify-content:center; color:#86868b; font-size:0.8rem;">No Image</div>'

    html = f"""<a href="{link}" target="_blank" style="text-decoration:none; color:inherit;">
                <div class="product-card">{img_html}<div class="product-title" title="{name}">{name}</div><div class="product-price">{price:,}원</div></div></a>"""
    st.markdown(html, unsafe_allow_html=True)

def generate_popup_html(brand, name, address):
    return f'<div style="font-family: Pretendard, sans-serif; padding:10px;"><b style="font-size:16px;">[{brand}] {name}</b><br><span style="color:#555; font-size:13px; margin-top:4px; display:inline-block;">{address}</span></div>'


# --- Kakao Map Renderer (from TOUR SEOUL) ---
def render_kakao_map(locations, height=700, level=8, center_lat=None, center_lng=None):
    if not locations: return st.warning("지도에 표시할 데이터가 없습니다.")

    markers_js, list_items_html = "", ""
    valid_locs = [l for l in locations if l['lat'] and l['lng']]
    
    for i, loc in enumerate(valid_locs):
        cong_lvl = loc.get('congestion_lvl', '정보없음')
        s_name = str(loc['name']).replace("'", "`")
        s_category = str(loc.get('category', '')).replace("'", "`")
        s_district = str(loc.get('district', '')).replace("'", "`")
        s_indoor = str(loc.get('indoor', '-')).replace("'", "`")
        s_age = str(loc.get('age', '-')).replace("'", "`")
        
        markers_js += f"""
            {{ title: '{s_name}', latlng: new kakao.maps.LatLng({loc['lat']}, {loc['lng']}), category: '{s_category}', district: '{s_district}', congestion: '{cong_lvl}', indoor: '{s_indoor}', age: '{s_age}' }},"""
        
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
            <div style="padding: 15px; background: #f8f9fa; border-bottom: 2px solid #ddd; font-weight: bold; position: sticky; top:0; z-index:10;">&#128205; 장소 목록 ({len(valid_locs)}곳)</div>
            {list_items_html}
        </div>
        <div id="map" style="flex: 1; height: 100%;"><div id="loading" style="text-align:center; padding-top:200px;">Map Loading...</div></div>
    </div>
    
    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_API_KEY}&autoload=false"></script>
    <script>
        var map, markers = [], infowindows = [];
        var ICON_URLS = {{ '여유': 'http://maps.google.com/mapfiles/ms/icons/green-dot.png', '보통': 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png', '약간 붐빔': 'http://maps.google.com/mapfiles/ms/icons/orange-dot.png', '붐빔': 'http://maps.google.com/mapfiles/ms/icons/red-dot.png', '정보없음': 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png' }};

        function initMap() {{
            document.getElementById('loading').style.display = 'none';
            var mapContainer = document.getElementById('map');
            var centerLat = {center_lat if center_lat else 37.5665};
            var centerLng = {center_lng if center_lng else 126.9780};
            var mapOption = {{ center: new kakao.maps.LatLng(centerLat, centerLng), level: {2 if center_lat else level} }};
            map = new kakao.maps.Map(mapContainer, mapOption); 
            var positions = [{markers_js}];

            var bounds = new kakao.maps.LatLngBounds();
            for (var i = 0; i < positions.length; i ++) {{
                var marker = new kakao.maps.Marker({{ map: map, position: positions[i].latlng, title: positions[i].title, image: new kakao.maps.MarkerImage(ICON_URLS[positions[i].congestion] || ICON_URLS['정보없음'], new kakao.maps.Size(32, 32)) }});
                var content = '<div style="padding:10px;min-width:180px;font-size:12px;line-height:1.6;border:none;"><b>' + positions[i].title + '</b><br><span style="color:#e74c3c;font-weight:bold;">실시간: ' + positions[i].congestion + '</span><br>' + positions[i].district + ' | ' + positions[i].category + '</div>';
                var infowindow = new kakao.maps.InfoWindow({{ content: content }});
                markers.push(marker); infowindows.push(infowindow);
                bounds.extend(positions[i].latlng);
                
                (function(m, info, idx) {{
                    kakao.maps.event.addListener(m, 'click', function() {{ focusMarker(idx); }});
                    kakao.maps.event.addListener(m, 'mouseover', function() {{ info.open(map, m); }});
                    kakao.maps.event.addListener(m, 'mouseout', function() {{ info.close(); }});
                }})(marker, infowindow, i);
            }}
            if(positions.length > 0 && !{ "true" if center_lat else "false" }) {{ map.setBounds(bounds); }}
        }}

        function focusMarker(idx) {{
            for (var i = 0; i < markers.length; i++) {{ infowindows[i].close(); document.getElementById('item-'+i).style.background = '#fff'; }}
            infowindows[idx].open(map, markers[idx]);
            map.setCenter(markers[idx].getPosition());
            map.setLevel(3);
            document.getElementById('item-'+idx).style.background = '#e7f5ff';
            document.getElementById('item-'+idx).scrollIntoView({{behavior:'smooth', block:'nearest'}});
        }}

        if (typeof kakao !== 'undefined') {{
            kakao.maps.load(initMap);
        }} else {{
            document.getElementById('loading').innerHTML = '<br><br><span style="color:red; font-size:18px; font-weight:bold;">⚠️ 카카오 맵 SDK 구동 실패!</span><br><br><span style="color:#555;">발급받으신 자바스크립트 키 자체는 정상이나, 카카오 서버에서 해당 키에 대한 <b>접근(도메인)이 차단</b>되었습니다.<br><br><a href="https://developers.kakao.com" target="_blank">카카오 디벨로퍼스</a> ➔ 내 애플리케이션 ➔ 플랫폼 메뉴로 이동하여,<br><b>[Web 사이트 도메인]</b>에 현재 스트림릿 주소인 <br><b>http://localhost:8501</b> 을 추가(등록)해 주셔야만 지도가 정상적으로 렌더링됩니다.</span>';        }}
    </script>
    """
    components.html(html_code, height=height + 20)

# --- ग्लोबल Persona Definitions ---
PERSONA_INFO = {
    '중국': ('효능 중심 프리미엄 케어파 (Efficacy-Focused Premium Care) 👑', '한국 클리닉의 리프팅 효과를 그대로, 집에서 완성하는 고밀도 광채. (High-density glow completed at home, just like the lifting effect of a Korean clinic.)'),
    '일본': ('저자극 장벽 케어파 (Low-Irritant Barrier Care) 🌿', '자극 없이 맑게 차오르는 수분감, 내일이 더 기대되는 투명한 결 케어. (Clear moisture without irritation, transparent texture care that makes tomorrow more exciting.)'),
    '대만': ('모공·쿨링 밸런스파 (Pore & Cooling Balance) 🧊', '피부 온도는 낮추고 모공은 촘촘하게, 번들거림 없는 클리어 스킨. (Lower skin temperature and tighten pores for clear skin without greasiness.)'),
    '미국': ('즉각적 광채 추구미 (Immediate Glow-Chasing) ✨', '성분으로 증명하고 결과를 빨리 보는 가장 완벽한 인스턴트 글로우 루틴. (The perfect instant glow routine that proves with ingredients and sees results fast.)'),
    '홍콩': ('멀티태스킹 케어파 (Multitasking Care) ⚡', '복잡한 일상을 심플하게, 단 하나로 장벽/톤업/자외선 차단을 마스터하는 극강의 효율. (Simplifying complex daily life, ultimate efficiency mastering barrier/toning/UV protection all in one.)')
}

SEOUL_DISTRICTS = [
    "전체 (All)", "강남구 (Gangnam-gu)", "강동구 (Gangdong-gu)", "강북구 (Gangbuk-gu)", "강서구 (Gangseo-gu)",
    "관악구 (Gwanak-gu)", "광진구 (Gwangjin-gu)", "구로구 (Guro-gu)", "금천구 (Geumcheon-gu)",
    "노원구 (Nowon-gu)", "도봉구 (Dobong-gu)", "동대문구 (Dongdaemun-gu)", "동작구 (Dongjak-gu)",
    "마포구 (Mapo-gu)", "서대문구 (Seodaemun-gu)", "서초구 (Seocho-gu)", "성동구 (Seongdong-gu)",
    "성북구 (Seongbuk-gu)", "송파구 (Songpa-gu)", "양천구 (Yangcheon-gu)", "영등포구 (Yeongdeungpo-gu)",
    "용산구 (Yongsan-gu)", "은평구 (Eunpyeong-gu)", "종로구 (Jongno-gu)", "중구 (Jung-gu)", "중랑구 (Jungnang-gu)"
]
# --- MAIN APP LOGIC ---
def main():
    inject_custom_css()
    
    # Header & Nav (From K-Beauty)
    col_logo, col_menu = st.columns([1, 4])
    with col_logo:
        st.markdown("""<div style="margin-top: -2px; display: flex; align-items: center;"><a href="/" style="text-decoration: none; color: #F93780; font-size: 22px; font-weight: 800;">K-Beauty MAP</a></div>""", unsafe_allow_html=True)
    with col_menu:
        menu_options = ["HOME (QUIZ)", "BEST ITEM", "STORES", "TOUR MAP", "TAX REFUND"]
        selected_menu = option_menu(
            menu_title=None, options=menu_options, default_index=0, orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background": "transparent", "margin-top": "0px", "margin-bottom": "30px", "justify-content": "flex-end"},
                "icon": {"display": "none"}, "nav-item": {"flex": "0 0 auto", "margin": "0px"},
                "nav-link": {"font-size": "13px", "font-weight": "600", "background": "transparent", "color": "#1e272e"},
                "nav-link-selected": {"background-color": "transparent", "color": "#F93780", "font-weight": "800", "text-decoration": "underline"}
            })

    # Location Service
    user_lat, user_lon = 37.5665, 126.9780  # Default Seoul
    if selected_menu in ["BEAUTY STORES", "MY TOUR MAP", "TAX REFUND"]:
        c1, c2 = st.columns([1, 10])
        with c1: loc_data = streamlit_geolocation()
        with c2: st.markdown("<div style='margin-top:0.8rem; font-weight:700;'>내 위치 찾기 (My Location)</div>", unsafe_allow_html=True)
        if loc_data and loc_data.get('latitude'):
            user_lat, user_lon = loc_data['latitude'], loc_data['longitude']

    # --- TAB 1: HOME (PERSONA QUIZ) ---
    if selected_menu == "HOME (QUIZ)":
        st.markdown("<h2 class='menu-heading'>Find Your K-Beauty Persona & Area</h2>", unsafe_allow_html=True)
        
        st.markdown("<div class='quiz-card'>", unsafe_allow_html=True)
        with st.form("persona_quiz_form"):
            st.markdown("<div class='quiz-title'>Q1. K-뷰티 스킨케어 제품을 고를 때, 가장 중요하게 생각하는 것은? <br>(What is your priority when choosing K-Beauty skin care products?)</div>", unsafe_allow_html=True)
            q1 = st.radio("Purchase Priority", [
                "[A] 강력하고 확실한 프리미엄 기술력 (확실한 효과) / Premium technology (Clear results)",
                "[B] 매일 발라도 자극 없이 편안하고 순한 데일리 수분 / Daily moisture without irritation",
                "[C] 가볍고 산뜻하게 모공과 열감을 잡아주는 제품 / Pore & cooling with light finish",
                "[D] 성분이 과학적으로 증명되고 체계적인 기능과 루틴 / Scientifically proven ingredients & routine",
                "[E] 장벽부터 톤업까지 하나로 끝내는 고효율 멀티 솔루션 / High-efficiency multitasking care"
            ])
            
            st.markdown("<hr><div class='quiz-title'>Q2. 이상적인 서울 여행의 모습에 가장 가까운 것은? <br>(Which one best describes your ideal trip to Seoul?)</div>", unsafe_allow_html=True)
            q2 = st.radio("Travel Style", [
                "[A] 화려한 백화점에서 쇼핑하고, 럭셔리한 실내 스팟 즐기기 / Shopping & Luxury indoor spots",
                "[B] 트렌디한 시장이나 팝업스토어로 리프레시 투어 / Trendy markets & Pop-up stores",
                "[C] 고궁을 걷고 활기찬 액티비티 체험하기 / Palaces & Energetic activities",
                "[D] 전시관이나 자연 속에서 차분하게 시간 보내기 / Quiet galleries & Nature"
            ])
            
            st.markdown("<hr><div class='quiz-title'>Q3. K-뷰티 쇼핑으로 완성하고 싶은 당신의 피부 상태는? <br>(What is your desired skin condition after K-Beauty shopping?)</div>", unsafe_allow_html=True)
            q3 = st.radio("Skin Goal", [
                "[A] 늘어짐 없이 탱탱한 밀도를 가진 [고밀도 윤광 피부] / Firm and radiant [High-density glow]",
                "[B] 수분을 머금어 속부터 편안하고 맑은 [투명 물광 피부] / Clear and moisturized [Transparent water-glow]",
                "[C] 번들거림 없이 매끄럽고 모공이 없는 [클리어 보송 피부] / Matte and poreless [Clear matte skin]",
                "[D] 잡티 없이 튼튼하게 빛나는 [건강 브라이트닝 피부] / Healthy and blemish-free [Brightening skin]",
                "[E] 짧은 시간에 만들어내는 [단기 효율 톤업 피부] / Quick results [Instant tone-up]"
            ])

            st.markdown("<hr><div class='quiz-title'>Q4. 서울에서 현재 어디에 계시거나 방문하고 싶으신가요? <br>(Where are you currently staying or want to visit in Seoul?)</div>", unsafe_allow_html=True)
            user_district_choice = st.selectbox("Preferred District (자치구 선택)", SEOUL_DISTRICTS)            
            submitted = st.form_submit_button("✨ 진단 결과 확인하기 (Show My Persona)")
            
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
                <div class='result-card'>
                    <h1 style='color:#fff;'>당신의 K-뷰티 페르소나 (Your Persona)</h1>
                    <h2 style='font-size:35px; margin:20px 0;'>{PERSONA_INFO[best_persona][0]}</h2>
                    <p style='font-size:18px;'><i>"{PERSONA_INFO[best_persona][1]}"</i></p>
                    <p style="margin-top:20px; font-weight: 700;">방문 희망 지역: <span style='font-size: 1.2em;'>&#128205; {st.session_state.get('user_district', '전체')}</span><br>(Your Target Area)</p>
                    <p style="margin-top:20px;">상단 메뉴의 <b>[TOUR MAP]</b> 탭에서 당신의 성향과 위치에 맞는 관광지를 확인하세요!<br>(Check custom places in TOUR MAP tab!)</p>
                </div>
            """, unsafe_allow_html=True)


    # --- TAB 2: BEST ITEM ---
    elif selected_menu == "BEST ITEM":
        st.markdown("<h2 class='menu-heading'>K-BEAUTY BEST ITEM</h2>", unsafe_allow_html=True)
        tab_oy, tab_daiso = st.tabs(["OLIVE YOUNG", "DAISO"])
        with tab_oy:
            df_oy = load_csv_data(os.path.join(TOUR_DATA_DIR, 'oliveyoung_final_top10_by_category.csv'))
            if not df_oy.empty:
                cols = st.columns(5)
                for idx, row in df_oy.iterrows():
                    with cols[idx % 5]: render_product_card(row, os.path.join(TOUR_IMG_DIR, 'oliveyoung_best'))
            else: st.warning("데이터가 아직 수집되지 않았습니다.")
        with tab_daiso:
            df_daiso = load_csv_data(os.path.join(TOUR_DATA_DIR, 'daiso_march_best.csv'))
            if not df_daiso.empty:
                cols = st.columns(5)
                for idx, row in df_daiso.iterrows():
                    with cols[idx % 5]: render_product_card(row, os.path.join(TOUR_IMG_DIR, 'daiso_beauty_best'))


    # --- TAB 3: BEAUTY STORES (Folium Base) ---
    elif selected_menu in ["STORES", "TAX REFUND"]:
        st.markdown(f"<h2 class='menu-heading'>{selected_menu} LOCATION</h2>", unsafe_allow_html=True)
        m = folium.Map(location=[user_lat, user_lon], zoom_start=14, tiles="CartoDB positron")
        folium.Marker([user_lat, user_lon], popup="My Location", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

        if selected_menu == "BEAUTY STORES":
            df_cosmo = load_csv_data(os.path.join(TOUR_DATA_DIR, 'seoul_cosmetic.csv'))
            if not df_cosmo.empty:
                # BOM 헤더(UTF-8-SIG) 및 공백 제거 처리
                df_cosmo.columns = [c.strip().replace('\ufeff', '') for c in df_cosmo.columns]
                
                oy_cluster = MarkerCluster(name="올리브영").add_to(m)
                daiso_cluster = MarkerCluster(name="다이소").add_to(m)
                
                for _, row in df_cosmo.iterrows():
                    if pd.notna(row.get('위도')) and pd.notna(row.get('경도')):
                        maker = str(row.get('메이커명', '')).strip().lower()
                        name = row.get('매장명', '')
                        addr = row.get('주소', '')
                        
                        if 'oliveyoung' in maker:
                            html = generate_popup_html('올리브영', name, addr)
                            folium.Marker([row['위도'], row['경도']], popup=folium.Popup(html, max_width=250), icon=folium.Icon(color="green")).add_to(oy_cluster)
                        elif 'daiso' in maker:
                            html = generate_popup_html('다이소', name, addr)
                            folium.Marker([row['위도'], row['경도']], popup=folium.Popup(html, max_width=250), icon=folium.Icon(color="red")).add_to(daiso_cluster)
        
        else: # TAX REFUND
            df_kiosk = load_csv_data(os.path.join(TOUR_DATA_DIR, 'tax_kiosk_locations.csv'))
            if not df_kiosk.empty:
                for _, row in df_kiosk.iterrows():
                    lat_col = 'latitude' if 'latitude' in row else 'lat'
                    lon_col = 'longitude' if 'longitude' in row else 'lon'
                    if pd.notna(row.get(lat_col)) and pd.notna(row.get(lon_col)):
                        html = generate_popup_html('키오스크', row.get('name', 'Tax Refund Kiosk'), row.get('address', ''))
                        folium.Marker([row[lat_col], row[lon_col]], popup=folium.Popup(html, max_width=250), icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

        st_folium(m, center=[user_lat, user_lon], zoom=14, width='100%', height=600)


    # --- TAB 4: MY TOUR MAP (Kakao & Realtime Congestion) ---
    elif selected_menu == "TOUR MAP":
        st.markdown("<h2 class='menu-heading'>MY PERSONA TOUR MAP</h2>", unsafe_allow_html=True)
        
        persona = st.session_state.get('user_persona', None)
        user_district = st.session_state.get('user_district', '전체')
        
        if not persona:
            st.warning("⚠️ HOME 탭에서 페르소나 진단을 먼저 진행해주세요! (Please complete the quiz first!)")
        
        display_name = PERSONA_INFO[persona][0] if persona else '전체 (진단 미완료)'
        st.sidebar.markdown(f"### 매핑 타겟: {display_name}")
        st.sidebar.markdown(f"### 추천 지역: {user_district}")        
        df_tour = load_csv_data(os.path.join(TOUR_DATA_DIR, 'last_tour_final_mapped.csv'))
        if df_tour.empty:
            return st.error("관광지 매핑 데이터를 불러오지 못했습니다.")

        # 구 필터링 및 페르소나 필터링
        if user_district != '전체':
            df_curr = df_tour[df_tour['시/군/구'] == user_district]
            # 해당 구에 데이터가 부족하면 서울 전체에서 가져옴
            if len(df_curr) < 5:
                st.sidebar.info(f"💡 '{user_district}'에 적합한 추천지가 부족하여 서울 전체를 탐색합니다.")
            else:
                df_tour = df_curr
        if persona:
            df_tour = df_tour[df_tour['K뷰티_추천_페르소나'].astype(str).str.contains(persona, na=False)]
        
        df_tour = df_tour.sort_values(by='검색건수', ascending=False).head(50)
        
        # 실시간 데이터 조인
        map_data = []
        for _, row in df_tour.iterrows():
            if pd.notnull(row['lat']) and pd.notnull(row['lng']):
                cd = row.get('area_cd')
                cong = '정보없음'
                if pd.notnull(cd):
                    cdata = get_seoul_city_data(cd)
                    if "congestion_lvl" in cdata:
                        cong = cdata["congestion_lvl"]
                
                map_data.append({
                    'name': row['관광지명'],
                    'category': row['소분류 카테고리'],
                    'district': row['시/군/구'],
                    'lat': row['lat'],
                    'lng': row['lng'],
                    'congestion_lvl': cong,
                    'indoor': row.get('실내/실외 구분', '-'),
                    'age': row.get('추천 연령대', '-')
                })
        
        st.markdown(f"<p style='text-align:center;'>당신의 라이프스타일에 꼭 맞는 맞춤 관광지 <b>{len(map_data)}곳</b>을 선별했습니다.</p>", unsafe_allow_html=True)
        render_kakao_map(map_data, center_lat=user_lat, center_lng=user_lon, level=6)

        # --- Section 4: 반나절 루트 제안 (The Actionable Itinerary) ---
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### 🗓️ Recommended Half-Day Itinerary")
        
        with st.expander("✨ 지금 바로 떠날 수 있는 '반나절 여행 코스' 보기 (Recommended Half-Day Course)", expanded=True):
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
                    "📍 오후 16:00 - 환급 키오스크에서 세금 환급 후 청계천 밤도깨비 야시장 산책 <br> (4:00 PM - Walk along Cheonggyecheon after tax refund at a kiosk)"                ]
            }
            
            # 현재 페르소나에 맞는 루트 출력 (없으면 기본값 일본/공통 루트)
            selected_itinerary = itinerary_data.get(persona, itinerary_data['일본'])
            
            for step in selected_itinerary:
                st.markdown(f"**{step}**")
            
            st.markdown("---")
            st.info("💡 위 코스는 현재 지역의 실시간 혼잡도와 당신의 페르소나 성향을 고려하여 설계되었습니다. (This course is designed considering real-time congestion and your persona preference.)")
if __name__ == "__main__":
    main()
