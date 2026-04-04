import os
import sqlite3
import pandas as pd
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_coords(row, api_key):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}

    idx = row.name
    title = str(row.get('postSj', ''))
    area = str(row.get('areaNm', ''))
    tags = str(row.get('tagList', ''))

    queries = []
    if title and title != 'nan':
        queries.append(title)
        queries.append(title.split(' ')[0])
        queries.append(title.split('(')[0].strip())
    
    if tags and tags != 'nan':
        first_tag = tags.split(',')[0].strip()
        if first_tag:
            queries.append(first_tag)

    queries = list(dict.fromkeys(queries))

    for q in queries:
        if not q or len(q) < 2: continue
        search_q = f"서울 {q}"
        try:
            resp = requests.get(url, headers=headers, params={"query": search_q}, timeout=5)
            data = resp.json()
            docs = data.get('documents', [])
            if docs:
                return idx, float(docs[0]['x']), float(docs[0]['y'])
        except Exception:
            pass
    return idx, None, None

def geocode_data():
    api_key = os.getenv("KAKAO_REST_API_KEY", "")
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    csv_path = os.path.join(data_dir, 'tour_data.csv')
    db_path = os.path.join(data_dir, 'tour_data.db')

    print("Loading mapped data...")
    df = pd.read_csv(csv_path)

    if 'lat' not in df.columns:
        df['lat'] = None
    if 'lon' not in df.columns:
        df['lon'] = None

    missing_mask = df['lat'].isna() | (df['lat'] == '')
    indices_to_fetch = df[missing_mask].index.tolist()
    
    print(f"Total locations to geocode: {len(indices_to_fetch)}")
    if len(indices_to_fetch) == 0:
        print("All locations are already geocoded.")
        return

    success_count = 0
    fail_count = 0

    rows_to_process = [df.loc[idx] for idx in indices_to_fetch]

    print("Geocoding in parallel...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_coords, row, api_key) for row in rows_to_process]
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Geocoding"):
            idx, lon, lat = future.result()
            if lon is not None:
                df.at[idx, 'lon'] = lon
                df.at[idx, 'lat'] = lat
                success_count += 1
            else:
                fail_count += 1

    print(f"Geocoding finished. Success: {success_count}, Failed: {fail_count}")

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Saved geocoded CSV: {csv_path}")

    conn = sqlite3.connect(db_path)
    df.to_sql('tour_list', conn, if_exists='replace', index=False)
    conn.close()
    print(f"Saved SQLite DB: {db_path}")

if __name__ == "__main__":
    geocode_data()
