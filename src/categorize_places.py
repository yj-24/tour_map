import pandas as pd
import os

def classify_indoor_outdoor(row):
    sub_cat = str(row.get('소분류 카테고리', ''))
    name = str(row.get('관광지명', ''))
    
    # 1. 키워드 기반 우선 매핑 (명칭에 실내외 특성이 강한 단어 포함 여부)
    if any(keyword in name for keyword in ['실내', '아쿠아리움', '백화점', '쇼핑몰', '극장', '센터', '회관', '키즈카페']):
        return '실내'
    if any(keyword in name for keyword in ['공원', '유수지', '야구장', '축구장', '해수욕장', '수영장(야외)', '광장', '둘레길', '시장']):
        # 하지만 일부 시장은 실내(아케이드)일 수 있음. 여기선 실외 기반 혼합으로 처리되도록 패스.
        pass
        
    # 2. 소분류 카테고리 기반 매핑
    indoor_cats = ['백화점', '쇼핑몰', '대형마트', '면세점', '전시시설', '공연시설', '웰니스관광', '공예체험']
    outdoor_cats = ['자연경관(하천/해양)', '자연경관(산)', '자연공원', '도시공원', '역사유적지', '역사유물', '육상레저스포츠']
    
    if sub_cat in indoor_cats:
        return '실내'
    elif sub_cat in outdoor_cats:
        return '실외'
    else:
        # 시장, 테마공원, 종교성지, 복합관광시설, 교통시설, 기타문화관광지 등
        return '혼합'

def classify_age_group(row):
    sub_cat = str(row.get('소분류 카테고리', ''))
    name = str(row.get('관광지명', ''))
    
    # 1. 1020 키워드 (데이트, 팝업, 핫플)
    if any(k in name for k in ['홍대', '성수', '이태원', '팝업', 'DDP', '디자인플라자', '가로수길', '카페거리', '방탈출']):
        return '1020세대'
    if sub_cat in ['데이트코스', '기타문화관광지']:
        return '1020세대'
        
    # 2. 3040 키워드 (어린이, 가족 쇼핑, 테마파크, 체험)
    if any(k in name for k in ['어린이', '키즈', '상상나라', '아울렛', '아쿠아리움', '가족', '공원', '테마파크', '플라자']):
        return '3040세대'
    if sub_cat in ['백화점', '대형마트', '쇼핑몰', '테마공원', '전시시설', '체험관광기타']:
        return '3040세대'
        
    # 3. 5060+ 키워드 (전통시장, 사찰, 등산, 힐링)
    if any(k in name for k in ['농수산물', '재래시장', '약령', '둘레길', '온천', '폭포', '사찰', '절']):
        return '5060세대'
    if sub_cat in ['시장', '자연경관(산)', '역사유적지', '역사유물', '종교성지']:
        return '5060세대'
        
    # 4. 공통 (그 외 지역은 전연령으로 판단)
    return '전연령'

def main():
    # 데이터 경로 설정
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    input_csv = os.path.join(DATA_DIR, 'last_tour_filtered.csv')
    output_csv = os.path.join(DATA_DIR, 'last_tour_enriched.csv')
    
    print(f"Reading {input_csv} ...")
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print("CSV 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        return
        
    # 새로운 컬럼 생성 (Apply 매핑)
    print("Applying Indoor/Outdoor classification ...")
    df['실내/실외 구분'] = df.apply(classify_indoor_outdoor, axis=1)
    
    print("Applying Age Group recommendation ...")
    df['추천 연령대'] = df.apply(classify_age_group, axis=1)
    
    # 저장
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"Successfully saved enriched data to {output_csv}")
    
    # 일부 통계 요약 출력
    print("\n[요약: 실내/실외 구분 분포]")
    print(df['실내/실외 구분'].value_counts())
    print("\n[요약: 추천 연령대 분포]")
    print(df['추천 연령대'].value_counts())

if __name__ == '__main__':
    main()
