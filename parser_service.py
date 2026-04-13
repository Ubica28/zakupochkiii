from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
import logging
from datetime import datetime

# Настройка логирования для отслеживания работы парсера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("parser.log"), logging.StreamHandler()])

# --- Функция парсинга Wildberries ---
# Сохраняем скриншот
driver.save_screenshot(f"debug_{int(time.time())}.png")
# Сохраняем HTML
with open(f"debug_{int(time.time())}.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
def parse_wildberries(url):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)
    try:
        # Ждём появления заголовка
        title_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1.product-page__title, h1[data-link='text\\:productName'], h1[itemprop='name']"))
        )
        title = title_elem.text.strip()
    except:
        title = "Название не найдено"
    
    try:
        # Пробуем несколько вариантов цены
        price_elem = None
        selectors = ["span.price-block__final-price", "span[itemprop='price']", "span.price-block__price", "ins.price-block__final-price"]
        for sel in selectors:
            try:
                price_elem = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                if price_elem.text:
                    break
            except:
                continue
        if price_elem:
            price = price_elem.text.strip()
        else:
            # Пробуем атрибут content
            price_elem = driver.find_element(By.CSS_SELECTOR, "span[itemprop='price']")
            price = price_elem.get_attribute("content")
            if price:
                price = f"{float(price):.2f} ₽"
            else:
                price = "Цена не найдена"
    except:
        price = "Цена не найдена"
    
    driver.quit()
    return title, price

# --- Функция парсинга Ozon ---
def parse_ozon(url):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)
    try:
        # Ждём появления заголовка
        title_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1[data-testid='product-title'], h1[itemprop='name'], div[data-testid='product-title']"))
        )
        title = title_elem.text.strip()
    except:
        title = "Название не найдено"
    
    try:
        # Пробуем найти цену
        price_elem = None
        selectors = ["span[data-testid='price-container'] span", "span[itemprop='price']", "div[data-testid='price-container'] span", "span[class*='price']"]
        for sel in selectors:
            try:
                price_elem = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                if price_elem.text:
                    break
            except:
                continue
        if price_elem:
            price = price_elem.text.strip()
        else:
            price = "Цена не найдена"
    except:
        price = "Цена не найдена"
    
    driver.quit()
    return title, price

# --- Функция парсинга Яндекс.Маркет ---
def parse_yandex_market(url):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)
    try:
        # Ждём заголовка
        title_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1[data-apiary='title'], h1[itemprop='name'], h1[data-auto='product-title']"))
        )
        title = title_elem.text.strip()
    except:
        title = "Название не найдено"
    
    try:
        # Цена
        price_elem = None
        selectors = ["span[data-apiary='price']", "span[itemprop='price']", "span[data-auto='snippet-price-current']"]
        for sel in selectors:
            try:
                price_elem = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                if price_elem.text:
                    break
            except:
                continue
        if price_elem:
            price = price_elem.text.strip()
        else:
            price = "Цена не найдена"
    except:
        price = "Цена не найдена"
    
    driver.quit()
    return title, price

# --- Главная функция обработки ---
def parse_excel_file(file_path='ТОВАРЫ.xlsx'):
    try:
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        logging.error(f"Файл {file_path} не найден.")
        return

    for index, row in df.iterrows():
        url = row['Ссылка']
        if pd.isna(url) or not isinstance(url, str):
            continue
        
        logging.info(f"Обработка: {url}")
        if 'wildberries.ru' in url:
            title, price = parse_wildberries(url)
        elif 'ozon.ru' in url:
            title, price = parse_ozon(url)
        elif 'market.yandex.ru' in url:
            title, price = parse_yandex_market(url)
        else:
            logging.warning(f"Неподдерживаемый маркетплейс: {url}")
            continue
        
        if title and price:
            df.at[index, 'Название'] = title
            df.at[index, 'Цена'] = price
            df.at[index, 'Статус'] = 'Обновлено'
            logging.info(f"Успешно: {title} - {price}")
        else:
            df.at[index, 'Статус'] = 'Ошибка'
            df.at[index, 'Ошибка'] = 'Не удалось получить данные'
            logging.error(f"Ошибка при парсинге: {url}")
        
        time.sleep(2)  # Задержка между запросами
    
    # Сохраняем результат в новый файл с меткой времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"parsed_products_{timestamp}.xlsx"
    df.to_excel(output_file, index=False)
    logging.info(f"Результаты сохранены в {output_file}")

if __name__ == "__main__":
    parse_excel_file()