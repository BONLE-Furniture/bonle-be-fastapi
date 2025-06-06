# search_result.py
import requests
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time
import router.crawling.shop_search.search_parsers as search_parsers
import urllib3
import os
from urllib.parse import urlparse

# 기본값 설정
DEFAULT_KEYWORD = "놀"
DEFAULT_ITEMS_PER_SITE = 2

# ssl 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def init_selenium():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--enable-unsafe-webgl")
    options.add_argument("--use-gl=swiftshader")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--allow-insecure-localhost')
    options.set_capability("acceptInsecureCerts", True)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def save_html(soup, site_name):
    if not os.path.exists("html"):
        os.makedirs("html")
    file_path = os.path.join("html", f"{site_name}_output.html")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(soup.prettify())

def is_product_page_gone(url, response):
    """상품 페이지가 사라졌는지 확인"""
    # 1. 404 에러 체크
    if response.status_code == 404:
        return True
        
    # 2. 리다이렉트 체크
    if response.history:
        original_path = urlparse(url).path
        final_path = urlparse(response.url).path
        
        # 홈페이지나 메인 카테고리로 리다이렉트된 경우
        if final_path in ['/', '/index.php', '/main/index.php']:
            return True
            
        # 상품 페이지에서 다른 페이지로 리다이렉트된 경우
        if 'goods_view.php' in original_path and 'goods_view.php' not in final_path:
            return True
            
    return False

def fetch_static_page(url, keyword):
    search_url = url.replace("키워드", keyword)
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        response = requests.get(search_url, headers=headers, verify=False, timeout=4, allow_redirects=True)
        response.raise_for_status()
        
        # 상품 페이지가 사라진 경우 체크
        if is_product_page_gone(search_url, response):
            print(f"Product page is gone or redirected: {search_url}")
            return None
            
        if "nordicpark.co.kr" in search_url:
            response.encoding = 'euc-kr'
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"Error fetching {search_url}: {e}")
        return None

def fetch_dynamic_page(driver, url, keyword):
    search_url = url.replace("키워드", keyword)
    driver.get(search_url)
    time.sleep(3)
    
    try:
        # 현재 URL 확인
        current_url = driver.current_url
        if is_product_page_gone(search_url, driver.execute_script("return window.performance.getEntries()[0].responseURL")):
            print(f"Product page is gone or redirected: {search_url}")
            return None
            
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"Alert: {alert_text}")
            alert.accept()
            if alert_text in ["검색결과가 없습니다.", "검색결과 없음."]:
                return BeautifulSoup("<html><body></body></html>", "html.parser")
        except:
            pass
            
        return BeautifulSoup(driver.page_source, "html.parser")
    except Exception as e:
        print(f"Error in dynamic page fetch: {e}")
        return None

def run_search(keyword=DEFAULT_KEYWORD, number=DEFAULT_ITEMS_PER_SITE):
    all_results = []

    with open("search_site_parsers.json", "r", encoding="utf-8") as file:
        site_parsers = json.load(file)

    enabled_sites = {name: data for name, data in site_parsers.items() if data["enabled"]}
    requires_selenium = any(data["fetch_type"] == "dynamic" for data in enabled_sites.values())
    driver = init_selenium() if requires_selenium else None

    try:
        for site_name, data in enabled_sites.items():
            search_url = data["search_url"]
            parser_name = data["parser"]
            fetch_type = data["fetch_type"]

            try:
                if fetch_type == "dynamic" and driver:
                    soup = fetch_dynamic_page(driver, search_url, keyword)
                else:
                    soup = fetch_static_page(search_url, keyword)

                if soup is None:  # 상품 페이지가 사라진 경우
                    continue

                save_html(soup, site_name)

                parser_function = getattr(search_parsers, parser_name, None)
                if parser_function is None:
                    continue

                results = parser_function(soup, number)
                for result in results:
                    result["site"] = site_name
                    if "brand" not in result:
                        result["brand"] = None

                all_results.extend(results)

            except Exception as e:
                print(f"{site_name} error: {e}")
    finally:
        if driver:
            driver.quit()

    return all_results