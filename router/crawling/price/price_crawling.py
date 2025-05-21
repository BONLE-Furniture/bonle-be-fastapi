import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from publicsuffix2 import get_sld, get_tld
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import urllib3
import chardet
import argparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 사이트 이름과 가격 정보, 상품 이름을 표시하는 (유형, 식별자) 형태의 배열
site_info = [
    ["rooming", None, None],
    ["hpix", None, None],
    ["8colors", None, None],
    ["ohou", ("meta", "product:price:amount"), ("meta", "og:title")],  # 오늘의집: Agent 차단 존재, 해결
    ["kream", None, None],
    ["editori", ("class", "cut-per-price"), ("meta", "twitter:title")],
    ["inartshop", ("class", "sale_price"), None],
    ["jaimeblanc", None, None],
    ["s-houz", None, None],
    ["29cm", ("id", "pdp_product_price"), ("id", "pdp_product_name")],  # 29CM: selenium 필수 시간 소요, 해결
    ["dansk", ("class", "productPriceSpan"), None],
    ["benufe", None, None],
    ["collectionb", ("class", "item-after-price"), None],
    ["innometsa", None, None],
    ["bibliotheque", None, None],  # 비블리오떼크: 링크에 상품 명이 들어가고, 상품명이 자주 변경
    # url = 'https://www.bibliotheque.co.kr/product/12%EC%9B%94-%EB%A7%90-%EC%9E%85%EA%B3%A0-%EB%A3%A8%EC%9D%B4%EC%8A%A4%ED%8F%B4%EC%84%BC-ph-5-%EB%AF%B8%EB%8B%88-%EB%AA%A8%EB%85%B8%ED%81%AC%EB%A1%AC-%EB%B2%84%EA%B1%B4%EB%94%94/5939/category/218/display/1/#listproduct_product'
    ["remod", None, None],
    ["mmmg", None, None],
    ["j-gallery", None, None],
    ["wonderaum", None, None],
    ["unwind", None, None],
    ["inscale", None, None],
    ["gyb", ("class", "price"), None],
    ["conranshop", ("class", "sale"), None],  # 할인과 일반 클래스 명이 달라 코드 내 별도 예외처리. 해결
    ["vorblick", ("class", "sale-price disib"), None],
    ["mignondejjoy", None, None],
    ["gareem", None, None],
    ["innovad", ("id", "sit_tot_price"), ("class", "prd_name md font_32")],  # SSL 인증서 문제 예외처리, 해결
    ["chairgallery", ("class", "real_price inline-blocked"), None],
    ["nordicpark", ("class", "price"), ("class", "tit-prd")],  # 인코딩 문제 존재. 해결
    ["tonstore", None, None],  # !!! 네이버 스마트스토어. 파싱 불가
    ["innohome", None, None],
    ["ilva", None, None],
    ["kartellkorea", ("class", "tr_price"), ("id", "sit_title")],  # 제품명 후처리
    ["stayh", None, None],
    ["segment", None, None],
    ["arkistore", None, None],
    # url = 'https://arkistore.com/product/detail.html?product_no=2564&cate_no=49&display_group=1'
    ["10x10", ("input", "itemPrice"), None]
]

# 셀레니움이 필요한 사이트 목록
run_selenium = ["29cm"]

# 인코딩이 별도로 필요한 사이트 목록
run_encoding = ["nordicpark"]

# 제품명 뒤에 '- 회사이름' 들어가는 경우 해당 배열에 추가
delete_company = ["stayh"]  # 제품 명 뒤 회사명 삭제

# 경고 메시지 제거
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


######################
### 사이트 이름 추출 ###
######################

def get_site_name(url):
    """URL에서 사이트 이름을 추출하는 함수"""
    parsed_url = urlparse(url)
    full_domain = get_sld(parsed_url.netloc)
    tld = get_tld(parsed_url.netloc)
    site_name = full_domain.replace(f".{tld}", "")

    return site_name


######################
##### 제품명 추출 #####
######################

def get_product_name(soup, site_name=None, default_info=None):
    """제품명을 추출하는 함수"""
    product_name_tag = None

    # 우선 site_info에 지정된 정보를 시도
    if default_info:
        attr_type, identifier = default_info
        if attr_type == "meta":
            meta_tag = soup.find("meta", property=identifier)
            if meta_tag and meta_tag.get("content"):
                return meta_tag["content"].strip()
            meta_tag = soup.find("meta", attrs={"name": identifier})
            if meta_tag and meta_tag.get("content"):
                return meta_tag["content"].strip()
        elif attr_type == "id":
            product_name_tag = soup.find(id=identifier)
        elif attr_type == "class":
            product_name_tag = soup.find(class_=identifier)
        elif attr_type == "input":
            input_tag = soup.find('input', attrs={"name": identifier})
            if input_tag and input_tag.has_attr('value'):
                return input_tag['value'].strip()

    # 기본 검색 옵션: 메타 태그의 "og:title"를 우선 시도
    if not product_name_tag:
        meta_tag = soup.find("meta", property="og:title")
        if meta_tag and meta_tag.get("content"):
            return meta_tag["content"].strip()

    # 기본 탐색: name 관련 ID가 포함된 요소
    if not product_name_tag:
        name_elements = soup.find_all(lambda tag: tag.has_attr('id') and 'name' in tag['id'].lower())
        if name_elements:
            return name_elements[0].get_text(" ", strip=True)

    return product_name_tag.get_text(" ", strip=True) if product_name_tag else None


######################
###### 가격 추출 ######
######################

def filter_price_elements(price_elements):
    """가격 요소에서 조건에 맞는 가격 정보만 필터링"""
    filtered_prices = []
    for element in price_elements:
        text = element.get_text(strip=True)
        if any(currency in text.upper() for currency in ['KRW', '원', 'WON']) or re.search(r'\d{3,}', text):
            filtered_prices.append({"id": element.get('id', 'N/A'), "text": text})
    return filtered_prices


def clean_price(raw_price_text):
    """가격 문자열을 정제하여 원하는 형태로 반환"""
    # "KRW", "원", "WON" 문자열 제거
    cleaned_text = re.sub(r'\b(KRW|원|WON)\b', '', raw_price_text).strip()

    # 쉼표가 있거나 없는 4자리 이상의 숫자 추출
    numbers = re.findall(r'\d{1,3}(?:,\d{3})+|\d{4,}', cleaned_text)
    int_numbers = [int(num.replace(',', '')) for num in numbers]

    if int_numbers:
        smallest_number = min(int_numbers)
        return f"{smallest_number:,}"

    return None


def get_price_from_elements(soup, site_name, default_info=None):
    """가격 정보를 추출하는 함수"""
    price_tag = None

    # 예외처리 #콘란샵
    if site_name == 'conranshop':
        attr_type, identifier = default_info
        # sale class 먼저 찾고
        price_tag = soup.find(class_=identifier)
        if price_tag:
            return clean_price(price_tag.get_text(" ", strip=True)) if price_tag else None
        price_tag = soup.find(class_='basic')
        if price_tag:
            return clean_price(price_tag.get_text(" ", strip=True)) if price_tag else None

    # 우선 site_info에 지정된 정보를 시도
    if default_info:
        attr_type, identifier = default_info
        if attr_type == "meta":
            meta_price = soup.find("meta", property=identifier)
            if meta_price and meta_price.get("content"):
                return clean_price(meta_price["content"])
        elif attr_type == "id":
            price_tag = soup.find(id=identifier)
        elif attr_type == "class":
            price_tag = soup.find(class_=identifier)
        elif attr_type == "input":
            input_tag = soup.find('input', attrs={"name": identifier})
            if input_tag and input_tag.has_attr('value'):
                return clean_price(input_tag['value'])

        if price_tag:
            return clean_price(price_tag.get_text(" ", strip=True)) if price_tag else None

    # 기본 검색 옵션: 메타 태그의 "product:sale_price:amount"를 우선 시도
    if not price_tag:
        meta_price = soup.find("meta", property="product:sale_price:amount")
        if meta_price and meta_price.get("content"):
            return clean_price(meta_price["content"])
        meta_price = soup.find("meta", property="product:price:amount")
        if meta_price and meta_price.get("content"):
            return clean_price(meta_price["content"])

    # 기본 검색 로직: price나 판매 키워드가 포함된 요소
    if not price_tag:
        price_elements = soup.find_all(lambda tag: (tag.has_attr('id') and 'price' in tag['id'].lower()) or
                                                   (tag.has_attr('class') and 'price' in ' '.join(
                                                       tag['class']).lower()) or
                                                   ('판매' in tag.get_text()))
        filtered_prices = filter_price_elements(price_elements)

        if filtered_prices:
            return clean_price(filtered_prices[0]['text'])

    return None


######################
##### 파싱 및 진행 #####
######################

# Chrome WebDriver 설정
options = Options()
options.headless = True


def get_html_content(url, site_name):
    if site_name in run_selenium:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        html_content = driver.page_source
        driver.quit()

    else:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Accept-Language': 'en-US,en;q=0.9',
            # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
        }

        if site_name == 'innovad':  # 예외처리
            response = requests.get(url, headers=headers, verify=False)
        else:
            response = requests.get(url, headers=headers, verify=False)  # SSL 인증서 검증 비활성화

        # 인코딩 예외 처리
        if site_name in run_encoding:
            detected_encoding = chardet.detect(response.content)['encoding']
            response.encoding = detected_encoding if detected_encoding else 'utf-8'  # 감지된 인코딩 사용

        if response.status_code != 200:
            print("Failed to retrieve the page")
            return None
        html_content = response.text
    return html_content


def get_all_info(url):
    site_name = get_site_name(url)

    html_content = get_html_content(url, site_name)
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')

    # site_info에서 사이트 정보 가져오기
    matched_site = next((item for item in site_info if item[0] == site_name), None)
    if matched_site:
        price_info, name_info = matched_site[1], matched_site[2]
        price = get_price_from_elements(soup, site_name, default_info=price_info)
        name = get_product_name(soup, site_name, default_info=name_info)
    else:
        # site_info가 없을 경우 기본 옵션 사용
        price = get_price_from_elements(soup, site_name, default_info=None)
        name = get_product_name(soup, site_name, default_info=None)

    # 후처리

    if site_name == 'kartellkorea':
        name = re.sub(r'\b(요약정보 및 구매)\b', '', name).strip()
    if site_name in delete_company:
        name = re.sub(r'\s*-\s*[^-]*$', '', name).strip()

    return {
        "site": site_name,
        "price": price,
        "name": name
    }
