# 라이브러리 추가
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
from concurrent.futures import ThreadPoolExecutor, as_completed 

app = Flask(__name__)

# --- 설정 (Settings) ---
DRIVER_PATH = "./chromedriver"
URL_FILE_NAME = "urls.txt"
ARCHIVE_FOLDER = "archive" 
USER_FOLDER = "user" 
DISPLAY_JSON_FILE = "current_crawl_display_data.json"
# 🚫 OUTPUT_HTML_FILE 상수는 더 이상 사용하지 않지만, 웹페이지 라우트 유지를 위해 임시로 주석 처리
# OUTPUT_HTML_FILE = "miningleague.html" 
# 한번에 5명씩, 실패 시 최대 10번 재시도
MAX_WORKERS = 5 # 순차 처리 강제
MAX_RETRIES = 10 # 재시도 횟수 설정

# --- 헬퍼 함수 (Helper Functions) ---

def _get_player_id_from_url(url):
    """URL에서 플레이어 ID를 추출합니다."""
    match = re.search(r'popup/(\d+)', url)
    return match.group(1) if match else None

def _initialize_driver():
    """Selenium WebDriver를 초기화하고 반환합니다. (안정화 옵션 적용)"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3") 
    options.add_argument("user-agent=Mozilla/50 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(executable_path=DRIVER_PATH, log_path=os.devnull) 
    return webdriver.Chrome(service=service, options=options)

def _read_urls_from_file(filename):
    """urls.txt 파일을 파싱하여 3줄(이름, 스탯URL, 스쿼드URL)을 하나의 그룹으로 묶어 리스트로 반환합니다."""
    managers = []
    if not os.path.exists(filename):
        raise FileNotFoundError(f"'{filename}' 파일을 찾을 수 없습니다.")

    with open(filename, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    it = iter(lines)
    for line1 in it:
        try:
            line2 = next(it)
            line3 = next(it)
            if line1.startswith('//') and 'stat/popup' in line2 and 'squad/popup' in line3:
                player_id = _get_player_id_from_url(line2)
                if player_id:
                    managers.append({
                        "name": line1.replace('//', '').strip(),
                        "player_id": player_id,
                        "stat_url": line2,
                        "squad_url": line3
                    })
        except StopIteration:
            break
    print(f"'{filename}'에서 총 {len(managers)}명의 감독 정보를 로드했습니다.")
    return managers

def _crawl_single_manager(manager_info):
    """한 명의 감독에 대한 모든 정보(전적, 구단가치)를 크롤링합니다."""
    driver = None
    result_data = manager_info.copy()
    
    today_date_iso = datetime.now().strftime("%Y-%m-%d")

    result_data.update({
        "구단주명": "N/A", 
        "승": "N/A", "무": "N/A", "패": "N/A",
        "판수": "N/A", "채굴 효율": "N/A", "승률": "N/A",
        "구단 가치": "0 BP",
        "비고": "-",
        "지난 시즌 승": "N/A", "지난 시즌 무": "N/A", "지난 시즌 패": "N/A",
        "지난 시즌 판수": "N/A", "지난 시즌 채굴 효율": "N/A", "지난 시즌 승률": "N/A",
        "crawl_time": today_date_iso
    })

    print(f"--- [작업] '{manager_info.get('name', 'N/A')}' 감독 처리 시작 ---")

    try:
        driver = _initialize_driver()
        driver.get(result_data['stat_url'])
        
        # 1-1. 구단주명 크롤링
        try:
            coach_name_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.coach"))
            )
            coach_name = coach_name_element.text.strip()
            if coach_name:
                result_data["구단주명"] = coach_name
                print(f" -> '{result_data['구단주명']}' 구단주명 추출 완료.")
        except Exception as e:
            print(f" -> 구단주명 추출 실패: {e}")
            result_data["비고"] = "구단주명 추출 실패"


        # 1-2. 전적 정보 탭 변경 및 크롤링
        league_dropdown_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".select_league .league"))
        )
        league_dropdown_button.click()

        manager_mode_tab = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))
        )

        current_stat_element_before_click = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".season_grade_info__current .grade_desc"))
        )
        old_text = current_stat_element_before_click.text

        manager_mode_tab.click()

        WebDriverWait(driver, 15).until_not(
            EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".season_grade_info__current .grade_desc"), old_text)
        )
        updated_stat_locator = (By.CSS_SELECTOR, ".season_grade_info__current .grade_desc")
        updated_stat_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(updated_stat_locator)
        )
        
        # 지난 시즌 데이터 로딩을 위한 명시적 대기 추가 (안정성 강화)
        last_season_locator = (By.CSS_SELECTOR, ".season_grade_info__last .grade_desc")
        last_season_text = ""
        try:
            WebDriverWait(driver, 10).until(
                EC.text_to_be_present_in_element(last_season_locator, "승") or
                EC.text_to_be_present_in_element(last_season_locator, "패")
            )
            last_season_element = driver.find_element(*last_season_locator)
            last_season_text = last_season_element.text
        except Exception as e:
            print(f" -> '{result_data['구단주명']}' 지난 시즌 데이터 로딩 대기 시간 초과 또는 오류 발생. 바로 추출 시도: {e}")
            try:
                last_season_element = driver.find_element(*last_season_locator)
                last_season_text = last_season_element.text
            except Exception:
                last_season_text = "" 
        
        # 전적 추출 시작
        current_text = updated_stat_element.text
        current_match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패\((\d+\.\d+)%\)', current_text)
        last_season_match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패\((\d+\.\d+)%\)', last_season_text)


        if current_match:
            win, draw, loss, win_rate_val = current_match.groups()
            win, draw, loss = int(win), int(draw), int(loss)
            total_games = win + draw + loss
            
            result_data.update({
                "승": win, "무": draw, "패": loss, "판수": total_games,
                "채굴 효율": win * 7 - draw * 3 - loss,
                "승률": f"{float(win_rate_val):.1f}%"
            })
            
            print(f" -> '{result_data['구단주명']}' 현재 전적 '{current_text}' 추출 완료.")
        else:
            print(f" -> '{result_data['구단주명']}' 현재 전적 추출 실패: 패턴 불일치 또는 데이터 없음.")
            if result_data["비고"] == "-":
                 result_data["비고"] = "전적 데이터 추출 실패"
            
        if last_season_match:
            last_win, last_draw, last_loss, last_win_rate_val = last_season_match.groups()
            last_win, last_draw, last_loss = int(last_win), int(last_draw), int(last_loss)
            last_total_games = last_win + last_draw + last_loss
            result_data.update({
                "지난 시즌 승": last_win, "지난 시즌 무": last_draw, "지난 시즌 패": last_loss,
                "지난 시즌 판수": last_total_games,
                "지난 시즌 채굴 효율": last_win * 7 - last_draw * 3 - last_loss,
                "지난 시즌 승률": f"{float(last_win_rate_val):.1f}%"
            })
            print(f" -> '{result_data['구단주명']}' 지난 시즌 전적 '{last_season_text}' 추출 완료.")
        else:
            print(f" -> '{result_data['구단주명']}' 지난 시즌 전적 추출 실패: 패턴 불일치 또는 데이터 없음. (텍스트: '{last_season_text[:30]}...')")


        # 2. 구단 가치 크롤링 (squad_url)
        driver.get(result_data['squad_url'])
        
        # 2-1. 구단 가치 크롤링
        squad_value_locator = (By.CSS_SELECTOR, "div.squad__info-panel__price p.txt strong")
        WebDriverWait(driver, 15).until(
            EC.text_to_be_present_in_element(squad_value_locator, 'BP')
        )
        squad_value_element = driver.find_element(*squad_value_locator)
        squad_value_text = squad_value_element.text.strip()
        
        match = re.search(r'(\d{1,3}(,\d{3})*조)', squad_value_text)
        if match:
            squad_value = match.group(1)
        else:
            squad_value = squad_value_text.split('BP')[0].strip()
            
        result_data["구단 가치"] = squad_value

        print(f" -> '{result_data['구단주명']}' 구단 가치 '{result_data['구단 가치']}' 추출 완료.")


    except Exception as e:
        print(f" -> '{result_data['구단주명']}' 처리 중 오류 발생: {e}")
        if str(e).strip():
            result_data["error"] = str(e)
        else:
            result_data["error"] = "WebDriver Internal Crash (Empty Message)"
    finally:
        if driver:
            driver.quit()
            # WebDriver 종료 후 OS 리소스 정리를 위한 충분한 지연 시간
            time.sleep(5) 

    return result_data

def _robust_crawl_manager(manager_info):
    """
    재시도 로직: 지정된 횟수(MAX_RETRIES)만큼 _crawl_single_manager를 실행합니다.
    """
    for attempt in range(MAX_RETRIES):
        result = _crawl_single_manager(manager_info)
        
        if "error" not in result:
            return result
        
        print(f" -> '{manager_info.get('name', 'N/A')}' (시도 {attempt + 1}/{MAX_RETRIES}) 크롤링 오류 발생. 5초 후 재시도...")
        if attempt < MAX_RETRIES - 1:
            time.sleep(5)
            
    return result

# --- Flask 라우트 (Flask Routes) ---

@app.route('/')
def index():
    # HTML 페이지는 크롤링 시작 버튼을 제공합니다.
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>FC Online 크롤링 매니저</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 p-8">
        <div class="max-w-4xl mx-auto bg-white p-6 rounded-xl shadow-2xl">
            <h1 class="text-3xl font-bold text-center text-blue-600 mb-6">FC Online 마이닝 리그 크롤러</h1>
            <div id="status-message" class="p-4 rounded-lg text-center mb-6 bg-yellow-100 text-yellow-800 hidden">크롤링을 시작하세요.</div>
            
            <button id="crawl-button" onclick="startCrawl()" class="w-full bg-green-500 hover:bg-green-600 text-white font-bold py-3 px-4 rounded-lg transition duration-200 shadow-md">
                크롤링 시작 (urls.txt 기반)
            </button>
            
            <div class="mt-8 text-center">
                <a href="/results_table" target="_blank" class="text-blue-500 hover:text-blue-700 underline font-semibold">
                    현재 크롤링 결과 테이블 보기 (JSON 기반 렌더링 필요)
                </a>
            </div>

            <script>
                function showMessage(type, message) {
                    const statusDiv = document.getElementById('status-message');
                    statusDiv.textContent = message;
                    statusDiv.classList.remove('hidden', 'bg-red-100', 'text-red-800', 'bg-green-100', 'text-green-800', 'bg-yellow-100', 'text-yellow-800');
                    if (type === 'error') {
                        statusDiv.classList.add('bg-red-100', 'text-red-800');
                    } else if (type === 'success') {
                        statusDiv.classList.add('bg-green-100', 'text-green-800');
                    } else {
                         statusDiv.classList.add('bg-yellow-100', 'text-yellow-800');
                    }
                    statusDiv.classList.remove('hidden');
                }

                async function startCrawl() {
                    const button = document.getElementById('crawl-button');
                    button.disabled = true;
                    button.textContent = '크롤링 진행 중... (순차 처리로 시간이 오래 걸립니다)'; 
                    showMessage('info', '크롤링을 시작합니다. 순차 처리 중이므로 시간이 오래 걸릴 수 있습니다...');

                    try {
                        const response = await fetch('/crawl', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        });
                        
                        const contentType = response.headers.get("content-type");
                        if (!contentType || !contentType.includes("application/json")) {
                            const errorText = await response.text();
                            showMessage('error', '❌ 서버 오류 (HTML 응답 수신): 서버가 JSON 대신 오류 페이지를 반환했습니다. 내용을 확인하세요. ' + errorText.substring(0, 100) + '...');
                            return;
                        }
                        
                        const data = await response.json();

                        if (data.status === 'success') {
                            showMessage('success', '✅ 크롤링 성공: ' + data.message + ' (JSON 파일 업데이트 완료)');
                        } else if (data.status === 'warning') {
                             showMessage('warning', '⚠️ 경고: ' + data.message);
                        } else {
                            showMessage('error', '❌ 크롤링 오류: ' + data.message);
                        }
                    } catch (error) {
                        showMessage('error', '❌ 네트워크 오류 또는 JSON 파싱 오류 발생: ' + error.message);
                    } finally {
                        button.disabled = false;
                        button.textContent = '크롤링 시작 (urls.txt 기반)';
                    }
                }
            </script>
        </div>
    </body>
    </html>
    """

@app.route('/results_table')
def results_table_page():
    try:
        if not os.path.exists(DISPLAY_JSON_FILE):
            return "데이터 없음. 먼저 크롤링을 실행하세요.", 404
        
        with open(DISPLAY_JSON_FILE, 'r', encoding='utf-8') as f:
            display_data = json.load(f)
            # JSON 데이터를 기반으로 HTML을 생성하여 반환합니다.
            return _generate_results_html(display_data)

    except Exception as e:
        return f"결과 테이블 로드 중 오류 발생: {e}", 500

@app.route('/crawl', methods=['POST'])
def crawl_data():
    today_date_str_iso = datetime.now().strftime("%Y-%m-%d") 
    today_date_str_yymmdd = datetime.now().strftime("%y%m%d") 

    ARCHIVE_FILE_NAME = f"{today_date_str_iso}.json" 
    ARCHIVE_PATH = os.path.join(ARCHIVE_FOLDER, ARCHIVE_FILE_NAME)
    
    if not os.path.exists(ARCHIVE_FOLDER):
        os.makedirs(ARCHIVE_FOLDER)

    try:
        managers_to_process = _read_urls_from_file(URL_FILE_NAME)
    except FileNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    if not managers_to_process:
        return jsonify({"status": "warning", "message": "처리할 감독 정보가 없습니다."}), 200

    previous_rank_map = {}
    if os.path.exists(ARCHIVE_PATH):
        try:
            with open(ARCHIVE_PATH, 'r', encoding='utf-8') as f:
                previous_results = json.load(f)
                previous_results.sort(key=lambda x: x.get('채굴 효율', -99999) if isinstance(x.get('채굴 효율'), int) else -99999, reverse=True)
                for i, item in enumerate(previous_results):
                    previous_rank_map[item.get('player_id')] = i + 1
            print(f" -> 아카이브 파일 '{ARCHIVE_FILE_NAME}'을 순위 비교를 위해 로드했습니다.")
        except Exception as e:
            print(f"이전 결과 로드 중 오류 발생: {e}. 이전 순위 비교는 수행하지 않습니다.")


    final_results = []
    
    # 순차 처리 및 재시도 로직 적용
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor: 
        future_to_manager = {executor.submit(_robust_crawl_manager, manager): manager for manager in managers_to_process}
        
        for future in as_completed(future_to_manager):
            result = future.result()
            if "error" in result:
                return jsonify({
                    "status": "error",
                    "message": f"'{result.get('구단주명', 'N/A')}' 처리 중 오류 발생으로 인해 전체 크롤링 작업을 중단합니다. 모든 재시도가 실패했습니다. 최종 오류: {result['error']}"
                }), 500
            
            final_results.append(result)

    # 오류 없이 모든 작업이 성공했을 경우에만 결과 처리 및 저장
    if final_results:
        final_results.sort(key=lambda x: x.get('채굴 효율', -99999) if isinstance(x.get('채굴 효율'), int) else -99999, reverse=True)

        for i, item in enumerate(final_results):
            current_rank = i + 1
            item['순위'] = current_rank 
            player_id = item.get('player_id')
            
            previous_rank = previous_rank_map.get(player_id)
            
            if previous_rank is None:
                item['비고'] = 'New'
            else:
                rank_change = previous_rank - current_rank
                if rank_change > 0:
                    item['비고'] = f'↑{rank_change}'
                elif rank_change < 0:
                    item['비고'] = f'↓{-rank_change}'
                else:
                    item['비고'] = '-'
        
            # 개별 유저 JSON 파일 저장 (순위 포함)
            USER_PLAYER_DIR = os.path.join(USER_FOLDER, player_id) 
            USER_FILE_NAME = f"{player_id}_{today_date_str_yymmdd}.json"         
            USER_FILE_PATH = os.path.join(USER_PLAYER_DIR, USER_FILE_NAME)
            
            if not os.path.exists(USER_PLAYER_DIR):
                os.makedirs(USER_PLAYER_DIR)

            user_record = {
                "crawl_time": item.get('crawl_time'), 
                "순위": item.get('순위'),             
                "구단주명": item.get('구단주명'),
                "승": item.get('승'), "무": item.get('무'), "패": item.get('패'),
                "판수": item.get('판수'), "채굴 효율": item.get('채굴 효율'), "승률": item.get('승률'),
                "구단 가치": item.get('구단 가치'),
            }
            
            try:
                with open(USER_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump([user_record], f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f" -> '{item.get('구단주명')}' 개별 기록 저장 중 오류 발생: {e}")
        
        crawled_results_with_ranks = final_results.copy()
        
        # 지난 시즌 최고 기록 계산 로직 (유지)
        mining_king = None
        win_rate_king = None
        game_count_king = None
        draw_king = None
        
        if final_results:
            mining_king = max(final_results, key=lambda x: x.get('지난 시즌 채굴 효율', -1) if isinstance(x.get('지난 시즌 채굴 효율'), int) else -1, default=None)
            
            def get_win_rate_float(x):
                try:
                    return float(x.get('지난 시즌 승률', '0%').replace('%', ''))
                except ValueError:
                    return 0.0

            win_rate_king = max(final_results, key=get_win_rate_float, default=None)
            game_count_king = max(final_results, key=lambda x: x.get('지난 시즌 판수', -1) if isinstance(x.get('지난 시즌 판수'), int) else -1, default=None)
            draw_king_candidates = [res for res in final_results if isinstance(res.get('지난 시즌 판수'), int) and res['지난 시즌 판수'] >= 4000]
            if draw_king_candidates:
                draw_king = min(draw_king_candidates, key=lambda x: x.get('지난 시즌 무', 9999), default=None)

        display_data = {
            "results": crawled_results_with_ranks,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mining_king": mining_king,
            "win_rate_king": win_rate_king,
            "game_count_king": game_count_king,
            "draw_king": draw_king
        }
        
        try:
            # 1. JSON 파일 아카이브 저장 (yyyy-mm-dd.json)
            with open(ARCHIVE_PATH, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, indent=4, ensure_ascii=False)
            
            # 2. DISPLAY JSON 파일 저장 (웹 표시용)
            with open(DISPLAY_JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(display_data, f, indent=4, ensure_ascii=False)

        except Exception as e:
            print(f"파일 저장 중 오류: {e}")
            return jsonify({"status": "error", "message": f"파일 저장 중 오류: {e}"}), 500

        success_count = len(final_results)
        fail_count = len(managers_to_process) - success_count
        
        return jsonify({
            "status": "success",
            "message": f"총 {len(managers_to_process)}명 중 {success_count}명 성공, {fail_count}명 실패. JSON 파일 업데이트 완료."
        })

    return jsonify({
        "status": "error",
        "message": "모든 크롤링 작업이 오류로 인해 완료되지 않았습니다."
    }), 500

def _generate_results_html(display_data):
    """
    크롤링 결과를 표시할 HTML 테이블을 생성합니다.
    (results_table 라우트에서 즉석으로 HTML을 생성하는 용도로 사용)
    """
    
    results = display_data['results']
    last_updated = display_data['last_updated']
    
    def get_king_info(king, key):
        return king.get('구단주명', 'N/A') if king and king.get(key) not in ["N/A", "0 BP", "추출 실패"] else 'N/A'

    mining_king_name = get_king_info(display_data.get('mining_king'), '지난 시즌 채굴 효율')
    win_rate_king_name = get_king_info(display_data.get('win_rate_king'), '지난 시즌 승률')
    game_count_king_name = get_king_info(display_data.get('game_count_king'), '지난 시즌 판수')
    draw_king_name = get_king_info(display_data.get('draw_king'), '지난 시즌 무')


    table_rows = ""
    success_count = 0
    fail_count = 0

    if results:
        for item in results:
            if item.get("error"):
                fail_count += 1
            else:
                success_count += 1

            row_class = ""
            remark_class = ""
            
            remark = item.get('비고', '-')
            if item.get("error"):
                row_class = "error-row"
            elif remark.startswith('↑') or remark == 'New':
                remark_class = "rank-up"
            elif remark.startswith('↓'):
                remark_class = "rank-down"
            elif remark == '-':
                remark_class = "rank-no-change"
            
            table_rows += f"""
            <tr class="{row_class}">
                <td class="col-rank">{item.get('순위', '-')}</td>
                <td class="col-remark {remark_class}">{remark}</td>
                <td class="col-owner-name">{item.get('구단주명', 'N/A')}</td>
                <td>{item.get('판수', 0)}</td>
                <td class="col-win-lose">{item.get('승', 'N/A')}</td>
                <td class="col-win-lose">{item.get('무', 'N/A')}</td>
                <td class="col-win-lose">{item.get('패', 'N/A')}</td>
                <td class="col-record">
                    <span class="current-record">{item.get('승', 'N/A')} / {item.get('무', 'N/A')} / {item.get('패', 'N/A')}</span>
                    <span class="last-record" style="display:none;">{item.get('지난 시즌 승', 'N/A')} / {item.get('지난 시즌 무', 'N/A')} / {item.get('지난 시즌 패', 'N/A')}</span>
                </td>
                <td>
                    <span class="current-mining">{item.get('채굴 효율', 0)}</span>
                    <span class="last-mining" style="display:none;">{item.get('지난 시즌 채굴 효율', 'N/A')}</span>
                </td>
                <td>
                    <span class="current-winrate">{item.get('승률', 'N/A')}</span>
                    <span class="last-winrate" style="display:none;">{item.get('지난 시즌 승률', 'N/A')}</span>
                </td>
                <td class="col-club-value">{item.get('구단 가치', '0 BP')}</td>
            </tr>
            """
    else:
        table_rows = """
            <tr>
                <td colspan="11">표시할 결과가 없습니다. 메인 페이지에서 크롤링을 시작해주세요.</td>
            </tr>
        """
        
    summary_message = f"총 {len(results)}개 중 {success_count}개 성공, {fail_count}개 실패." if results else "크롤링된 데이터가 없습니다."

    html_content = f"""
<!DOCTYPE html>
<html lang="ko">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>ESCLUB</title>
        <link rel="stylesheet" href="/static/style.css" />

        <meta property="og:url" content="https://esclub.dothome.co.kr/miningleague.html" />
        <meta property="og:title" content="ES클럽 채굴리그" />
        <meta property="og:type" content="website" />
        <meta property="og:description" content="ES클럽 감독모드 채굴리그" />
    </head>
    <body>
        <div class="container">
            <h1>ES클럽 채굴리그 (통합)</h1>
            <p>크롤링된 데이터를 기반으로 계산된 통합 전적 표입니다.</p>

            <div class="kings-section">
                <h2>지난 시즌 최고 기록</h2>
                <div class="kings-grid">
                    <div class="king-card">
                        <h3>🏆 채굴왕</h3>
                        <p><strong>{mining_king_name}</strong></p>
                        <p>{display_data.get('mining_king', {}).get('지난 시즌 채굴 효율', 'N/A')} 효율</p>
                    </div>
                    <div class="king-card">
                        <h3>👑 승률왕</h3>
                        <p><strong>{win_rate_king_name}</strong></p>
                        <p>{display_data.get('win_rate_king', {}).get('지난 시즌 승률', 'N/A')}</p>
                    </div>
                    <div class="king-card">
                        <h3>🥇 판수왕</h3>
                        <p><strong>{game_count_king_name}</strong></p>
                        <p>{display_data.get('game_count_king', {}).get('지난 시즌 판수', 'N/A')} 판</p>
                    </div>
                    <div class="king-card">
                        <h3>🔥 승부왕</h3>
                        <p><strong>{draw_king_name}</strong></p>
                        <p>{display_data.get('draw_king', {}).get('지난 시즌 무', 'N/A')} 무승부</p>
                    </div>
                </div>
            </div>

            <div class="league-section">
                <h2>전체 결과</h2>
                <div class="table-responsive">
                    <table id="mainTable">
                        <thead>
                            <tr>
                                <th class="col-rank sortable" data-sort-key="순위">순위<span class="sort-icon"></span></th>
                                <th class="col-remark">비고</th>
                                <th class="col-owner-name">구단주명</th>
                                <th class="sortable" data-sort-key="판수">판수<span class="sort-icon"></span></th>
                                <th class="col-win-lose">승</th>
                                <th class="col-win-lose">무</th>
                                <th class="col-win-lose">패</th>
                                <th class="col-record">전적</th>
                                <th class="sortable" data-sort-key="채굴 효율">채굴 효율<span class="sort-icon"></span></th>
                                <th class="sortable" data-sort-key="승률">승률<span class="sort-icon"></span></th>
                                <th class="col-club-value sortable" data-sort-key="구단 가치">구단가치<span class="sort-icon"></span></th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
                <p id="main_summary_message" class="update-info">
                    {summary_message}
                </p>
            </div>

            <p class="update-info" id="lastUpdatedInfo">데이터 마지막 최신화: {last_updated}</p>
            <p class="update-info" id="copyrightInfo">사이트 내 FC온라인 관련 모든 정보의 저작권은 EA Sports 및 NEXON에 있습니다.</p>
        </div>

        <script src="/static/results_table.js"></script>
    </body>
</html>
    """
    return html_content


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)