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

# --- 설정 ---
DRIVER_PATH = "./chromedriver"
URL_FILE_NAME = "urls.txt"
OUTPUT_JSON_FILE = "fconline_manager_stats.json"

def parse_urls(filename):
    """
    urls.txt 파일을 파싱하여 3줄(이름, 스탯URL, 스쿼드URL)을 하나의 그룹으로 묶어 리스트로 반환합니다.
    """
    managers = []
    if not os.path.exists(filename):
        print(f"오류: '{filename}' 파일을 찾을 수 없습니다.")
        return managers

    with open(filename, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    it = iter(lines)
    for line1 in it:
        try:
            line2 = next(it)
            line3 = next(it)
            if line1.startswith('//') and 'stat/popup' in line2 and 'squad/popup' in line3:
                user_code_match = re.search(r'/(\d+)$', line2)
                if user_code_match:
                    user_code = user_code_match.group(1)
                    managers.append({
                        "name": line1.replace('//', '').strip(),
                        "user_code": user_code,
                        "stat_url": line2,
                        "squad_url": line3
                    })
        except StopIteration:
            break
    
    print(f"'{filename}'에서 총 {len(managers)}명의 감독 정보를 로드했습니다.")
    return managers

def scrape_stat_data(driver, stat_url):
    """
    감독모드 전적 페이지에서 승, 무, 패 정보를 스크래핑합니다.
    """
    try:
        print(f"전적 정보 처리 중... ({stat_url})")
        driver.get(stat_url)
        
        # 리그 버튼 클릭
        league_selector_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "league"))
        )
        league_selector_link.click()
        
        # 감독 모드 탭 클릭
        manager_mode_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))
        )
        manager_mode_tab.click()
        
        # 전적 정보가 로드될 때까지 대기
        grade_desc_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "grade_desc"))
        )
        
        # time.sleep을 WebDriverWait으로 대체하여 안정성 향상
        WebDriverWait(driver, 10).until(
            lambda d: re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패', d.find_element(By.CLASS_NAME, "grade_desc").text)
        )

        full_text = driver.find_element(By.CLASS_NAME, "grade_desc").text
        match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패', full_text)

        if match:
            return {
                "승": int(match.group(1)),
                "무": int(match.group(2)),
                "패": int(match.group(3)),
            }
    except Exception as e:
        print(f"전적 정보 처리 중 오류 발생: {e}")
    return None

def scrape_squad_value(driver, squad_url):
    """
    스쿼드 가치 페이지에서 구단 가치 정보를 스크래핑합니다.
    대기 조건을 강화하여 안정성을 높입니다.
    """
    try:
        print(f"스쿼드 가치 처리 중... ({squad_url})")
        driver.get(squad_url)
        
        # "BP"라는 텍스트가 나타날 때까지 대기 (조건 강화)
        squad_value_element = WebDriverWait(driver, 15).until(
            EC.text_to_be_present_in_element(
                (By.CSS_SELECTOR, "div.squad__info-panel__price p.txt strong"), 'BP'
            )
        )
        squad_value = squad_value_element.text.strip()
        print(f"-> 구단 가치 '{squad_value}' 추출 완료.")
        return squad_value
    except Exception as e:
        print(f"-> 구단 가치 추출 실패: {e}")
    return "0 BP" # 실패 시 기본값

def main():
    managers = parse_urls(URL_FILE_NAME)
    if not managers:
        return

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    
    service = Service(executable_path=DRIVER_PATH)
    driver = None
    
    all_results = []
    success_count = 0
    fail_count = 0

    try:
        driver = webdriver.Chrome(service=service, options=options)
        
        for manager in managers:
            print(f"\n--- '{manager['name']}' 감독 처리 시작 ---")
            
            stat_data = scrape_stat_data(driver, manager['stat_url'])
            squad_value = scrape_squad_value(driver, manager['squad_url'])

            if stat_data:
                result = {
                    "구단주명": manager['name'],
                    "승": stat_data.get("승", "N/A"),
                    "무": stat_data.get("무", "N/A"),
                    "패": stat_data.get("패", "N/A"),
                    "구단 가치": squad_value
                }
                all_results.append(result)
                success_count += 1
            else:
                fail_count += 1

    except Exception as e:
        print(f"스크립트 실행 중 치명적인 오류 발생: {e}")
    finally:
        if driver:
            driver.quit()
        print("\n--- 크롤링 완료 ---")

    # --- 최종 결과 저장 ---
    try:
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=4, ensure_ascii=False)
        print(f"\n모든 데이터가 '{OUTPUT_JSON_FILE}' 파일에 성공적으로 저장되었습니다.")
    except Exception as e:
        print(f"JSON 파일 저장 중 오류 발생: {e}")

    # --- 요약 보고 ---
    print("\n--- 크롤링 요약 ---")
    print(f"총 감독 수: {len(managers)}")
    print(f"성공: {success_count}")
    print(f"실패: {fail_count}")
    print("------------------")

if __name__ == "__main__":
    main()
