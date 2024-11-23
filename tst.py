from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.firefox.options import Options
from multiprocessing import Pool, cpu_count
import concurrent.futures

# تنظیمات اولیه
BASE_URL = "https://www.digikala.com"
CATEGORY_URL = "https://www.digikala.com/search/category-food/?page={}"
START_UNIX_TIME = int(time.time())  # زمان شروع مسابقه

def setup_driver():
    """ایجاد یک نمونه جدید از درایور."""
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/120.0")
    
    # تنظیم preferences برای Firefox
    options.set_preference("intl.accept_languages", "en-US, en")
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    
    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(30)
    return driver

def get_total_pages(driver):
    """استخراج تعداد کل صفحات."""
    print("Trying to get total pages...")
    try:
        url = CATEGORY_URL.format(1)
        print(f"Accessing URL: {url}")
        driver.get(url)
        
        # اضافه کردن اسکرول به پایین صفحه
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # تلاش برای یافتن المان با XPath
        pages_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((
                By.XPATH, 
                "/html/body/div[1]/div[1]/div[3]/div[3]/div[1]/div[3]/section[1]/div[2]/div[21]/div/div[2]/span[4]/span"
            ))
        )
        
        total_pages = int(pages_element.text)
        print(f"Found {total_pages} pages")
        
        # ذخیره اسکرین‌شات و HTML برای دیباگ
        driver.save_screenshot("debug_screenshot.png")
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        return total_pages
        
    except Exception as e:
        print(f"Error getting total pages: {str(e)}")
        print("Saving error state...")
        try:
            driver.save_screenshot("error_screenshot.png")
            with open("error_page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except:
            print("Could not save error state")
        return 2

def get_product_links(page):
    """استخراج لینک محصولات از یک صفحه."""
    print(f"Getting products from page {page}...")
    driver = setup_driver()
    try:
        url = CATEGORY_URL.format(page)
        print(f"Accessing URL: {url}")
        driver.get(url)
        time.sleep(3)
        
        # اسکرول به پایین صفحه برای لود شدن همه محصولات
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        try:
            # استفاده از کلاس دقیق محصولات
            products = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR, 
                    "div.product-list_ProductList__item__LiiNI"
                ))
            )
            
            print(f"Found {len(products)} product containers")
            
            links = []
            for product in products:
                try:
                    # پیدا کردن لینک داخل هر محصول
                    link_element = product.find_element(By.TAG_NAME, "a")
                    href = link_element.get_attribute("href")
                    if href and "/product/" in href:
                        links.append(href)
                except Exception as e:
                    print(f"Error extracting link from product: {e}")
                    continue
            
            print(f"Successfully extracted {len(links)} product links from page {page}")
            return links
            
        except Exception as e:
            print(f"Error finding products on page {page}: {e}")
            driver.save_screenshot(f"error_page_{page}.png")
            return []
            
    except Exception as e:
        print(f"Error on page {page}: {e}")
        return []
    finally:
        driver.quit()

def process_product(product_url):
    """پردازش یک محصول."""
    print(f"Processing product: {product_url}")
    driver = setup_driver()
    try:
        driver.get(product_url)
        time.sleep(2)  # کمی صبر می‌کنیم تا صفحه لود شود
        
        # تلاش برای یافتن تصاویر با سلکتورهای مختلف
        try:
            images = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.product-gallery img"))
            )
            urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]
            print(f"Found {len(urls)} images for product")
            return urls
        except Exception as e:
            print(f"Error finding images: {e}")
            return []
    except Exception as e:
        print(f"Error processing product {product_url}: {e}")
        return []
    finally:
        driver.quit()

def filter_images_by_unix(image_urls):
    """فیلتر کردن تصاویر بر اساس زمان Unix در لینک."""
    valid_images = []
    for url in image_urls:
        try:
            unix_time = int(url.split("_")[1].split(".")[0])
            if unix_time >= START_UNIX_TIME:
                valid_images.append(url)
        except Exception as e:
            print(f"Error processing URL: {url} - {e}")
    return valid_images

def wait_for_page_load(driver):
    """انتظار برای لود کامل صفحه."""
    try:
        # انتظار برای لود شدن body
        WebDriverWait(driver, 10).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        # کمی تاخیر اضافی برای لود شدن محتوای داینامیک
        time.sleep(2)
    except Exception as e:
        print(f"Warning: Page load wait failed: {e}")
if __name__ == "__main__":
    print("Starting the scraper...")
    start_time = time.time()
    
    try:
        driver = setup_driver()
        total_pages = get_total_pages(driver)
        driver.quit()
        
        print(f"Will process {total_pages} pages")
        all_product_links = []
        
        # پردازش صفحات در بچ‌های 50 تایی
        BATCH_SIZE = 50
        MAX_WORKERS = 10
        
        for batch_start in range(1, total_pages + 1, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_pages + 1)
            print(f"\nProcessing batch {batch_start} to {batch_end-1}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                batch_pages = range(batch_start, batch_end)
                product_links_lists = list(executor.map(get_product_links, batch_pages))
                batch_links = [link for sublist in product_links_lists if sublist for link in sublist]
                all_product_links.extend(batch_links)
            
            print(f"Batch complete. Total products so far: {len(all_product_links)}")
            
            # ذخیره تدریجی نتایج
            with open("product_links.txt", "w", encoding="utf-8") as f:
                for link in all_product_links:
                    f.write(link + "\n")
            
            # نمایش پیشرفت
            progress = (batch_end - 1) / total_pages * 100
            elapsed_time = time.time() - start_time
            print(f"Progress: {progress:.1f}% | Time elapsed: {elapsed_time:.1f} seconds")
        
        print(f"\nAll done! Total products found: {len(all_product_links)}")
        print(f"Results saved to product_links.txt")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        print(f"Total execution time: {time.time() - start_time} seconds")
