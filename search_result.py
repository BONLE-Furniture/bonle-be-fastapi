# search_result.py
import requests
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time
import search_parsers
import argparse
import urllib3

# 기본값 설정
DEFAULT_KEYWORD = "놀"
DEFAULT_ITEMS_PER_SITE = 2
items_per_site = DEFAULT_ITEMS_PER_SITE


# ssl 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def parse_arguments():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(description='상품 검색 프로그램')
    parser.add_argument('-k', '--keyword', type=str, default=DEFAULT_KEYWORD,
                      help=f'검색어 (기본값: {DEFAULT_KEYWORD})')
    parser.add_argument('-n', '--number', type=int, default=DEFAULT_ITEMS_PER_SITE,
                      help=f'사이트당 검색 결과 개수 (기본값: {DEFAULT_ITEMS_PER_SITE})')
    return parser.parse_args()

# Selenium 전역 설정
def init_selenium():
    """Selenium 드라이버 초기화"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--enable-unsafe-webgl")  # SwiftShader를 명시적으로 활성화
    options.add_argument("--use-gl=swiftshader")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    # SSL 에러 무시를 위한 옵션들 추가
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--allow-insecure-localhost')
    options.set_capability("acceptInsecureCerts", True)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    return driver

# 공통 함수
def save_html(soup, site_name):
    """디버깅을 위해 HTML 저장"""
    import os
    
    # html 폴더가 없으면 생성
    if not os.path.exists("html"):
        os.makedirs("html")
        
    # html 폴더 안에 파일 저장
    file_path = os.path.join("html", f"{site_name}_output.html")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(soup.prettify())

def fetch_static_page(url, keyword):
    """Static HTML 페이지 가져오기"""
    search_url = url.replace("키워드", keyword)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        response = requests.get(search_url, headers=headers, verify=False, timeout=4)  # 4초 타임아웃 설정
        response.raise_for_status()
        
        # nordicpark인 경우에만 euc-kr 인코딩 적용
        if "nordicpark.co.kr" in search_url:
            response.encoding = 'euc-kr'
        
        return BeautifulSoup(response.text, "html.parser")
    
    except requests.Timeout:
        print(f"Timeout occurred while fetching {search_url}")
        return None
    except requests.RequestException as e:
        print(f"Error occurred while fetching {search_url}: {e}")
        return None

def fetch_dynamic_page(driver, url, keyword):
    """Selenium Dynamic HTML 페이지 가져오기"""
    search_url = url.replace("키워드", keyword)
    driver.get(search_url)
    
    time.sleep(3)
    print("Page loaded successfully.")
    
    try:
        # 알림창이 있는지 확인하고 처리
        alert = driver.switch_to.alert
        alert_text = alert.text
        print(f"Alert message: {alert_text}")
        alert.accept()  # 알림창 닫기
        
        # 검색 결과가 없는 경우 빈 결과 반환
        if alert_text == "검색결과가 없습니다." or alert_text == "검색결과 없음.":
            return BeautifulSoup("<html><body></body></html>", "html.parser")
            
    except:
        pass  # 알림창이 없는 경우 계속 진행
    
    return BeautifulSoup(driver.page_source, "html.parser")

def main(keyword=DEFAULT_KEYWORD, number=DEFAULT_ITEMS_PER_SITE):
    all_results = []

    # 사이트 파서 매핑 정보 로드
    with open("search_site_parssers.json", "r", encoding="utf-8") as file:
        site_parsers = json.load(file)

    print(f"검색어 : {keyword}")
    print(f"사이트 별 개수 : {items_per_site}")

    # enabled가 true인 사이트들만 사용
    enabled_sites = {name: data for name, data in site_parsers.items() if data["enabled"]}

    # Selenium 초기화 여부 확인
    requires_selenium = any(data["fetch_type"] == "dynamic" for data in enabled_sites.values())
    driver = init_selenium() if requires_selenium else None

    try:
        for site_name, data in enabled_sites.items():
            search_url = data["search_url"]
            parser_name = data["parser"]
            fetch_type = data["fetch_type"]

            print(f"\n검색 사이트: {site_name}")
            print(f"검색 URL: {search_url.replace('키워드', keyword)}")
            
            try:
                # HTML 페이지 가져오기
                if fetch_type == "dynamic" and driver is not None:
                    soup = fetch_dynamic_page(driver, search_url, keyword)
                else:
                    soup = fetch_static_page(search_url, keyword)

                # 디버깅을 위해 HTML 저장
                save_html(soup, site_name)
                print(f"{site_name} HTML이 성공적으로 저장되었습니다.")

                # 파서 함수 실행 시도
                try:
                    parser_function = getattr(search_parsers, parser_name, None)
                    if parser_function is None:
                        print(f"경고: Parser function '{parser_name}'을 찾을 수 없습니다. HTML만 저장됩니다.")
                        continue

                    results = parser_function(soup, number)
                    # results에 site 추가
                    for result in results:
                        result["site"] = site_name
                        # Brand가 없으면 None
                        if "brand" not in result:
                            result["brand"] = None
                    
                    if not results:
                        print(f"{site_name}에서 검색 결과를 찾을 수 없습니다.")
                    else:
                        print(f"{site_name}에서 {len(results)}개의 상품을 찾았습니다.")
                        all_results.extend(results)

                except ImportError:
                    print(f"경고: search_parsers 모듈을 찾을 수 없습니다. HTML만 저장됩니다.")
                except Exception as e:
                    print(f"파서 실행 중 오류 발생: {str(e)}. HTML만 저장됩니다.")

            except Exception as e:
                print(f"{site_name} HTML 가져오기 중 오류 발생: {str(e)}")

    finally:
        if driver is not None:
            driver.quit()

    # 결과 반환 방식 변경
    if all_results:
        return all_results
    else:
        return []

args = parse_arguments()
items_per_site = args.number

if __name__ == "__main__":
    results = main(args.keyword, args.number)
    # 콘솔 출력 로직
    if results:
        print("\n=== 검색 결과 ===")
        for idx, product in enumerate(results, 1):
            print(f"\n## Product {idx}")
            print(f"Site:           {product['site']}")
            print(f"Image URL:      {product['image_url']}")
            print(f"Product URL:    {product['product_url']}")
            print(f"Name:           {product['name']}")
            print(f"Price:          {product['price']}")
            print(f"Brand:          {product['brand']}")
    else:
        print("\n모든 사이트에서 검색 결과를 찾을 수 없습니다.")
