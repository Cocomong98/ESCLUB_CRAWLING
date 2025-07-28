from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# 웹드라이버 경로 (app.py와 같은 폴더에 있다고 가정)
DRIVER_PATH = "./chromedriver"

# 결과 저장 파일 경로 (다음 회차 비교를 위한 데이터)
OUTPUT_JSON_FILE = "fconline_manager_stats.json"

# 웹 페이지 표시용 임시 데이터 파일 (서버가 HTML을 렌더링할 때 사용)
DISPLAY_JSON_FILE = "current_crawl_display_data.json"

# 렌더링된 HTML 페이지를 파일로 저장할 경로
OUTPUT_HTML_FILE = "fconline_manager_stats.html"

# 동시에 실행할 크롤링 작업 수
MAX_WORKERS = 11

# -------------------------------------------------------------
# 헬퍼 함수: URL에서 플레이어 ID 추출 (예: '1155593160' 부분)
def _get_player_id_from_url(url):
    match = re.search(r'popup/(\d+)', url)
    if match:
        return match.group(1)
    return None

# -------------------------------------------------------------
# 헬퍼 함수: 이전 결과 JSON 파일을 로드하고 플레이어 ID별 과거 순위 딕셔너리 반환 (통합)
def _load_previous_results(json_file_path):
    previous_ranks = {} # {player_id: rank, ...}
    if os.path.exists(json_file_path):
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                previous_data_combined = json.load(f)
            
            # 이전 데이터를 채굴 효율 기준으로 정렬하여 과거 순위 맵 생성
            sorted_previous_data = sorted(
                [item for item in previous_data_combined if "error" not in item], # 오류 없는 항목만 순위 산정에 포함
                key=lambda x: (
                    x.get('채굴 효율', -float('inf')) if isinstance(x.get('채굴 효율'), (int, float)) else -float('inf'),
                    x.get('player_id', '') 
                ),
                reverse=True
            )
            
            for rank, item in enumerate(sorted_previous_data, 1):
                if 'player_id' in item:
                    previous_ranks[item['player_id']] = rank
        except json.JSONDecodeError as e:
            print(f"경고: 이전 JSON 파일을 읽는 중 오류 발생 (파일 손상?): {e}")
        except Exception as e:
            print(f"경고: 이전 결과 로드 중 알 수 없는 오류 발생: {e}")
    return previous_ranks

# -------------------------------------------------------------
# 헬퍼 함수: Selenium 드라이버 초기화 (Headless 모드 등 옵션 포함)
def _initialize_driver():
    options = Options()
    options.add_argument("--headless")         # 브라우저 창을 띄우지 않음
    options.add_argument("--disable-gpu")      # GPU 사용 비활성화 (Headless 모드에서 권장)
    options.add_argument("--window-size=1920x1080") # 창 크기 설정 (Headless에서도 유효)
    options.add_argument("--no-sandbox")       # Docker 또는 일부 서버 환경에서 필요
    options.add_argument("--disable-dev-shm-usage") # Docker 또는 일부 서버 환경에서 필요
    service = Service(executable_path=DRIVER_PATH)
    return webdriver.Chrome(service=service, options=options)

# -------------------------------------------------------------
# 헬퍼 함수: URL 파일 읽기 (주석 포함) (하나의 파일에서 읽도록 수정)
def _read_urls_from_file(filename):
    urls_with_annotation = []
    current_annotation = ""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"'{filename}' 파일을 찾을 수 없습니다.")

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            stripped_line = line.strip()
            if not stripped_line: # 빈 줄 건너뛰기
                continue
            if stripped_line.startswith('//'): # "//"로 시작하면 각주로 간주
                current_annotation = stripped_line[2:].strip() # "//" 제거 후 공백 제거
            elif stripped_line.startswith('#'): # 혹시 파이썬 스타일 주석도 처리하고 싶다면
                current_annotation = stripped_line[1:].strip()
            elif stripped_line.startswith('http://') or stripped_line.startswith('https://'):
                urls_with_annotation.append((stripped_line, current_annotation))
                current_annotation = "" # URL을 처리했으니 현재 각주 초기화
            else: # 예상치 못한 형식의 줄 (무시하거나 오류 처리)
                print(f"경고 ({filename}): 알 수 없는 형식의 줄이 발견되었습니다: {stripped_line}")
    return urls_with_annotation

# -------------------------------------------------------------
# 단일 URL을 크롤링하는 함수 (각 스레드에서 실행될 예정)
def _crawl_single_url(item_to_process):
    url = item_to_process['url']
    annotation = item_to_process['annotation']
    # league_name은 더 이상 사용하지 않음 (통합이므로)
    
    driver = None # 드라이버 초기화
    
    player_id = _get_player_id_from_url(url)
    current_url_data = {
        # "리그명": league_name, # 리그명 필드 제거 또는 '통합' 등으로 변경 가능
        "URL": url,
        "player_id": player_id,
        "주석": annotation,
        "구단주명": "N/A",
        "승": "N/A", "무": "N/A", "패": "N/A",
        "판수": "N/A", "채굴 효율": "N/A", "승률": "N/A",
        "비고": "-" # 비고 초기값
    }
    
    print(f"--- [스레드-{os.getpid()}] 처리 시작: {url} ---")
    
    try:
        driver = _initialize_driver() # 각 스레드에서 독립적인 드라이버 인스턴스 생성
        driver.get(url)
        
        # 웹페이지 요소 로딩 및 클릭 (WebDriverWait 사용)
        WebDriverWait(driver, 10 + 5).until( # 5초 추가
            EC.presence_of_element_located((By.CLASS_NAME, "selector_wrap"))
        )
        # print(f"  [스레드-{os.getpid()}] 프로필 팝업 로드 완료.")

        league_selector_link = WebDriverWait(driver, 5 + 5).until( # 5초 추가
            EC.element_to_be_clickable((By.CLASS_NAME, "league"))
        )
        league_selector_link.click()
        # print(f"  [스레드-{os.getpid()}] 드롭다운 펼침 완료.")
        time.sleep(1 + 5) # 5초 추가

        manager_mode_tab = WebDriverWait(driver, 5 + 5).until( # 5초 추가
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))
        )
        manager_mode_tab.click()
        # print(f"  [스레드-{os.getpid()}] 감독 모드 탭 클릭 완료.")

        # print(f"  [스레드-{os.getpid()}] 감독 모드 데이터 로딩을 위해 10초 대기합니다...")
        time.sleep(10 + 5) # 5초 추가

        grade_desc_element = WebDriverWait(driver, 10 + 5).until( # 5초 추가
            EC.presence_of_element_located((By.CLASS_NAME, "grade_desc"))
        )
        full_text = grade_desc_element.text
        match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패', full_text)

        if match:
            win = int(match.group(1))
            draw = int(match.group(2))
            loss = int(match.group(3))
            
            total_games = win + draw + loss
            # 채굴 효율 공식 수정 반영: 승리*7 - 무승부*3 - 패배
            mining_efficiency = win * 7 - draw * 3 - loss 
            win_rate = (win / total_games * 100) if total_games > 0 else 0.0
            
            current_url_data["승"] = win
            current_url_data["무"] = draw
            current_url_data["패"] = loss
            current_url_data["판수"] = total_games
            current_url_data["채굴 효율"] = mining_efficiency
            current_url_data["승률"] = f"{win_rate:.2f}%"
        else:
            print(f"  [스레드-{os.getpid()}] 전적 정보를 찾을 수 없습니다.")

        coach_name_element = WebDriverWait(driver, 5 + 5).until( # 5초 추가
            EC.presence_of_element_located((By.CLASS_NAME, "coach"))
        )
        current_url_data["구단주명"] = coach_name_element.text
        # print(f"  [스레드-{os.getpid()}] 구단주명 추출 완료.")
        
    except Exception as e:
        # 오류 발생 시 오류 메시지 저장
        print(f"  [스레드-{os.getpid()}] URL({url}) 처리 중 오류 발생: {e}")
        current_url_data["error"] = str(e)
    
    finally: # 각 스레드에서 사용한 드라이버는 반드시 종료
        if driver:
            driver.quit()
            # print(f"  [스레드-{os.getpid()}] 드라이버 종료.")
    
    return current_url_data

# -------------------------------------------------------------
# 웹 페이지의 초기 로딩을 위한 라우트
@app.route('/')
def index():
    return render_template('index.html')

# 결과 테이블 페이지 라우트 (데이터를 파일에서 읽어와 렌더링)
@app.route('/results_table')
def results_table_page():
    try:
        if os.path.exists(DISPLAY_JSON_FILE):
            with open(DISPLAY_JSON_FILE, 'r', encoding='utf-8') as f:
                display_data = json.load(f)
            
            results = display_data.get('results', [])
            last_updated = display_data.get('last_updated', '정보 없음')
            
            return render_template('results_table.html', results=results, last_updated=last_updated)
        else:
            return render_template('results_table.html', results=[], last_updated='데이터 없음', message='크롤링된 데이터 파일이 없습니다.')
    except json.JSONDecodeError as e:
        return render_template('results_table.html', results=[], last_updated='오류', message=f'데이터 파일 손상: {e}')
    except Exception as e:
        return render_template('results_table.html', results=[], last_updated='오류', message=f'데이터 로드 중 알 수 없는 오류: {e}')


# 크롤링 요청을 처리할 API 라우트
@app.route('/crawl', methods=['POST'])
def crawl_data():
    urls_file = "urls.txt" # 단일 URL 파일

    # 이전 결과 로드 (순위 비교를 위해)
    previous_ranks = _load_previous_results(OUTPUT_JSON_FILE) # 이제 통합 순위 맵
    if previous_ranks:
        print(f"이전 결과 ({len(previous_ranks)}명) 로드 완료. 순위 비교를 수행합니다.")
    else:
        print("이전 결과 파일이 없거나 읽을 수 없습니다. 새로운 순위로 기록됩니다.")

    # URL 파일에서 데이터 읽기
    urls_data = []
    try:
        urls_data = _read_urls_from_file(urls_file)
        if not urls_data: print(f"경고: '{urls_file}' 파일에 유효한 URL이 없습니다.")
    except FileNotFoundError as e:
        print(f"오류: {e}")
        return jsonify({"status": "error", "message": f"{urls_file} 파일을 찾을 수 없습니다."}), 500
    except Exception as e:
        print(f"오류: {e}")
        return jsonify({"status": "error", "message": f"{urls_file} 파일 읽기 오류: {str(e)}"}), 500
    
    # 모든 URL을 단일 통합 리스트로 준비
    all_urls_to_process = []
    for url_tuple in urls_data:
        # 통합이므로 리그명은 제거하고, 필요하면 '통합' 등으로 고정 가능
        all_urls_to_process.append({"url": url_tuple[0], "annotation": url_tuple[1]}) 

    total_urls_count = len(all_urls_to_process)
    if total_urls_count == 0:
         return jsonify({"status": "warning", "message": "유효한 URL이 없습니다."}), 200

    print(f"웹 요청을 받았습니다. 총 {total_urls_count}개의 URL을 로드했습니다. {MAX_WORKERS}개씩 병렬 처리 시작.")

    all_combined_results = [] # 각 URL별 스크랩된 원시 데이터를 저장 (순위 비교 전)
    
    # ThreadPoolExecutor를 사용하여 MAX_WORKERS 만큼의 워커(스레드)로 작업을 병렬 실행
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for result in executor.map(_crawl_single_url, all_urls_to_process):
            all_combined_results.append(result)

    # 순위 비교 및 '비고' 필드 계산 (통합 순위 계산)
    print("\n=== 순위 비교 및 '비고' 필드 계산 시작 (통합) ===")
    
    final_processed_results = [] # 순위 비교 후 최종적으로 프론트엔드로 보낼 데이터
    
    # 현재 데이터의 순위를 계산 (오류 없는 항목만 순위 산정에 포함)
    current_ranked_data = sorted(
        [item for item in all_combined_results if "error" not in item],
        key=lambda x: (
            x.get('채굴 효율', -float('inf')) if isinstance(x.get('채굴 효율'), (int, float)) else -float('inf'),
            x.get('player_id', '') # 채굴 효율 동점 시 player_id로 순서 고정
        ),
        reverse=True # 채굴 효율은 내림차순 (높을수록 상위)
    )
    
    current_ranks_map = {item['player_id']: rank for rank, item in enumerate(current_ranked_data, 1)}

    for item in all_combined_results: # 원본 데이터(오류 포함)를 순회하며 비고 채우기
        if "error" not in item and item['player_id'] in current_ranks_map:
            current_rank = current_ranks_map[item['player_id']]
            
            # 이전 순위가 있다면 비교
            if item['player_id'] in previous_ranks: # 통합 순위 맵 사용
                prev_rank = previous_ranks[item['player_id']]
                rank_diff = prev_rank - current_rank # 양수면 상승, 음수면 하락
                if rank_diff > 0:
                    item['비고'] = f"↑{rank_diff}"
                elif rank_diff < 0:
                    item['비고'] = f"↓{abs(rank_diff)}"
                else:
                    item['비고'] = "-"
            else:
                item['비고'] = "New" # 이전 결과에 없는 새로운 플레이어
        else:
            item['비고'] = "오류" # 크롤링 중 오류가 발생했거나, 순위 계산에서 제외된 항목

        final_processed_results.append(item)
    
    # 최종적으로 웹에 표시할 데이터를 채굴 효율 기준으로 한 번 더 정렬
    final_processed_results.sort(
        key=lambda x: (
            x.get('채굴 효율', -float('inf')) if isinstance(x.get('채굴 효율'), (int, float)) else -float('inf'),
            x.get('player_id', '')
        ),
        reverse=True
    )

    # 전체 성공/실패 카운트 계산
    success_count = sum(1 for item in all_combined_results if "error" not in item)
    fail_count = total_urls_count - success_count

    # -------------------------------------------------------------
    # 1. JSON 파일 저장 (다음 회차 비교를 위한 최소한의 데이터)
    output_data_for_json = [] 
    for item in final_processed_results:
        json_item = {
            "player_id": item.get("player_id"),
            "구단주명": item.get("구단주명"), 
            # "리그명": item.get("리그명"), # 리그명 제거
            "승": item.get("승"),
            "무": item.get("무"),
            "패": item.get("패"),
            "판수": item.get("판수"),
            "채굴 효율": item.get("채굴 효율"),
            "승률": item.get("승률")
        }
        if "error" in item: 
            json_item["error"] = item["error"]
        output_data_for_json.append(json_item)

    try:
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data_for_json, f, indent=4, ensure_ascii=False)
        print(f"\n모든 데이터가 '{OUTPUT_JSON_FILE}' 파일에 성공적으로 저장되었습니다. (기존 파일 덮어쓰기)")
    except Exception as e:
        print(f"JSON 파일 저장 중 오류 발생: {e}")
    # -------------------------------------------------------------

    # -------------------------------------------------------------
    # 2. 웹 페이지 표시용 데이터 JSON 파일 저장
    display_data_for_web = {
        "results": final_processed_results, 
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        with open(DISPLAY_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(display_data_for_web, f, indent=4, ensure_ascii=False)
        print(f"웹 페이지 표시용 데이터가 '{DISPLAY_JSON_FILE}' 파일에 저장되었습니다.")
    except Exception as e:
        print(f"웹 페이지 표시용 데이터 파일 저장 중 오류 발생: {e}")
    # -------------------------------------------------------------

    # -------------------------------------------------------------
    # 3. 렌더링된 HTML 페이지를 파일로 저장
    try:
        rendered_html = render_template('results_table.html', 
                                         results=display_data_for_web['results'], 
                                         last_updated=display_data_for_web['last_updated'])
        
        with open(OUTPUT_HTML_FILE, 'w', encoding='utf-8') as f: 
            f.write(rendered_html)
        print(f"렌더링된 HTML 페이지가 '{OUTPUT_HTML_FILE}' 파일에 저장되었습니다. (기존 파일 덮어쓰기)")
    except Exception as e:
        print(f"HTML 파일 저장 중 오류 발생: {e}")
    # -------------------------------------------------------------

    # 최종 결과를 웹 응답으로 반환
    return jsonify({
        "status": "success",
        "message": f"총 {total_urls_count}개 URL 중 {success_count}개 성공, {fail_count}개 실패.",
        "results": final_processed_results,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
