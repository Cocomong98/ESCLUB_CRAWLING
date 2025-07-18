from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options # Options 모듈 임포트 추가
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import os
import json

# 웹드라이버 경로
driver_path = "./chromedriver"

# -------------------------------------------------------------
# 처리할 URL 목록을 파일에서 읽어오기
# -------------------------------------------------------------
url_file_name = "urls.txt"
target_urls = []

if not os.path.exists(url_file_name):
    print(f"오류: '{url_file_name}' 파일을 찾을 수 없습니다. 파일을 생성하고 URL을 입력해 주세요.")
    exit()

try:
    with open(url_file_name, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url:
                target_urls.append(url)
except Exception as e:
    print(f"URL 파일을 읽는 중 오류 발생: {e}")
    exit()

if not target_urls:
    print(f"경고: '{url_file_name}' 파일에 유효한 URL이 없습니다.")
    exit()

print(f"'{url_file_name}'에서 총 {len(target_urls)}개의 URL을 로드했습니다.")

# -------------------------------------------------------------
# 모든 URL에서 추출된 결과를 저장할 리스트 초기화
all_results = []
# 결과 요약 변수 추가
success_count = 0
fail_count = 0
# -------------------------------------------------------------

try:
    # -------------------------------------------------------------
    # Headless 모드 설정 추가
    options = Options()
    options.add_argument("--headless")         # 브라우저 창을 띄우지 않음
    options.add_argument("--disable-gpu")      # GPU 사용 비활성화 (Headless 모드에서 권장)
    options.add_argument("--window-size=1920x1080") # 창 크기 설정 (Headless에서도 유효)
    # -------------------------------------------------------------

    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options) # options 적용

    for url in target_urls:
        print(f"\n--- URL 처리 시작: {url} ---")

        current_url_data = {
            "구단주명": "N/A",
            "승": "N/A",
            "무": "N/A",
            "패": "N/A"
        }
        
        # -------------------------------------------------------------
        # 각 URL 처리 성공 여부 트래킹
        url_processed_successfully = False
        # -------------------------------------------------------------

        print("FC 온라인 프로필 페이지로 이동합니다...")
        try: # 전체 크롤링 로직을 다시 한 번 try-except로 감싸서 특정 URL 실패 시 스킵 및 카운트
            driver.get(url)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "selector_wrap"))
            )
            print("프로필 팝업이 로드되었습니다.")

            print("리그 선택 드롭다운을 펼칩니다...")
            league_selector_link = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "league"))
            )
            league_selector_link.click()
            print("드롭다운이 펼쳐졌습니다.")

            time.sleep(1)

            print("감독 모드 탭을 찾고 클릭합니다...")
            manager_mode_tab = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))
            )
            manager_mode_tab.click()
            print("감독 모드 탭을 클릭했습니다.")

            print("감독 모드 데이터 로딩을 위해 10초 대기합니다...") # 이전 요청대로 10초 유지
            time.sleep(10) # 10초 대기 (고정)

            # -------------------------------------------------------------
            # 4. '감독 모드' 선택 후 보이는 승/무/패 정보 가져오기
            # -------------------------------------------------------------
            print("감독 모드 전적 정보 추출 중...")
            # grade_desc_element의 WebDriverWait 대기 시간을 1초에서 10초로 다시 늘립니다.
            # 데이터 로딩 후 요소가 나타나는 시간은 충분히 주어야 합니다.
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
                print("전적 정보를 찾을 수 없습니다.")

            # -------------------------------------------------------------
            # 5. 구단주명 가져오기
            # -------------------------------------------------------------
            print("구단주명 추출 중...")
            # coach_name_element의 WebDriverWait 대기 시간을 1초에서 5초로 다시 늘립니다.
            coach_name_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "coach"))
            )
            current_url_data["구단주명"] = coach_name_element.text

            url_processed_successfully = True # 이 URL 처리 성공으로 표시

        except Exception as e:
            print(f"URL({url}) 처리 중 오류 발생: {e}")
            # 이 URL에 대한 데이터는 기본값인 N/A로 남거나, 오류 메시지를 추가할 수 있습니다.
            current_url_data["error"] = str(e) # 오류 메시지 저장
            fail_count += 1
            # continue # 오류가 나면 다음 URL로 넘어가기 (이 바깥 try-except가 처리)


        # 최종 결과 출력 (콘솔)
        print("\n--- FC 온라인 감독모드 전적 결과 ---")
        print(f"URL: {url}") # URL은 터미널 출력용으로만 남겨둠
        print(f"구단주명: {current_url_data['구단주명']}")
        print(f"승: {current_url_data['승']}")
        print(f"무: {current_url_data['무']}")
        print(f"패: {current_url_data['패']}")
        if "error" in current_url_data:
            print(f"오류: {current_url_data['error']}")
        print("----------------------------------")

        # 현재 URL의 결과 데이터를 all_results 리스트에 추가
        all_results.append(current_url_data)

        if url_processed_successfully:
            success_count += 1 # 성공 카운트 증가


except Exception as e:
    print(f"스크립트 실행 중 치명적인 오류 발생: {e}")

finally:
    print("\n모든 URL 처리 완료. 브라우저를 닫습니다.")
    if 'driver' in locals():
        driver.quit()

    # -------------------------------------------------------------
    # 추출된 모든 데이터를 JSON 파일로 저장 (기존 파일 자동 덮어쓰기)
    # -------------------------------------------------------------
    output_json_file = "fconline_manager_stats.json"
    try:
        with open(output_json_file, 'w', encoding='utf-8') as f: # 'w' 모드는 항상 덮어씁니다.
            json.dump(all_results, f, indent=4, ensure_ascii=False)
        print(f"\n모든 데이터가 '{output_json_file}' 파일에 성공적으로 저장되었습니다. (기존 파일 덮어쓰기)")
    except Exception as e:
        print(f"JSON 파일 저장 중 오류 발생: {e}")

    # -------------------------------------------------------------
    # 종합 결과 보고
    print("\n--- 크롤링 요약 ---")
    print(f"총 처리 요청 URL 수: {len(target_urls)}")
    print(f"성공적으로 처리된 URL 수: {success_count}")
    print(f"처리 실패한 URL 수: {fail_count}")
    print("------------------")