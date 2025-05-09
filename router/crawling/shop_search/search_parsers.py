#search_parsers.py

import re
from bs4 import Comment

# 공통 상품 정보 추출 함수
def extract_product_details(product, image_selector, name_selector, url_selector, product_url_prefix, price_selector=None, brand_selector=None):
    """상품의 공통 요소 (이미지, 이름, URL) 추출"""
    # 이미지 URL 추출
    image_url = None
    if image_selector:
        img_tag = product.select_one(image_selector)
        image_url = img_tag["src"] if img_tag else "No image found"
        if image_url and image_url.startswith("//"):
            image_url = f"https:{image_url}"
        
    # 상품명 추출
    name = None
    if name_selector:
        name_tag = product.select_one(name_selector)
        name = name_tag.get_text(separator=' ', strip=True).strip() if name_tag else "No name found"

    # 브랜드명 추출
    brand = None
    if brand_selector:
        brand_tag = product.select_one(brand_selector)
        brand = brand_tag.get_text().strip() if brand_tag else "No brand found"
        # print(f"brand: {brand}")

    # URL 추출
    url_tag = product.select_one(url_selector)
    product_url = url_tag["href"] if url_tag and url_tag.has_attr("href") else "No product URL found"
    if product_url and product_url.startswith("/"):
        product_url = f"{product_url_prefix}{product_url}"
    elif product_url and product_url.startswith("../"):
        product_url = f"{product_url_prefix}/{product_url.replace('../', '')}"

    # 가격 추출
    price = None
    if price_selector:
        price_tag = product.select_one(price_selector)
        # print(f"price_tag: {price_tag}")
        if price_tag:
            price = price_tag.get("data-sale") if "data-sale" in price_tag.attrs else price_tag.text.strip()

    ### 후처리

    # 가격문의 일 경우 가격을 999,999,999로 설정
    if price and (price.startswith("가격문의") or price.startswith("매장 별도문의")):
        price = '999,999,999'

    # 가격에서 숫자만 추출
    if price: price = re.sub(r'[^0-9,]', '', price)

    # 0원이나 1원인 경우 품절 여부 확인
    if price and price.strip() in ["0", "0원", "1", "1원"]:
        soldout_img1 = product.select_one("div.soldout-icon img[alt='품절']")
        soldout_img2 = product.select_one("div.icon img[alt='품절']")
        soldout_img3 = product.select_one("div.promotion img[alt*='품절']")
        if soldout_img1 or soldout_img2 or soldout_img3:
            price = "품절"

    # 상품명에서 "상품명 : " 제거
    if name: name = re.sub("상품명 : ", "", name)

    # url에서 /.*-입고- 제거 (ex. abc.com/product/12월-입고-테이블-램프/6002 > abc.com/product/테이블-램프/6002)
    if product_url and "-입고-" in product_url:
        product_url = re.sub(r'/*-입고-', '/', product_url)

    # url에서 입고 날짜 제거 (ex. bibliotheque.co.kr/product/12월-말/루이스폴센-ph-5/5940/category/67/display/1/ > bibliotheque.co.kr/product/루이스폴센-ph-/5940/category/67/display/1/)
    if product_url and "/product/" in product_url:
        product_url = re.sub(r'/product/(?:\d+월-(?:초|중|말)/)?(.*?)/', r'/product/\1/', product_url)
        # 1월, 2월 - 12월 제거
        product_url = re.sub(r'/(?:\d+월-)?', '/', product_url)

    return {
        "image_url": image_url,
        "product_url": product_url,
        "name": name,
        "price": price,
        "brand": brand
    }

# 각 사이트별 파서 정의
def parse_8colors(soup, items_per_site):
    """8colors 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid4 > li")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.prdImg img",
            name_selector="p.name a",
            url_selector="p.name a", 
            product_url_prefix="https://8colors.co.kr",
            price_selector="span.discount_rate",
            brand_selector="ul.spec li.xans-record- > span[style*='font-size:12px'][style*='color:#000000'][style*='font-weight:bold']:last-child" 
        )

        product_details.append(details)

    return product_details

def parse_rooming(soup, items_per_site):
    """Rooming 사이트의 검색 결과 파싱"""
    product_cards = soup.select("ul.prd-list.flex.grid-5.flex-wrap > li")[:items_per_site]
    product_details = []

    for product in product_cards:
        details = extract_product_details(
            product,
            image_selector="div.img-box img",
            name_selector="div.description .name a",
            url_selector="div.description .name a", 
            product_url_prefix="https://rooming.co.kr",
            price_selector="li.prd-price",
            brand_selector="ul.spec li[data-name='제조사'] > span[style*='font-size:12px'][style*='color:#555555']:last-child"  # 마지막 span 선택
        )

        product_details.append(details)

    return product_details

def parse_hpix(soup, items_per_site):
    """HPIX 사이트의 검색 결과 파싱"""
    products = soup.select("ul.row.product-list > li.product-item")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.image img",
            name_selector="div.description p.name span",  
            url_selector="a.blur",      
            product_url_prefix="https://hpix.co.kr",
            price_selector="div.price-info p.price:not(.sale)",
            brand_selector="div.description p.brand"
        )
        
        # 할인가가 있는 경우 할인가를 가격으로 사용
        sale_price = product.select_one("div.price-info p.price.sale span")
        if sale_price and sale_price.text.strip():
            price = sale_price.text.strip()
            price = re.search(r'([\d,]+)', price)
            if price: details["price"] = price.group(1)
            
        product_details.append(details)

    return product_details

def parse_ohou(soup, items_per_site):
    """오늘의집 사이트의 검색 결과 파싱"""
    products = soup.select("div.search-store__scroller__product__wrap article")[:items_per_site]
    product_details = []

    for product in products:
        # 이미지 URL을 먼저 추출
        img_tag = product.select_one("div.css-ypqde8.e1bro5mc2 img")
        image_url = ""
        if img_tag and not img_tag.get("src", "").startswith("data:image"):  # base64 이미지 제외
            # srcset의 마지막 URL 사용
            srcset = img_tag.get("srcset", "")
            if srcset:
                image_urls = srcset.split(",")
                last_url = image_urls[-1].split(" ")[0]
                image_url = last_url
            else:
                image_url = img_tag.get("src", "")

        details = extract_product_details(
            product,
            image_selector=None,  # 이미지는 위에서 직접 처리
            name_selector="span.product-name",
            url_selector="a",
            product_url_prefix="https://ohou.se",
            price_selector="span.css-1skx3t9",
            brand_selector="div.product-brand"
        )
        
        details["image_url"] = image_url  # 추출한 이미지 URL 설정
        
        product_details.append(details)

    return product_details

def parse_kream(soup, items_per_site): #실패 
    """KREAM 사이트의 검색 결과 파싱"""
    products = soup.select("div.search_result_item")[:items_per_site]  
    product_details = []

    print(products)

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.product_img img",
            name_selector="div.product_info div.name",
            url_selector="div.product_info a",
            product_url_prefix="https://kream.co.kr",
            price_selector="div.product_info div.price"
        )
             
        product_details.append(details)

    return product_details

def parse_editori(soup, items_per_site):
    """Editori 사이트의 검색 결과 파싱"""
    products = soup.select("div.item_gallery_type ul > li")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.item_photo_box img.middle",
            name_selector="div.item_tit_box strong.item_name",
            url_selector="div.item_photo_box a",
            product_url_prefix="https://www.editori.kr",
            price_selector="div.item_money_box strong.item_price span"
        )
        
        product_details.append(details)

    return product_details

def parse_jaimeblanc(soup, items_per_site):
    """Jaime Blanc 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid5 > li")[:items_per_site]
    product_details = []

    for product in products:
        price_spans = product.select("ul.xans-element- li.xans-record- span")
        if len(price_spans) > 0:
            # 가격은 "판매가" 라벨 다음의 span에 있음
            price_index = next((i for i, span in enumerate(price_spans) if "판매가" in span.text), None)
            if price_index is not None and price_index + 1 < len(price_spans):
                price = price_spans[price_index + 1].text.strip()
                if price: price = re.sub(r'[^0-9,]', '', price)
            else:
                price = None
        else:
            price = None

        details = extract_product_details(
            product,
            image_selector="div.thumbnail img",
            name_selector="div.description p.name a",
            url_selector="div.description p.name a",
            product_url_prefix="https://jaimeblanc.com",
            price_selector=None,
            brand_selector="ul.spec li.xans-record-:first-child > span[style*='color:#ababab']:last-child"  # 브랜드
        )
        details["price"] = price
        
        product_details.append(details)

    return product_details

def parse_shouz(soup, items_per_site):
    """S-houz 사이트의 검색 결과 파싱"""
    products = soup.select("div.sp-product-item.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="i.sp-product-item-thumb-origin img",  # 이미지는 i 태그 안의 img
            name_selector="span.sp-product-enname",  # 상품명
            url_selector="div.sp-product-name a",  # URL
            product_url_prefix="https://s-houz.com",
            price_selector="div.sp-c-dc-price div",  # 최종 할인가
            brand_selector="div[rel='브랜드'] > span[style*='font-size:11px']:not(.displaynone)"  # 브랜드
        )
        
        product_details.append(details)

    return product_details

def parse_dansk(soup, items_per_site):
    """Dansk 사이트의 검색 결과 파싱"""
    # 상품 목록 선택 - 각 상품은 div.shopProductWrapper 안에 있음
    products = soup.select("div.shopProductWrapper")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector=None,  # 이미지는 background-image로 설정되어 있음
            name_selector="div.shopProduct.productName",  # 상품명
            url_selector="a",  # URL
            product_url_prefix="https://dansk.co.kr",
            price_selector="span.productDiscountPriceSpan, span.productPriceSpan",  # 할인가 또는 일반가
            brand_selector=None  # 브랜드는 상품명에서 추출
        )
        
        # 이미지 URL 처리 (background-image에서 URL 추출)
        img_tag = product.select_one("div.thumb.img")
        details["image_url"] = img_tag["imgsrc"]
        
        # 상품명에서 브랜드 추출
        if details["name"] and "/" in details["name"]:
            brand, name = details["name"].split("/", 1)
            details["brand"] = brand.strip()
            details["name"] = name.strip()
        else:
            details["brand"] = None

        product_details.append(details)

    return product_details

def parse_benufe(soup, items_per_site):
    """Benufe 사이트의 검색 결과 파싱"""
    products = soup.select("ul.product__list > li.list__item")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.item__thumb img.thumb__image",  # 이미지
            name_selector="p.info__name span",  # 상품명
            url_selector="div.item__thumb a",  # URL
            product_url_prefix="https://benufe.com",
            price_selector="ul.info__spec li.product_price.xans-record-",
            brand_selector="p.info__brand a"
        )
        
        product_details.append(details)

    return product_details

def parse_collectionb(soup, items_per_site):
    """Collection B 사이트의 검색 결과 파싱"""
    products = soup.select("div.goods-list-table.grid4 > div.section")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.goods-list-img-wrapper img.list-img",  # 이미지
            name_selector="h6.item_name",  # 상품명
            url_selector="div.goods-list-img-wrapper a",  # URL
            product_url_prefix="https://www.collectionb.cc",
            price_selector="div.item_money_box strong.item_price span",
            brand_selector=None  # data-brandnm 속성을 가진 span.item_brand
        )
        
        brand_tag = product.select_one("span.item_brand")
        if brand_tag:
            details["brand"] = brand_tag.get("data-brandnm")

        # 브랜드명의 언더스코어를 공백으로 변환하고 첫 글자를 대문자로
        if details["brand"]:
            details["brand"] = details["brand"].replace("_", " ").title()
        
        product_details.append(details)

    return product_details

def parse_innometsa(soup, items_per_site):
    """Innometsa 사이트의 검색 결과 파싱"""
    products = soup.select("div.xans-search-result.prd_list > ul > li")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="img.prdImg",  # 이미지
            name_selector= "h3.name span",  # 상품명
            url_selector="h3.name a",  # URL
            product_url_prefix="https://innometsa.com",
            price_selector="p.price span.sale_price",
            brand_selector="h4.brand"  # 브랜드
        )
        
        if details["name"]:
            # 괄호로 시작하는 부분 이후 내용 제거
            if '(' in details["name"] :
                details["name"] = details["name"][:details["name"].find('(')].strip()
                
        
        product_details.append(details)

    return product_details

def parse_bibliotheque(soup, items_per_site):
    """Bibliotheque 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid_tll2 > li.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.thumbnail img.thumb",  # 이미지
            name_selector="strong.name span:nth-of-type(2)",  # 상품명
            url_selector="div.thumbnail a",  # URL
            product_url_prefix="https://bibliotheque.co.kr",
            price_selector=None,  # 판매가격
            brand_selector="h3.prd_brand_name"  # 브랜드
        )
        
        # 1. 상품명 처리
        if details["name"]:
            # 대괄호로 둘러싸인 부분 제거
            details["name"] = re.sub(r'\[[^\]]*\]\s*', '', details["name"])
            details["name"] = details["name"].strip()
        
        # 2. URL 처리
        if details["product_url"]:
            # '/product/' 이후의 부분에서만 '-입고-' 제거
            url_parts = details["product_url"].split('/product/', 1)
            if len(url_parts) > 1:
                url_parts[1] = re.sub(r'.*-입고-', '', url_parts[1])
                details["product_url"] = f"{url_parts[0]}/product/{url_parts[1]}"
        
        # 3. 가격 추출 
        price_label = product.find('span', string='판매가')
        if price_label:
            # 판매가 라벨의 다음에서 가격 추출
            price_span = price_label.find_parent('strong').find_next_sibling('span')
            if price_span:
                details["price"] = re.sub(r'[^0-9,]', '', price_span.text.strip())
            
            
        
        product_details.append(details)

    return product_details

def parse_remod(soup, items_per_site):
    """Remod 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid4 > li.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.prdImg img",  # 이미지
            name_selector="strong.name span:nth-of-type(2)",  # 상품명 (두 번째 span)
            url_selector="div.prdImg a",  # URL
            product_url_prefix="https://remod.co.kr",
            price_selector="li[rel='판매가'] > span[style*='font-size:17px']:not(#span_product_tax_type_text)",  # 가격
            brand_selector="li[rel='브랜드'] > span[style*='font-size:12px']"  # 브랜드
        )

        product_details.append(details)

    return product_details

def parse_mmmg(soup, items_per_site):
    """MMMG 사이트의 검색 결과 파싱"""
    products = soup.select("li.list-item.col-6.col-md-3.fs-14.xans-record-")[:items_per_site]
    product_details = []

    for product in products:

        details = extract_product_details(
            product,
            image_selector="img.prd-img",  # 이미지
            name_selector="div.text div.title span",  # 상품명
            url_selector="a",  # URL
            product_url_prefix="https://mmmg.kr",
            price_selector="div.price p.normal-price",  # 가격
            brand_selector=None
        )

        #브랜드 정보 추출 (주석 처리된 부분 포함)
        brand = None
        comments = product.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if 'class="brand"' in comment:
                # 주석에서 브랜드명만 추출
                brand = comment.strip().replace('<div class="brand">', '').replace('</div>', '').strip()
                break
        details["brand"] = brand

        #상품명에서 <br> 태그를 공백으로 변환
        if details["name"]:
            details["name"] = details["name"].replace("\n", " ").strip()
                   
        product_details.append(details)

    return product_details

def parse_jgallery(soup, items_per_site):
    """J-Gallery 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid4 > li.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.thumbnail img",  # 이미지
            name_selector="strong.name span:nth-of-type(2)",  # 상품명 (두 번째 span)
            url_selector="div.thumbnail a",  # URL
            product_url_prefix="https://j-gallery.co.kr",
            price_selector="ul.spec li.xans-record- > span[style*='color:#9e9e9e']:not(.title)",
            brand_selector=None # 브랜드 없음
        )
        
        product_details.append(details)

    return product_details

def parse_wonderaum(soup, items_per_site):
    """Wonderaum 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid4 > li.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.prdImg img",  # 이미지
            name_selector="li.eng_product_name > span[style*='font-size:16px']:not(.title)",  # 한글 상품명
            url_selector="div.prdImg a",  # URL
            product_url_prefix="https://wonderaum.com",
            price_selector="li.product_price > span[style*='font-weight:bold']:not(.title)",  # 가격
            brand_selector="div.brand"
        )
         
        product_details.append(details)

    return product_details

def parse_unwind(soup, items_per_site):
    """Unwind 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid4.m_grid2 > li.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.prdImg img",  # 이미지
            name_selector="strong.name > a > span[style*='color:#282828']:not(.title)",  # 상품명
            url_selector="div.prdImg a",  # URL
            product_url_prefix="https://unwind.kr",
            price_selector="li.product_price > span[style*='color:#282828']:not(.title)",  # 가격
            brand_selector="li.prd_brand > span[style*='color:#a1a1a1']:not(.title)"  # 브랜드
        )
        
        product_details.append(details)

    return product_details

def parse_inscale(soup, items_per_site):
    """Inscale 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid2 > li.prd_list_inner")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.prdImg img",  # 이미지
            name_selector="strong.name > a > span[style*='font-size:14px']:not(.title)",  # 상품명
            url_selector="div.prdImg a",  # URL
            product_url_prefix="https://inscale.co.kr",
            price_selector="li[name='판매가'] > span[style*='font-size:13px']:not(.title)",  # 가격
            brand_selector="li[name='상품요약정보'] > span[style*='font-size:13px']:not(.title)"  # 브랜드
        )
        
        product_details.append(details)

    return product_details

def parse_conranshop(soup, items_per_site):
    """The Conran Shop 사트의 검색 결과 파싱"""
    product_details = []
    
    # 모든 스크립트 태그 찾기
    scripts = soup.find_all('script')
    
    # 상품 정보를 담을 리스트
    products_info = []
    
    # 스크립트에서 모든 상품 정보 추출
    for script in scripts:
        script_text = script.string
        if not script_text:
            continue
            
        # 상품명들 추출
        goodsNm_matches = re.finditer(r'var goodsNm = "([^"]+)"', script_text)
        # 상품번호들 추출
        goodsNo_matches = re.finditer(r"var goodsNo = '([^']+)'", script_text)
        # 가격들 추출
        price_matches = re.finditer(r'<dd class="basic"><span>([0-9,]+)</span>', script_text)
        # 이미지 관련 정보들 추출
        corp_matches = re.finditer(r"var corporationGoodsNo = '([^']+)'", script_text)
        option_matches = re.finditer(r"var optionCode = '([^']+)'", script_text)
        value_matches = re.finditer(r"var optionValueCode = '([^']+)'", script_text)
        # 브랜드명 추출
        brand_pattern = (
            r'strHtml \+=\'[^\']*?<div class="conran_product_attr">[^\']*?\';.*?' +
            r'(?:strHtml \+=\'[^\']*?<strong class="label">for</strong>[^\']*?\';.*?)?' +
            r'strHtml \+=\'[^\']*?<span class="value">([^<]+)</span>[^\']*?\''
        )
        
        brand_matches = re.finditer(
            brand_pattern,
            script_text,
            re.DOTALL
        )
        
        # 각 매치 결과를 리스트로 변환
        goodsNms = [m.group(1) for m in goodsNm_matches]
        goodsNos = [m.group(1) for m in goodsNo_matches]
        prices = [m.group(1) for m in price_matches]
        corps = [m.group(1) for m in corp_matches]
        options = [m.group(1) for m in option_matches]
        values = [m.group(1) for m in value_matches]
        brands = [m.group(1) for m in brand_matches]

        # goodsNo 홀수 제거
        goodsNos = [goodsNo for i, goodsNo in enumerate(goodsNos) if i % 2 == 0]

        # brands
        # ["'+item[i].DSGN_NM+'", "'+dsgrNm+'"] 제거
        brands = [brand.replace("\'+item[i].DSGN_NM+\'", '') for brand in brands]
        brands = [brand.replace("\'+dsgrNm+\'", '') for brand in brands]
        brands = [brand.replace("\'+item[i].BRD_NM+\'", '') for brand in brands]
        # 빈 문자열 제거
        brands = [brand for brand in brands if brand]

        # 모든 정보가 있는 경우에만 상품 정보 생성
        for i in range(min(len(goodsNms), len(goodsNos), len(prices), len(corps), len(options), len(values), len(brands))):
            product_info = {
                'goodsNm': goodsNms[i],
                'goodsNo': goodsNos[i],
                'price': prices[i],
                'corporationGoodsNo': corps[i],
                'optionCode': options[i],
                'optionValueCode': values[i],
                'brand': brands[i]
            }
            products_info.append(product_info)

            if len(products_info) >= items_per_site:
                break
    
    # 각 상품 정보로 최종 결과 생성
    for product in products_info[:items_per_site]:
        # goodsNo에서 숫자만 추출하여 2자리씩 분할
        nums = re.sub(r'[^0-9]', '', product['goodsNo'])[-8:]
        path_parts = [nums[i:i+2] for i in range(0, 8, 2)]
        
        # 이미지 URL 생성
        image_url = f"https://simage.conranshop.kr/goods/{'/'.join(path_parts)}/" + \
                   f"{product['corporationGoodsNo']}_{product['optionCode']}_{product['optionValueCode']}_260.jpg"
        
        details = {
            "image_url": image_url,
            "product_url": f"https://www.conranshop.kr/display/showDisplay.lecs?goodsNo={product['goodsNo']}",
            "name": product['goodsNm'],
            "price": product['price'],
            "brand": product['brand']
        }
        product_details.append(details)

    return product_details

def parse_vorblick(soup, items_per_site):
    """Vorblick 사이트의 검색 결과 파싱"""
    products = soup.select("div.item_gallery_type ul > li")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.item_photo_box img",  # 이미지
            name_selector="div.item_tit_box strong.item_name",  # 상품명
            url_selector="div.item_photo_box a",  # URL
            product_url_prefix="https://www.vorblick.co.kr",
            price_selector="div.item_money_box strong.item_price span",  # 가격
            brand_selector="span.item_brand strong"  # 브랜드 ([Artemide] 형식)
        )
        
        # 브랜드에서 대괄호 제거
        if details["brand"]:
            details["brand"] = details["brand"].strip("[]")
        
        product_details.append(details)

    return product_details

def parse_mignondejjoy(soup, items_per_site):
    """Mignondejjoy 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.grid4 > li.d_item")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.thumbnail img.thum_main_img",  # 메인 이미지
            name_selector="div.description strong.name a > span[style*='font-size:13px']",  # 상품명
            url_selector="div.thumbnail a",  # URL
            product_url_prefix="https://mignondejjoy.com",
            price_selector="ul.spec li.xans-record-:last-child > span[style*='font-size:12px']",  # 가격
            brand_selector="ul.spec li.xans-record-:first-child > span[style*='font-size:10px'][style*='font-weight:bold']"  # 브랜드
        )

        # 품절 체크
        #if product.select_one("div.promotion img[alt='품절']"):
        #    details["price"] = "품절"
        
        product_details.append(details)

    return product_details

def parse_gareem(soup, items_per_site):
    """Gareem 사이트의 검색 결과 파싱"""
    products = soup.select("div.xans-search-result ul.prdList > li")[:items_per_site]
    product_details = []

    for product in products:
        # 기본 상품명 추출
        name_tag = product.select_one("div.description strong.name a > span[style*='font-size:16px']")
        name = name_tag.get_text(strip=True) if name_tag else "No name found"
        
        # 상품간략설명 추출
        desc_tag = product.select_one("ul.spec li.xans-record- > span[style*='font-size:14px']")
        desc = desc_tag.get_text(strip=True) if desc_tag else ""
        
        # 상품명과 설명 합치기
        full_name = f"{name} - {desc}" if desc else name

        details = extract_product_details(
            product,
            image_selector="div.prdImg img.thumb",  # 메인 이미지
            name_selector=None,  # 상품명은 위에서 직접 처리
            url_selector="div.prdImg a",  # URL
            product_url_prefix="https://gareem.com",
            price_selector="div.price_box p.basic_price",  # 가격
            brand_selector=None  # 브랜드 정보 없음
        )

        # 처리된 상품명 적용
        details["name"] = full_name

        product_details.append(details)

    return product_details

def parse_innovad(soup, items_per_site):
    """Innovad 사이트의 검색 결과 파싱"""
    products = soup.select("ul.shop_prd_list > li.prd_layout1")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.prd_thumb img",  # 이미지
            name_selector="div.prd_info a.prd_name",  # 상품명
            url_selector="div.prd_thumb a",  # URL
            product_url_prefix="https://www.innovad.co.kr",
            price_selector="div.prd_cost span:first-child",  # 가격
            brand_selector=None 
        )
        
        
        product_details.append(details)

    return product_details

def parse_chairgallery(soup, items_per_site):
    """Chairgallery 사이트의 검색 결과 파싱"""
    products = soup.select("div.view_box > div.repeat_area")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.box_thumb img",  # 이미지
            name_selector="div.box_content div.text-16.text-bold",  # 상품명
            url_selector="div.box_thumb a",  # URL
            product_url_prefix="https://chairgallery.co.kr",
            price_selector="span.prod_pay",  # 가격
            brand_selector="div.box_content span.body_font_color_70"  # 브랜드
        )



        product_details.append(details)

    return product_details

def parse_nordicpark(soup, items_per_site):
    """Nordicpark 사이트의 검색 결과 파싱"""
    products = soup.select("div.item-cont > dl.item-list")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.main_icons img",  # 이미지
            name_selector="li.prd-name a",  # 상품명
            url_selector="dt.thumb a",  # URL
            product_url_prefix="https://www.nordicpark.co.kr",
            price_selector="li.prd-price span.price",  # 가격
            brand_selector=None
        )

       
        product_details.append(details)

    return product_details

def parse_innohome(soup, items_per_site):
    """Innohome 사이트의 검색 결과 파싱"""
    products = soup.select("div.item.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.prdImg img.thumb",  # 이미지
            name_selector="p.name a > span[style*='font-size:12px']",  # 상품명
            url_selector="div.prdImg a",  # URL
            product_url_prefix="https://innohome.kr",
            price_selector="div.info-wrap div.box-price",  # 가격
            brand_selector=None  # 브랜드는 상품명에서 추출
        )

        # 상품명에서 [Floor Sample] 등의 태그 제거 및 브랜드 추출
        if details["name"]:
            # [Floor Sample] 등의 태그 제거
            name = re.sub(r'\[.*?\]\s*', '', details["name"])
            
            # 브랜드 추출 (하이픈 앞부분)
            brand_match = re.search(r'([^-]+)\s*-\s*(.+)', name)
            if brand_match:
                details["brand"] = brand_match.group(1).strip()
                details["name"] = brand_match.group(2).strip()
            else:
                details["brand"] = None
                details["name"] = name.strip()

        product_details.append(details)

    return product_details

def parse_ilva(soup, items_per_site):
    """Ilva 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList > li.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.thumbnail img",  # 이미지
            name_selector="div.name span",  # 상품명
            url_selector="a",  # URL
            product_url_prefix="https://ilva.co.kr",
            price_selector="li.product_price > span[style*='font-weight:bold']",  # 가격
            brand_selector=None  # 브랜드 없음
        )

        # 상품 설명(사이즈) 추출
        desc_tag = product.select_one("li.simple_desc span[style*='color:#7d7d7d']")
        if desc_tag and details["name"]:
            desc = desc_tag.get_text(strip=True)
            #details["name"] = f"{details['name']} ({desc})"  # 상품명에 사이즈 정보 추가

        details["brand"] = "Ilva"  # 브랜드는 항상 Ilva
        
        product_details.append(details)

    return product_details

def parse_kartellkorea(soup, items_per_site):
    """Kartellkorea 사이트의 검색 결과 파싱"""
    products = soup.select("div.sct_all_wrap")[:items_per_site]
    product_details = []

    for product in products:
        # 기본 정보 추출 (이름, URL, 가격)
        details = extract_product_details(
            product,
            image_selector=None,  # 이미지는 별도 처리
            name_selector="div.sct_txt a",  # 상품명
            url_selector="div.sct_txt a",  # URL
            product_url_prefix="https://kartellkorea.co.kr",
            price_selector="div.sct_cost",  # 가격
            brand_selector=None  # 브랜드 없음
        )

        # 이미지는 이전 형제 요소인 sct_li에서 찾기
        prev_li = product.find_previous("li", class_="sct_li")
        if prev_li:
            img_tag = prev_li.select_one("div.item_img > img")
            details["image_url"] = img_tag["src"] if img_tag else "No image found"

        # 브랜드는 항상 Kartell
        details["brand"] = "Kartell"

        product_details.append(details)

    return product_details
    
def parse_stayh(soup, items_per_site):
    """Stayh 사이트의 검색 결과 파싱"""
    products = soup.select("ul#prdList > li.product_item")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.item_thumb img.prd_img",  # 이미지
            name_selector="div.item_name_box span.info_name span",  # 상품명
            url_selector="div.item_thumb a.img_box",  # URL
            product_url_prefix="https://stayh.co.kr",
            price_selector="li.spec_item.product_price span.spec_info span",  # 가격
            brand_selector="div.item_brand_box span.info_brand_name"  # 브랜드
        )

        product_details.append(details)

    return product_details
    

def parse_segment(soup, items_per_site):
    """Segment 사이트의 검색 결과 파싱"""
    products = soup.select("ul.thumbnail > li.xans-record-")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="div.thumbnail-image img.thumb-img",  # 이미지
            name_selector="p.name span",  # 상품명
            url_selector="div.thumbnail-image a",  # URL
            product_url_prefix="https://segment.kr",
            price_selector="div.price > div:first-child",  # 가격
            brand_selector="p.brand a"  # 브랜드
        )

        # 상품명에서 줄바꿈 처리
        if details["name"]:
            details["name"] = details["name"].replace("\n", " ").replace("  ", " ")

        product_details.append(details)

    return product_details


def parse_arkistore(soup, items_per_site):
    """Arkistore 사이트의 검색 결과 파싱"""
    products = soup.select("ul.prdList.column4 > li.item")[:items_per_site]
    product_details = []

    for product in products:
        details = extract_product_details(
            product,
            image_selector="img.thumb",  # 이미지
            name_selector="ul.xans-product-listitem > li:nth-child(2) > span[style*='color:#262626']",  # 영문상품명
            url_selector="a[name^='anchorBoxName_']",  # URL
            product_url_prefix="https://arkistore.com",
            price_selector="ul.xans-product-listitem > li:nth-child(3) > span[style*='color:#616161']",  # 가격
            brand_selector="ul.xans-product-listitem > li:nth-child(1) > span[style*='color:#a3a3a3']"  # 브랜드
        )

        # 브랜드명에서 대괄호 제거 (예: [&Tradition] -> &Tradition)
        if details["name"]:
            details["name"] = re.sub(r'^\[.*?\]\s*', '', details["name"])

        product_details.append(details)

    return product_details


shop_list = [  {
    "shop": "8COLORS",
    "product_id": "https://www.ssfshop.com/8Seconds",
    "brand_list": [
      "brand_louispoulsen",
      "brand_stringfurniture",
      "brand_gubi"
    ]
  },
  {
    "shop": "EDITORI",
    "product_id": "https://www.editori.kr/",
    "brand_list": [
      "brand_louispoulsen"
    ]
  },
  {
    "shop": "HPIX",
    "product_id": "https://hpix.co.kr",
    "brand_list": [
      "brand_louispoulsen",
      "brand_agolighting",
      "brand_tecta"
    ]
  },
  {
    "shop": "J.GALLERY",
    "product_id": "https://j-gallery.co.kr",
    "brand_list": [
      "brand_karimoku60",
      "brand_karimoku",
      "brand_agolighting"
    ]
  },
  {
    "shop": "COLLECTION B",
    "product_id": "https://www.collectionb.cc/main/index.php",
    "brand_list": [
      "brand_louispoulsen",
      "brand_agolighting"
    ]
  },
  {
    "shop": "JAIME BLANC",
    "product_id": "https://jaimeblanc.com/index.html",
    "brand_list": [
      "brand_louispoulsen",
      "brand_magis",
      "brand_stringfurniture"
    ]
  },
  {
    "shop": "S.HOUZ",
    "product_id": "https://s-houz.com/",
    "brand_list": [
      "brand_louispoulsen"
    ]
  },
  {
    "shop": "DANSK",
    "product_id": "https://www.dansk.co.kr/",
    "brand_list": [
      "brand_louispoulsen",
      "brand_carlhansen&son"
    ]
  },
  {
    "shop": "BENUFE",
    "product_id": "https://benufe.com/",
    "brand_list": [
      "brand_louispoulsen",
      "brand_magis",
      "brand_agolighting"
    ]
  },
  {
    "shop": "INNOMETSA",
    "product_id": "https://innometsa.com/",
    "brand_list": [
      "brand_louispoulsen",
      "brand_hayfur",
      "brand_hayacc",
      "brand_andtrandition",
      "brand_agolighting",
      "brand_stringfurniture",
      "brand_gubi",
      "brand_wildespieth"
    ]
  },
  {
    "shop": "BIBLIOTHEQUE",
    "product_id": "https://www.bibliotheque.co.kr/",
    "brand_list": [
      "brand_louispoulsen",
      "brand_karimoku60",
      "brand_karimoku",
      "brand_cassina",
      "brand_carlhansen&son"
    ]
  },
  {
    "shop": "ROOMING",
    "product_id": "https://www.rooming.co.kr/",
    "brand_list": [
      "brand_louispoulsen",
      "brand_flos",
      "brand_hayfur",
      "brand_hayacc",
      "brand_andtrandition",
      "brand_magis",
      "brand_agolighting",
      "brand_stringfurniture"
    ]
  },
  {
    "shop": "REMOD",
    "product_id": "https://www.remod.co.kr/",
    "brand_list": [
      "brand_karimoku60",
      "brand_karimoku"
    ]
  },
  {
    "shop": "MMMG",
    "product_id": "https://mmmg.kr/",
    "brand_list": [
      "brand_karimoku60",
      "brand_karimoku"
    ]
  },
  {
    "shop": "Wonderaum",
    "product_id": "https://www.wonderaum.com/",
    "brand_list": [
      "brand_karimoku60",
      "brand_karimoku",
      "brand_stringfurniture"
    ]
  },
  {
    "shop": "UNWIND",
    "product_id": "https://unwind.kr/",
    "brand_list": [
      "brand_karimoku60",
      "brand_karimoku",
      "brand_agolighting"
    ]
  },
  {
    "shop": "Inscale",
    "product_id": "https://inscale.co.kr/",
    "brand_list": [
      "brand_virtraacc",
      "brand_vitrafur",
      "brand_carlhansen&son"
    ]
  },
  {
    "shop": "Space+Logic",
    "product_id": "https://spacelogic.co.kr/",
    "brand_list": [
      "brand_cassina",
      "brand_usm",
      "brand_magis"
    ]
  },
  {
    "shop": "The Conran shop",
    "product_id": "https://www.lotteon.com/p/display/shop/seltDpShop/32848",
    "brand_list": [
      "brand_magis",
      "brand_carlhansen&son",
      "brand_agolighting",
      "brand_verpan"
    ]
  },
  {
    "shop": "VORBLICK",
    "product_id": "https://www.vorblick.co.kr/",
    "brand_list": [
      "brand_magis",
      "brand_agolighting"
    ]
  },
  {
    "shop": "MIGNONDEJJOY",
    "product_id": "https://mignondejjoy.com/index.html",
    "brand_list": [
      "brand_carlhansen&son"
    ]
  },
  {
    "shop": "Gareem",
    "product_id": "https://www.gareem.com/",
    "brand_list": [
      "brand_hermanmiller"
    ]
  },
  {
    "shop": "Innovad",
    "product_id": "https://www.innovad.co.kr/",
    "brand_list": [
      "brand_hermanmiller"
    ]
  },
  {
    "shop": "Chair Gallery",
    "product_id": "https://www.chairgallery.co.kr/",
    "brand_list": []
  },
  {
    "shop": "nordicpark",
    "product_id": "https://www.nordicpark.co.kr/",
    "brand_list": [
      "brand_stringfurniture"
    ]
  },
  {
    "shop": "Ton Store",
    "product_id": "https://brand.naver.com/ton",
    "brand_list": [
      "brand_ton"
    ]
  },
  {
    "shop": "Innohome",
    "product_id": "https://innohome.kr/",
    "brand_list": [
      "brand_astep"
    ]
  },
  {
    "shop": "ILVA Korea",
    "product_id": "https://ilva.co.kr/",
    "brand_list": []
  },
  {
    "shop": "Kartell Korea",
    "product_id": "https://kartellkorea.co.kr/",
    "brand_list": []
  },
  {
    "shop": "Stay H",
    "product_id": "https://www.stayh.co.kr/",
    "brand_list": [
      "brand_carlhansen&son"
    ]
  },
  {
    "shop": "Segment",
    "product_id": "https://segment.kr/",
    "brand_list": [
      "brand_fatboy"
    ]
  },
  {
    "shop": "Arki Store",
    "product_id": "https://arkistore.com/",
    "brand_list": []
  },
  {
    "shop": "InART",
    "product_id": "https://www.inartshop.com/main/index",
    "brand_list": [
      "brand_louispoulsen"
    ]
  }]