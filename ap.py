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



# --- 설정 ---

DRIVER_PATH = "./chromedriver"

URL_FILE_NAME = "urls.txt"

OUTPUT_JSON_FILE = "fconline_manager_stats.json"

DISPLAY_JSON_FILE = "current_crawl_display_data.json"

OUTPUT_HTML_FILE = "miningleague.html"

MAX_WORKERS = 5



# --- 헬퍼 함수 ---



def _get_player_id_from_url(url):

match = re.search(r'popup/(\d+)', url)

return match.group(1) if match else None



def _initialize_driver():

options = Options()

options.add_argument("--headless")

options.add_argument("--disable-gpu")

options.add_argument("--window-size=1920x1080")

options.add_argument("--no-sandbox")

options.add_argument("--disable-dev-shm-usage")

service = Service(executable_path=DRIVER_PATH)

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



# def _crawl_single_manager(manager_info):

# """한 명의 감독에 대한 모든 정보(전적, 구단가치)를 크롤링합니다."""

# driver = None

# result_data = manager_info.copy()

# result_data.update({

# "구단주명": manager_info.get('name', "N/A"),

# "승": "N/A", "무": "N/A", "패": "N/A",

# "판수": "N/A", "채굴 효율": "N/A", "승률": "N/A",

# "구단 가치": "0 BP",

# "비고": "-",

# "지난 시즌 승": "N/A", "지난 시즌 무": "N/A", "지난 시즌 패": "N/A",

# "지난 시즌 판수": "N/A", "지난 시즌 채굴 효율": "N/A", "지난 시즌 승률": "N/A"

# })



# print(f"--- [스레드] '{result_data['구단주명']}' 감독 처리 시작 ---")



# try:

# driver = _initialize_driver()


# # 1. 감독모드 전적 크롤링

# driver.get(result_data['stat_url'])



# # "공식 경기" 버튼이 클릭 가능할 때까지 기다렸다가 클릭

# league_button = WebDriverWait(driver, 15).until(

# EC.element_to_be_clickable((By.CLASS_NAME, "league"))

# )

# league_button.click()



# # "감독 모드" 탭이 클릭 가능할 때까지 기다렸다가 클릭

# manager_mode_tab = WebDriverWait(driver, 15).until(

# EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))

# )

# manager_mode_tab.click()



# # 전적 정보가 나타날 때까지 기다림

# current_season_element = WebDriverWait(driver, 15).until(

# EC.presence_of_element_located((By.CSS_SELECTOR, ".season_grade_info__current .grade_desc"))

# )

# current_text = current_season_element.text

# current_match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패\((\d+\.\d+)%\)', current_text)



# if current_match:

# win, draw, loss, win_rate_val = current_match.groups()

# win, draw, loss = int(win), int(draw), int(loss)

# total_games = win + draw + loss

# result_data.update({

# "승": win, "무": draw, "패": loss, "판수": total_games,

# "채굴 효율": win * 7 - draw * 3 - loss,

# "승률": f"{float(win_rate_val):.1f}%"

# })



# # 2. 구단 가치 크롤링

# driver.get(result_data['squad_url'])

# squad_value_locator = (By.CSS_SELECTOR, "div.squad__info-panel__price p.txt strong")

# WebDriverWait(driver, 15).until(

# EC.text_to_be_present_in_element(squad_value_locator, 'BP')

# )

# squad_value_element = driver.find_element(*squad_value_locator)

# result_data["구단 가치"] = squad_value_element.text.strip()

# print(f" -> '{result_data['구단주명']}' 구단 가치 '{result_data['구단 가치']}' 추출 완료.")



# except Exception as e:

# print(f" -> '{result_data['구단주명']}' 처리 중 오류 발생: {e}")

# result_data["error"] = str(e)

# finally:

# if driver:

# driver.quit()


# return result_data



# --- Flask 라우트 ---



def _crawl_single_manager(manager_info):

"""한 명의 감독에 대한 모든 정보(전적, 구단가치)를 크롤링합니다."""

driver = None

result_data = manager_info.copy()

result_data.update({

"구단주명": manager_info.get('name', "N/A"),

"승": "N/A", "무": "N/A", "패": "N/A",

"판수": "N/A", "채굴 효율": "N/A", "승률": "N/A",

"구단 가치": "0 BP",

"비고": "-",

"지난 시즌 승": "N/A", "지난 시즌 무": "N/A", "지난 시즌 패": "N/A",

"지난 시즌 판수": "N/A", "지난 시즌 채굴 효율": "N/A", "지난 시즌 승률": "N/A"

})



print(f"--- [스레드] '{result_data['구단주명']}' 감독 처리 시작 ---")



try:

driver = _initialize_driver()


# 1. 감독모드 전적 크롤링

driver.get(result_data['stat_url'])



# "공식 경기 1 ON 1" 버튼이 클릭 가능할 때까지 기다린 후 클릭

league_dropdown_button = WebDriverWait(driver, 15).until(

EC.element_to_be_clickable((By.CSS_SELECTOR, ".select_league .league"))

)

league_dropdown_button.click()



# "감독 모드" 탭 요소를 찾기

manager_mode_tab = WebDriverWait(driver, 15).until(

EC.element_to_be_clickable((By.CSS_SELECTOR, "a[onclick='SetType(52);']"))

)


# 현재 전적 정보의 텍스트를 미리 저장해둡니다.

# 이 텍스트가 변경될 때까지 기다리는 것이 핵심입니다.

current_stat_element_before_click = WebDriverWait(driver, 5).until(

EC.presence_of_element_located((By.CSS_SELECTOR, ".season_grade_info__current .grade_desc"))

)

old_text = current_stat_element_before_click.text


# "감독 모드" 탭 클릭

manager_mode_tab.click()



# 전적 정보가 나타날 때까지 기다림 (텍스트가 이전과 달라질 때까지)

WebDriverWait(driver, 15).until_not(

EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".season_grade_info__current .grade_desc"), old_text)

)


# 업데이트된 전적 정보 추출

updated_stat_element = WebDriverWait(driver, 15).until(

EC.presence_of_element_located((By.CSS_SELECTOR, ".season_grade_info__current .grade_desc"))

)

current_text = updated_stat_element.text

current_match = re.search(r'(\d+)승\s*(\d+)무\s*(\d+)패\((\d+\.\d+)%\)', current_text)



if current_match:

win, draw, loss, win_rate_val = current_match.groups()

win, draw, loss = int(win), int(draw), int(loss)

total_games = win + draw + loss

result_data.update({

"승": win, "무": draw, "패": loss, "판수": total_games,

"채굴 효율": win * 7 - draw * 3 - loss,

"승률": f"{float(win_rate_val):.1f}%"

})

print(f" -> '{result_data['구단주명']}' 전적 '{current_text}' 추출 완료.")

else:

print(f" -> '{result_data['구단주명']}' 전적 추출 실패: 패턴 불일치 또는 데이터 없음.")

result_data["비고"] = "전적 데이터 추출 실패"


# 2. 구단 가치 크롤링

# 전적 크롤링이 완료된 후에 구단 가치 페이지로 이동합니다.

driver.get(result_data['squad_url'])

squad_value_locator = (By.CSS_SELECTOR, "div.squad__info-panel__price p.txt strong")

WebDriverWait(driver, 15).until(

EC.text_to_be_present_in_element(squad_value_locator, 'BP')

)

squad_value_element = driver.find_element(*squad_value_locator)

result_data["구단 가치"] = squad_value_element.text.strip()

print(f" -> '{result_data['구단주명']}' 구단 가치 '{result_data['구단 가치']}' 추출 완료.")



except Exception as e:

print(f" -> '{result_data['구단주명']}' 처리 중 오류 발생: {e}")

result_data["error"] = str(e)

finally:

if driver:

driver.quit()


return result_data



@app.route('/')

def index():

return render_template('index.html')



@app.route('/results_table')

def results_table_page():

if not os.path.exists(DISPLAY_JSON_FILE):

return render_template('results_table.html', results=[], last_updated='데이터 없음')

with open(DISPLAY_JSON_FILE, 'r', encoding='utf-8') as f:

display_data = json.load(f)

return render_template('results_table.html', **display_data)



@app.route('/crawl', methods=['POST'])

def crawl_data():

try:

managers_to_process = _read_urls_from_file(URL_FILE_NAME)

except FileNotFoundError as e:

return jsonify({"status": "error", "message": str(e)}), 500



if not managers_to_process:

return jsonify({"status": "warning", "message": "처리할 감독 정보가 없습니다."}), 200



crawled_results = []

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

crawled_results = list(executor.map(_crawl_single_manager, managers_to_process))



final_results = [res for res in crawled_results if 'error' not in res]



display_data = {

"results": crawled_results, # 에러 포함 전체 결과를 표시할 수 있도록 수정

"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

}



try:

with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:

json.dump(final_results, f, indent=4, ensure_ascii=False)

with open(DISPLAY_JSON_FILE, 'w', encoding='utf-8') as f:

json.dump(display_data, f, indent=4, ensure_ascii=False)


rendered_html = render_template('results_table.html', **display_data)

with open(OUTPUT_HTML_FILE, 'w', encoding='utf-8') as f:

f.write(rendered_html)



except Exception as e:

print(f"파일 저장 중 오류: {e}")

return jsonify({"status": "error", "message": f"파일 저장 중 오류: {e}"}), 500



success_count = len(final_results)

fail_count = len(managers_to_process) - success_count



return jsonify({

"status": "success",

"message": f"총 {len(managers_to_process)}명 중 {success_count}명 성공, {fail_count}명 실패.",

"results": crawled_results

})



if __name__ == '__main__':

app.run(debug=True, host='0.0.0.0', port=5001)