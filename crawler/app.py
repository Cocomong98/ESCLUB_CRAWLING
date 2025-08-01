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
MAX_WORKERS = 5

# -------------------------------------------------------------
# 헬퍼 함수: URL에서 플레이어 ID 추출 (예: '1155593160' 부분)
def _get_player_id_from_url(url):
    match = re.search(r'popup/(\d+)', url)
    if match:
        return match.group(1)
    return None

# -------------------------------------------------------------
# 헬퍼 함수: 이전 결과 JSON 파일을 로드하고 모든 데이터를 반환 (업데이트 로직을 위해)
def _load_all_previous_data(json_file_path):
    previous_data = {} # {player_id: {data}, ...}
    if os.path.exists(json_file_path):
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                player_id = item.get('player_id')
                if player_id:
                    previous_data[player_id] = item
        except json.JSONDecodeError as e:
            print(f"경고: 이전 JSON 파일을 읽는 중 오류 발생 (파일 손상?): {e}")
        except Exception as e:
            print(f"경고: 이전 결과 로드 중 알 수 없는 오류 발생: {e}")
    return previous_data

# -------------------------------------------------------------
# 헬퍼 함수: Selenium 드라이버 초기화 (Headless 모드 등 옵션 포함)
def _initialize_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(executable_path=DRIVER_PATH)
    return webdriver.Chrome(service=service, options=options)

# -------------------------------------------------------------
# 헬퍼 함수: URL 파일 읽기 (주석 포함)
def _read_urls_from_file(filename):
    urls_with_annotation = []
    current_annotation = ""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"'{filename}' 파일을 찾을 수 없습니다.")

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            if stripped_line.startswith('//'):
                current_annotation = stripped_line[2:].strip()
            elif stripped_line.startswith('#'):
                current_annotation = stripped_line[1:].strip()
            elif stripped_line.startswith('http://') or stripped_line.startswith('https://'):
                urls_with_annotation.append((stripped_line, current_annotation))
                current_annotation = ""
            else:
                print(f"경고 ({filename}): 알 수 없는 형식의 줄이 발견되었습니다: {stripped_line}")
    return urls_with_annotation

# -------------------------------------------------------------
# 단일 URL을 크롤링하는 함수 (각 스레드에서 실행될 예정)
def _crawl_single_url(item_to_process):
    url = item_to_process['url']
    annotation = item_to_process['annotation']
    
    driver = None
    
    player_id = _get_player_id_from_url(url)
    current_url_data = {
        "URL": url,
        "player_id": player_id,
        "주석": annotation,
        "구단주명": "N/A",
        "승": "N/A", "무": "N/A", "패": "N/A",
        "판수": "N/A", "채굴 효율": "N/A", "승률": "N/A",
        "비고": "-"
    }
    
    print(f"--- [스레드-{os.getpid()}] 처리 시작: {url} ---")
    
    try:
        driver = _initialize_driver()
        driver.get(url)
        
        WebDriverWait(driver, 10 + 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "selector_wrap"))
        )

        league_selector_link = WebDriverWait(driver, 5 + 5).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "league"))
        )
        league_selector_link.click()
        time.sleep(1 + 5)

        manager_mode_tab = WebDriverWait(driver, 5 + 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))
        )
        manager_mode_tab.click()
        time.sleep(10 + 5)

        grade_desc_element = WebDriverWait(driver, 10 + 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "grade_desc"))
        )
        full_text = grade_desc_element.text
        match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패', full_text)

        if match:
            win = int(match.group(1))
            draw = int(match.group(2))
            loss = int(match.group(3))
            
            total_games = win + draw + loss
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
            current_url_data["error"] = "전적 정보 찾기 실패"

        coach_name_element = WebDriverWait(driver, 5 + 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "coach"))
        )
        current_url_data["구단주명"] = coach_name_element.text
        
    except Exception as e:
        print(f"  [스레드-{os.getpid()}] URL({url}) 처리 중 오류 발생: {e}")
        current_url_data["error"] = str(e)
    
    finally:
        if driver:
            driver.quit()
    
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
    urls_file = "urls.txt"

    # 이전 결과 로드 (업데이트 및 순위 비교를 위해 모든 데이터 로드)
    previous_data_by_id = _load_all_previous_data(OUTPUT_JSON_FILE)
    previous_ranks = {}
    if previous_data_by_id:
        # 순위 비교를 위한 이전 순위 맵 생성
        sorted_previous_data = sorted(
            [item for item in previous_data_by_id.values() if "error" not in item],
            key=lambda x: (
                x.get('채굴 효율', -float('inf')) if isinstance(x.get('채굴 효율'), (int, float)) else -float('inf'),
                x.get('player_id', '')
            ),
            reverse=True
        )
        previous_ranks = {item['player_id']: rank for rank, item in enumerate(sorted_previous_data, 1)}
        print(f"이전 결과 ({len(previous_data_by_id)}명) 로드 완료. 순위 비교를 수행합니다.")
    else:
        print("이전 결과 파일이 없거나 읽을 수 없습니다. 새로운 순위로 기록됩니다.")

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
    
    all_urls_to_process = []
    for url_tuple in urls_data:
        all_urls_to_process.append({"url": url_tuple[0], "annotation": url_tuple[1]}) 

    total_urls_count = len(all_urls_to_process)
    if total_urls_count == 0:
         return jsonify({"status": "warning", "message": "유효한 URL이 없습니다."}), 200

    print(f"웹 요청을 받았습니다. 총 {total_urls_count}개의 URL을 로드했습니다. {MAX_WORKERS}개씩 병렬 처리 시작.")

    crawled_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for result in executor.map(_crawl_single_url, all_urls_to_process):
            crawled_results.append(result)

    # -------------------------------------------------------------
    # 새로운 데이터와 기존 데이터 비교 및 업데이트 로직
    # -------------------------------------------------------------
    updated_results_map = {}
    
    # 1. 기존 데이터(이전 크롤링 결과)를 먼저 맵에 채움
    for item in previous_data_by_id.values():
        updated_results_map[item['player_id']] = item

    # 2. 크롤링한 데이터(새로운 크롤링 결과)로 맵을 업데이트
    #    (채굴 효율이 더 높은 경우에만 업데이트)
    for new_item in crawled_results:
        player_id = new_item.get('player_id')
        if not player_id:
            # player_id가 없는 데이터는 건너뜀
            continue

        if "error" in new_item:
            # 새로운 크롤링 결과에 오류가 있다면 기존 데이터를 유지 (덮어쓰지 않음)
            # 만약 기존 데이터도 없다면, 오류 데이터만 기록
            if player_id not in updated_results_map:
                updated_results_map[player_id] = new_item
            continue

        # 기존 데이터와 비교
        if player_id in updated_results_map:
            prev_item = updated_results_map[player_id]
            # 채굴 효율이 숫자인지 확인 후 비교
            prev_efficiency = prev_item.get('채굴 효율')
            new_efficiency = new_item.get('채굴 효율')
            
            is_prev_valid = isinstance(prev_efficiency, (int, float))
            is_new_valid = isinstance(new_efficiency, (int, float))
            
            # 이전 데이터가 유효하지 않으면 새 데이터로 무조건 업데이트
            if not is_prev_valid:
                updated_results_map[player_id] = new_item
            # 이전 데이터와 새로운 데이터가 모두 유효하면, 더 높은 값으로 업데이트
            elif is_prev_valid and is_new_valid and new_efficiency > prev_efficiency:
                updated_results_map[player_id] = new_item
            # 그 외의 경우 (새로운 데이터가 더 낮거나, 동점이거나)는 기존 데이터 유지
        else:
            # 기존 데이터에 없는 새로운 플레이어면 추가
            updated_results_map[player_id] = new_item
    
    all_combined_results = list(updated_results_map.values())
    
    # 순위 비교 및 '비고' 필드 계산 (통합 순위 계산)
    print("\n=== 순위 비교 및 '비고' 필드 계산 시작 (통합) ===")
    
    final_processed_results = []
    
    current_ranked_data = sorted(
        [item for item in all_combined_results if "error" not in item],
        key=lambda x: (
            x.get('채굴 효율', -float('inf')) if isinstance(x.get('채굴 효율'), (int, float)) else -float('inf'),
            x.get('player_id', '')
        ),
        reverse=True
    )
    
    current_ranks_map = {item['player_id']: rank for rank, item in enumerate(current_ranked_data, 1)}

    for item in all_combined_results:
        if "error" not in item and item['player_id'] in current_ranks_map:
            current_rank = current_ranks_map[item['player_id']]
            if item['player_id'] in previous_ranks:
                prev_rank = previous_ranks[item['player_id']]
                rank_diff = prev_rank - current_rank
                if rank_diff > 0:
                    item['비고'] = f"↑{rank_diff}"
                elif rank_diff < 0:
                    item['비고'] = f"↓{abs(rank_diff)}"
                else:
                    item['비고'] = "-"
            else:
                item['비고'] = "New"
        else:
            item['비고'] = "오류"

        final_processed_results.append(item)
    
    final_processed_results.sort(
        key=lambda x: (
            x.get('채굴 효율', -float('inf')) if isinstance(x.get('채굴 효율'), (int, float)) else -float('inf'),
            x.get('player_id', '')
        ),
        reverse=True
    )

    success_count = sum(1 for item in final_processed_results if "error" not in item)
    fail_count = total_urls_count - success_count

    # -------------------------------------------------------------
    # 1. JSON 파일 저장
    output_data_for_json = [] 
    for item in final_processed_results:
        json_item = {
            "player_id": item.get("player_id"),
            "구단주명": item.get("구단주명"), 
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

    return jsonify({
        "status": "success",
        "message": f"총 {total_urls_count}개 URL 중 {success_count}개 성공, {fail_count}개 실패.",
        "results": final_processed_results,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
