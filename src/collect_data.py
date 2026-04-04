import os
import sqlite3
import pandas as pd
import requests
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

FILTERS = {
    'Age': {
        '10대': 'AGE_GROUP_1', '20대': 'AGE_GROUP_2', '30대': 'AGE_GROUP_3',
        '40대': 'AGE_GROUP_4', '50대': 'AGE_GROUP_5', '60대 이상': 'AGE_GROUP_6'
    },
    'Companion': {
        '가족': 'GO_WITH_3', '무장애관광': 'GO_WITH_8', '반려동물 동반 (보조동물 제외)': 'GO_WITH_7',
        '부모': 'GO_WITH_5', '아이동반 (영유아, 어린이)': 'GO_WITH_6', '친구': 'GO_WITH_1',
        '커플/부부': 'GO_WITH_2', '혼자': 'GO_WITH_4'
    },
    'Theme': {
        'SNS 핫플': 'THEME_15', '경관/포토스팟': 'THEME_1', '나들이': 'THEME_4', '드라이브': 'THEME_9',
        '로맨틱': 'THEME_14', '문화/예술': 'THEME_6', '문화유적지 (역사투어)': 'THEME_5', '쇼핑': 'THEME_10',
        '식도락': 'THEME_2', '실내': 'THEME_16', '실외': 'THEME_17', '액티비티': 'THEME_7',
        '체험관광 (자녀체험)': 'THEME_8', '캠핑': 'THEME_12', '한강': 'THEME_13', '한류': 'THEME_11', '휴식/힐링': 'THEME_3'
    },
    'Season': {
        '봄': 'PERIOD_MOMENT_1', '여름': 'PERIOD_MOMENT_2', '가을': 'PERIOD_MOMENT_3',
        '겨울': 'PERIOD_MOMENT_4', '연중 (사계절)': 'PERIOD_MOMENT_5'
    }
}

base_url = "https://korean.visitseoul.net/comm/curation/ajax/postList"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://korean.visitseoul.net/curation",
    "X-Requested-With": "XMLHttpRequest",
}

def fetch_page(opt_val, page, cat_type, cat_name):
    try:
        payload = {"curPage": page, "type": "All", "optionList": opt_val, "langCodeId": "ko"}
        r = requests.post(base_url, headers=headers, data=payload, timeout=10)
        items = r.json().get("listVO", {}).get("listObject", [])
        return (cat_type, cat_name, items)
    except Exception:
        return (cat_type, cat_name, [])

def collect_data():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, 'tour_data.csv')
    db_path = os.path.join(data_dir, 'tour_data.db')
    
    if os.path.exists(csv_path):
        print("Existing CSV found. Loading base data...")
        df_base = pd.read_csv(csv_path)
        all_items_df = df_base.copy()
    else:
        print("Base CSV required but not found. Please ensure tour_data.csv exists.")
        return

    post_mappings = {}
    
    def add_map(post_sn, cat_type, cat_name):
        if post_sn not in post_mappings:
            post_mappings[post_sn] = {'Age': set(), 'Companion': set(), 'Theme': set(), 'Season': set()}
        post_mappings[post_sn][cat_type].add(cat_name)

    # First, get total pages for all filters
    print("Pre-fetching total pages for all filters...")
    tasks = []
    
    for cat_type, options in FILTERS.items():
        for cat_name, opt_val in options.items():
            payload = {"curPage": 1, "type": "All", "optionList": opt_val, "langCodeId": "ko"}
            try:
                r = requests.post(base_url, headers=headers, data=payload, timeout=10)
                f_total_page = r.json().get("listVO", {}).get("totalPage", 0)
                for page in range(1, int(f_total_page) + 1):
                    tasks.append((opt_val, page, cat_type, cat_name))
            except Exception as e:
                pass

    print(f"Total API pages to fetch across all categories: {len(tasks)}")
    
    start_time = time.time()
    # Multithreading fetch
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(fetch_page, *task) for task in tasks]
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Fetching Mappings in Parallel"):
            cat_type, cat_name, items = future.result()
            for item in items:
                sn = item.get("postSn")
                if sn:
                    add_map(sn, cat_type, cat_name)

    print(f"Mapping fetch completed in {time.time() - start_time:.2f} seconds.")
    print("Merging mapping columns into dataframe...")
    
    all_items_df['postSn_str'] = all_items_df['postSn'].astype(str)
    
    age_map, comp_map, theme_map, sea_map = {}, {}, {}, {}
    for sn, m in post_mappings.items():
        sn_str = str(sn)
        age_map[sn_str] = ', '.join(sorted(m['Age']))
        comp_map[sn_str] = ', '.join(sorted(m['Companion']))
        theme_map[sn_str] = ', '.join(sorted(m['Theme']))
        sea_map[sn_str] = ', '.join(sorted(m['Season']))

    all_items_df['연령대'] = all_items_df['postSn_str'].map(age_map).fillna('')
    all_items_df['일행'] = all_items_df['postSn_str'].map(comp_map).fillna('')
    all_items_df['테마'] = all_items_df['postSn_str'].map(theme_map).fillna('')
    all_items_df['시기'] = all_items_df['postSn_str'].map(sea_map).fillna('')
    
    all_items_df.drop(columns=['postSn_str'], inplace=True, errors='ignore')

    print(f"Final Mapped Columns: {['연령대', '일행', '테마', '시기']}")
    all_items_df.dropna(axis=1, how='all', inplace=True)
    nunique = all_items_df.nunique(dropna=False)
    cols_to_drop = nunique[nunique == 1].index
    all_items_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

    before_dup = len(all_items_df)
    all_items_df = all_items_df.loc[all_items_df.astype(str).drop_duplicates().index]
    print(f"Dropped duplicates. Old: {before_dup}, New: {len(all_items_df)}")
    print(f"Final row count: {len(all_items_df)}")
    
    all_items_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Saved FULL mapped CSV: {csv_path}")
    
    conn = sqlite3.connect(db_path)
    all_items_df.to_sql('tour_list', conn, if_exists='replace', index=False)
    conn.close()
    print(f"Saved SQLite DB: {db_path}")

if __name__ == "__main__":
    collect_data()
