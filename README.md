# FC Online Manager Stats Crawler

이 프로젝트는 FC Online Manager 모드의 통계를 크롤링하고 웹 인터페이스를 통해 시각화하는 도구입니다.

## 시작하기

이 프로젝트를 로컬 환경에서 설정하고 실행하기 위한 지침입니다.

### 전제 조건

이 프로젝트를 실행하려면 다음이 설치되어 있어야 합니다:

*   **Python 3**: [Python 공식 웹사이트](https://www.python.org/downloads/)에서 다운로드 및 설치
*   **pip**: Python 패키지 관리자 (Python 3 설치 시 함께 설치되는 경우가 많습니다)
*   **Google Chrome 브라우저**: [Google Chrome 공식 웹사이트](https://www.google.com/chrome/)에서 다운로드 및 설치
*   **ChromeDriver**: 설치된 Chrome 브라우저 버전에 맞는 ChromeDriver를 다운로드해야 합니다.
    1.  Chrome 브라우저를 열고 주소창에 `chrome://version`을 입력하여 Chrome 버전을 확인합니다.
    2.  [ChromeDriver 다운로드 페이지](https://chromedriver.chromium.org/downloads)로 이동하여 본인의 Chrome 버전에 맞는 ChromeDriver를 다운로드합니다.
    3.  다운로드한 `chromedriver` 실행 파일을 이 프로젝트의 루트 디렉토리 (README.md 파일이 있는 곳)에 배치합니다.

### 의존성 설치

프로젝트에 필요한 Python 라이브러리를 설치합니다.

1.  프로젝트 루트 디렉토리로 이동합니다:
    ```bash
    cd /path/to/your/project/crawler
    ```
2.  `requirements.txt` 파일을 생성합니다. 이 파일에는 프로젝트에 필요한 모든 Python 라이브러리가 포함됩니다.
    ```bash
    pip freeze > requirements.txt
    ```
    (참고: 이 명령은 현재 환경에 설치된 모든 패키지를 `requirements.txt`에 기록합니다. 만약 가상 환경을 사용하고 있다면, 가상 환경 내에서 이 명령을 실행하여 프로젝트에 필요한 패키지만 포함되도록 하는 것이 좋습니다.)
3.  `requirements.txt`에 명시된 라이브러리를 설치합니다:
    ```bash
    pip install -r requirements.txt
    ```

### 크롤러 실행

크롤링 작업을 수행하는 스크립트를 실행합니다.

```bash
python fconline_crawler.py
```
(참고: `fconline_crawler.py`가 특정 인자나 설정 파일을 필요로 할 수 있습니다. 스크립트 내부를 확인하거나 추가 지침이 필요할 수 있습니다.)

### 웹 애플리케이션 실행

크롤링된 데이터를 시각화하는 웹 애플리케이션을 실행합니다.

```bash
python app.py
```

애플리케이션이 시작되면 웹 브라우저를 열고 `http://127.0.0.1:5000` (또는 콘솔에 표시되는 주소)으로 이동하여 결과를 확인할 수 있습니다.

## 파일 구조

```
.
├───.git/
├───archive/                # 크롤링된 데이터 아카이브
├───static/                 # CSS, JavaScript 등 정적 파일
├───templates/              # HTML 템플릿 파일
├───user/                   # 사용자별 크롤링 데이터
├───.DS_Store               # macOS 시스템 파일 (무시됨)
├───.gitignore              # Git이 무시할 파일 목록
├───ap.py                   # (추정) API 관련 스크립트
├───app.py                  # 웹 애플리케이션 메인 스크립트 (Flask 추정)
├───chromedriver            # Chrome 웹 드라이버 실행 파일 (Git에서 무시됨)
├───current_crawl_display_data.json # 현재 크롤링 데이터 (Git에서 무시됨)
├───dummy.html
├───dummy.js
├───favicon.ico
├───fconline_crawler.py     # 메인 크롤링 스크립트
├───fconline_manager_stats.html # 매니저 통계 HTML (추정)
├───fconline_manager_stats.json # 매니저 통계 JSON (Git에서 무시됨)
├───league2_urls.txt        # 리그 2 URL 목록 (추정)
├───LICENSE.chromedriver    # ChromeDriver 라이선스 (Git에서 무시됨)
├───logo.png
├───miningleague.html
├───README.md               # 이 파일
├───THIRD_PARTY_NOTICES.chromedriver # ChromeDriver 서드파티 고지 (Git에서 무시됨)
├───urls.txt                # 크롤링할 URL 목록
└───requirements.txt        # Python 의존성 목록 (생성 필요)
```

## 기여

기여에 대한 내용은 여기에 추가할 수 있습니다.

## 라이선스

라이선스 정보는 여기에 추가할 수 있습니다.
