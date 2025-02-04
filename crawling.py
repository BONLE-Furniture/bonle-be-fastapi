# Selenium을 사용한 해결 방법
from googletrans import Translator
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

translator = Translator()

# 인아트 크롤링
def inart_crawling():
    url = "https://www.inartshop.com/goods/brand?page=1&searchMode=brand&brand%5B0%5D=b0087&per=40&code=0087"
    # url = "https://search.shopping.naver.com/search/all?bt=-1&frm=NVSCPRO&query=%EB%84%A4%EC%9D%B4%EB%B2%84+%EC%87%BC%ED%95%91"
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option("detach", True)
    driver = webdriver.Chrome()
    driver.get(url)
    driver.implicitly_wait(10)


    items = driver.find_elements(By.CLASS_NAME, "goods_list_style1")
    json_data = []
    for item in items:
        name = item.find_element(By.CLASS_NAME, "goods_name_area").text
        price = item.find_element(By.CLASS_NAME, "goods_price_area").text
        link = item.find_element(By.CLASS_NAME, "goods_name_area > a").get_attribute("href")
        brand_id = "brand_louispoulsen"
        shop_id = "shop_inart"
        json_data.append({
            "name": name,
            "price": price,
            "shop_url": link,
            "shop_id": shop_id,
            "brand_id": brand_id
        })
    return json_data

print(inart_crawling())
# # scroll type
# while True:
#     # 스크롤을 화면 가장 아래로 내림
#     driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")


# # 요소가 로드될 때까지 대기
# elements = WebDriverWait(driver, 10).until(
#     EC.presence_of_all_elements_located((By.CLASS_NAME, "goods_list_style1"))
# )

