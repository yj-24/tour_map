import pandas as pd
import os

def get_matching_personas(row):
    cat = str(row.get('소분류 카테고리', ''))
    name = str(row.get('관광지명', ''))
    matched = []
    
    # 1. 중국 (효능 중심 프리미엄 케어파) 
    # 방한 목적: 백화점·쇼핑몰 중심, 전시시설, 공연시설 연계
    if cat in ['백화점', '쇼핑몰', '면세점', '전시시설', '공연시설']:
        matched.append('중국')
        
    # 2. 일본 (저자극 장벽 케어파)
    # 방한 목적: 쇼핑몰·백화점 중심, 전시시설, 기타문화관광지
    if cat in ['쇼핑몰', '백화점', '전시시설', '기타문화관광지']:
        matched.append('일본')
        
    # 3. 대만 (모공·쿨링 밸런스 케어파)
    # 방한 목적: 도시공원, 시장, 체험관광기타 연계
    if cat in ['도시공원', '시장', '체험관광기타']:
        matched.append('대만')
        
    # 4. 미국 (즉각적 광채 추구미)
    # 방한 목적: 쇼핑몰 중심, 테마공원·복합문화공간, 전시시설 연계
    if cat in ['쇼핑몰', '테마공원', '복합관광시설', '전시시설']:
        matched.append('미국')
        
    # 5. 홍콩 (멀티태스킹 케어파)
    # 방한 목적: 백화점·쇼핑몰, 공연시설, 복합상업시설 연계
    if cat in ['백화점', '쇼핑몰', '공연시설', '복합관광시설']:
        matched.append('홍콩')
        
    # ----- 이름(명칭) 기반 형태소 보정 (Fallback) -----
    if not matched:  # 소분류로 하나도 안 잡힌 경우 명칭 텍스트로 추가 할당
        if '공원' in name or '둘레길' in name or '유원지' in name:
            matched.append('대만')
        elif '시장' in name or '상가' in name:
            matched.append('대만')
        elif '갤러리' in name or '미술관' in name or '박물관' in name:
            matched.extend(['중국', '일본', '미국'])
        elif '테마' in name or '월드' in name or '파크' in name or '스튜디오' in name:
            matched.extend(['미국', '홍콩'])
        elif '쇼핑' in name or '아울렛' in name or '몰' in name:
            matched.extend(['중국', '일본', '미국', '홍콩'])
        else:
            # 아예 분류가 안 되는 일반 장소들 (산, 하천, 교통시설 등)
            matched.append('공통(전체)')
            
    # 중복 제거 후 콤마 텍스트로 반환 (스트림릿에서 str.contains 로 필터링하기 편하게)
    matched = list(dict.fromkeys(matched)) # 순서 유지하면서 중복 제거
    return ", ".join(matched)

def main():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    input_csv = os.path.join(DATA_DIR, 'last_tour_enriched.csv')
    output_csv = os.path.join(DATA_DIR, 'last_tour_final_mapped.csv')
    
    print(f"Reading data from: {input_csv}")
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print("파일이 존재하지 않습니다.")
        return
        
    print("최종 확정된 페르소나 5종 (중,일,대,미,홍) 다중 매핑 진행 중...")
    
    # K뷰티_페르소나 다중 할당 컬럼 생성
    df['K뷰티_추천_페르소나'] = df.apply(get_matching_personas, axis=1)
    
    # CSV 저장
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"성공! 최종 매핑 완료 파일을 저장했습니다: {output_csv}\n")
    
    # 간단한 통계 로직 (어떤 페르소나가 가장 많은 관광지와 연결되었는지)
    print("📊 [각 페르소나별 연결된 관광지 총 노출 개수]")
    persona_counts = {'중국':0, '일본':0, '대만':0, '미국':0, '홍콩':0, '공통(전체)':0}
    
    for row_val in df['K뷰티_추천_페르소나']:
        for p in persona_counts.keys():
            if p in row_val:
                persona_counts[p] += 1
                
    for k, v in persona_counts.items():
        print(f" - {k}: {v}곳 추천 가능")

if __name__ == '__main__':
    main()
