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

app = Flask(__name__)

# 웹드라이버 경로 (app.py와 같은 폴더에 있다고 가정)
DRIVER_PATH = "./chromedriver"

# 결과 저장 파일 경로 (app.py와 같은 폴더에 저장)
OUTPUT_JSON_FILE = "fconline_manager_stats.json"

# 웹 페이지의 초기 로딩을 위한 라우트
@app.route('/')
def index():
    return render_template('index.html')

# 크롤링 요청을 처리할 API 라우트
@app.route('/crawl', methods=['POST'])
def crawl_data():
    # -------------------------------------------------------------
    # urls.txt 파일에서 URL 목록 읽어오기 (기존 로직 재사용)
    # -------------------------------------------------------------
    url_file_name = "urls.txt"
    target_urls = []

    if not os.path.exists(url_file_name):
        return jsonify({"status": "error", "message": f"'{url_file_name}' 파일을 서버에서 찾을 수 없습니다."}), 500

    try:
        with open(url_file_name, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    target_urls.append(url)
    except Exception as e:
        return jsonify({"status": "error", "message": f"URL 파일을 읽는 중 오류 발생: {str(e)}"}), 500

    if not target_urls:
        return jsonify({"status": "warning", "message": f"'{url_file_name}' 파일에 유효한 URL이 없습니다."}), 200

    print(f"웹 요청을 받았습니다. '{url_file_name}'에서 총 {len(target_urls)}개의 URL을 로드했습니다.")

    # -------------------------------------------------------------
    # Selenium 크롤링 로직 시작
    # -------------------------------------------------------------

    all_results = []
    success_count = 0
    fail_count = 0
    total_urls_count = len(target_urls) # 총 URL 개수

    driver = None
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        service = Service(executable_path=DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)

        # enumerate를 사용하여 순번(index)을 가져옵니다.
        for index, url in enumerate(target_urls):
            # -------------------------------------------------------------
            # 터미널에 현재 처리 중인 순번 표시
            print(f"\n--- URL 처리 시작: {index + 1}/{total_urls_count} - {url} ---")
            # -------------------------------------------------------------

            current_url_data = {
                "URL": url, # 웹 페이지 결과 표시를 위해 URL은 포함 (JSON 저장 시에만 제외)
                "구단주명": "N/A",
                "승": "N/A",
                "무": "N/A",
                "패": "N/A"
            }
            url_processed_successfully = False
            
            try:
                driver.get(url)

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "selector_wrap"))
                )
                print(f"{index + 1}/{total_urls_count} - 프로필 팝업 로드 완료.")

                league_selector_link = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "league"))
                )
                league_selector_link.click()
                print(f"{index + 1}/{total_urls_count} - 드롭다운 펼침 완료.")
                time.sleep(1)

                manager_mode_tab = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))
                )
                manager_mode_tab.click()
                print(f"{index + 1}/{total_urls_count} - 감독 모드 탭 클릭 완료.")

                print(f"{index + 1}/{total_urls_count} - 감독 모드 데이터 로딩을 위해 10초 대기합니다...")
                time.sleep(10)

                grade_desc_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "grade_desc"))
                )
                full_text = grade_desc_element.text
                match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패', full_text)

                if match:
                    current_url_data["승"] = int(match.group(1))
                    current_url_data["무"] = int(match.group(2))
                    current_url_data["패"] = int(match.group(3))
                else:
                    print(f"{index + 1}/{total_urls_count} - 전적 정보를 찾을 수 없습니다.")

                coach_name_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "coach"))
                )
                current_url_data["구단주명"] = coach_name_element.text
                print(f"{index + 1}/{total_urls_count} - 구단주명 추출 완료.")
                
                url_processed_successfully = True

            except Exception as e:
                print(f"URL({url}) 처리 중 오류 발생: {e}")
                current_url_data["error"] = str(e)
                fail_count += 1

            all_results.append(current_url_data)

            if url_processed_successfully:
                success_count += 1
        
    except Exception as e:
        print(f"크롤링 스크립트 실행 중 치명적인 오류 발생: {e}")
        return jsonify({"status": "error", "message": f"크롤링 중 치명적인 오류 발생: {str(e)}", "results": all_results}), 500

    finally:
        if driver:
            driver.quit()

    # -------------------------------------------------------------
    # JSON 파일 저장 로직
    # -------------------------------------------------------------
    output_data_for_json = []
    for item in all_results:
        json_item = {k: v for k, v in item.items() if k != "URL"} # JSON 저장 시 URL 필드 제외
        output_data_for_json.append(json_item)

    try:
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data_for_json, f, indent=4, ensure_ascii=False)
        print(f"\n모든 데이터가 '{OUTPUT_JSON_FILE}' 파일에 성공적으로 저장되었습니다. (기존 파일 덮어쓰기)")
    except Exception as e:
        print(f"JSON 파일 저장 중 오류 발생: {e}")

    # 최종 결과를 웹 응답으로 반환
    return jsonify({
        "status": "success",
        "message": f"총 {total_urls_count}개 URL 중 {success_count}개 성공, {fail_count}개 실패.",
        "results": all_results
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)