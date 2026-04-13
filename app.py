# -*- coding: utf-8 -*-
from dotenv import load_dotenv
import os
import sqlite3
import os
import time
import re
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import requests
load_dotenv()

app = Flask(__name__)
CORS(app)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('zakupki.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT,
                  title TEXT,
                  price TEXT,
                  image_url TEXT,
                  priority TEXT,
                  status TEXT,
                  notes TEXT,
                  author TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def add_columns():
    conn = sqlite3.connect('zakupki.db')
    c = conn.cursor()
    try: c.execute('ALTER TABLE items ADD COLUMN notes TEXT')
    except: pass
    try: c.execute('ALTER TABLE items ADD COLUMN author TEXT')
    except: pass
    try: c.execute('ALTER TABLE items ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    except: pass
    conn.commit()
    conn.close()

add_columns()

ALLOWED_USERS = [int(id.strip()) for id in os.getenv('ALLOWED_USERS', '').split(',') if id.strip()]

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

BOT_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram_notification(chat_id, text):
    try:
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        requests.post(TELEGRAM_API_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cats/<filename>')
def cat_image(filename):
    return send_from_directory('cats', filename)

@app.route('/api/cats', methods=['GET'])
def get_cats():
    cats_folder = os.path.join(os.path.dirname(__file__), 'cats')
    if not os.path.exists(cats_folder):
        return jsonify({'images': []})
    files = [f for f in os.listdir(cats_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    return jsonify({'images': files})

# ========== ПАРСИНГ ==========
def extract_url_from_text(text):
    match = re.search(r'https?://\S+', text)
    return match.group(0) if match else text.strip()

def parse_product(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    session = requests.Session()
    session.headers.update(headers)

    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
        final_url = resp.url
        html = resp.text
        print(f"[DEBUG] Финальный URL: {final_url}")
    except Exception as e:
        print(f"[ERROR] Запрос не удался: {e}")
        return None, None, None

    # ---------- Wildberries ----------
    if 'wildberries.ru' in final_url:
        try:
            wb_id_match = re.search(r'/catalog/(\d+)/', final_url)
            if not wb_id_match:
                wb_id_match = re.search(r'[?&]id=(\d+)', final_url)
            if wb_id_match:
                wb_id = wb_id_match.group(1)
                api_url = f'https://card.wb.ru/cards/v2/detail?nm={wb_id}'
                api_headers = {
                    'User-Agent': headers['User-Agent'],
                    'Accept': 'application/json',
                    'Referer': 'https://www.wildberries.ru/',
                }
                api_resp = session.get(api_url, headers=api_headers, timeout=15)
                if api_resp.status_code == 200 and api_resp.text.strip().startswith('{'):
                    data = api_resp.json()
                    if data.get('data', {}).get('products'):
                        prod = data['data']['products'][0]
                        title = prod.get('name')
                        price_val = prod.get('salePriceU') or prod.get('priceU')
                        price = f"{int(price_val) / 100:.2f} ₽" if price_val else "Цена не указана"
                        vol = int(wb_id) // 100000
                        part = int(wb_id) // 1000
                        image_url = f"https://basket-01.wb.ru/vol{vol}/part{part}/{wb_id}/images/big/1.jpg"
                        return title, price, image_url
        except Exception as e:
            print(f"[WB] Ошибка API: {e}")

        if html and isinstance(html, str):
            try:
                title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                    title = re.sub(r'\s+', ' ', title)
                    import html as html_escape
                    title = html_escape.unescape(title)
                    price_match = re.search(r'"price":"(\d+)"', html)
                    price = f"{int(price_match.group(1))} ₽" if price_match else "Цена не указана"
                    return title, price, "https://via.placeholder.com/300?text=Нет+фото"
            except Exception as e:
                print(f"[WB] Ошибка парсинга HTML: {e}")

    # ---------- Ozon ----------
    elif 'ozon.ru' in final_url:
        try:
            ozon_id = None
            patterns = [r'"product_id":"(\d+)"', r'"id":"(\d+)","type":"product"', r'/product/(\d+)']
            for pat in patterns:
                match = re.search(pat, html)
                if match:
                    ozon_id = match.group(1)
                    break
            if ozon_id:
                api_url = f'https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/product/{ozon_id}'
                api_headers = {'User-Agent': headers['User-Agent'], 'Accept': 'application/json'}
                api_resp = session.get(api_url, headers=api_headers, timeout=15)
                data = api_resp.json()
                title = None
                price = None
                image_url = None
                if 'layout' in data and 'widgetStates' in data['layout']:
                    for widget_data in data['layout']['widgetStates'].values():
                        try:
                            w = json.loads(widget_data)
                            if 'trackingData' in w and w['trackingData'].get('name'):
                                title = w['trackingData']['name']
                            if 'price' in w:
                                p = w['price']
                                if isinstance(p, dict) and 'price' in p:
                                    price = f"{p['price']} ₽"
                            if 'images' in w and w['images']:
                                img = w['images'][0]
                                image_url = img.get('link') if isinstance(img, dict) else img
                            if title and price and image_url:
                                break
                        except:
                            continue
                if title:
                    return title, price, image_url
        except Exception as e:
            print(f"[Ozon] Ошибка: {e}")

    # ---------- Яндекс Маркет ----------
    elif 'market.yandex.ru' in final_url:
        try:
            patterns = [
                r'<script type="application/json" data-state="product">(.*?)</script>',
                r'<script id="state" type="application/json">(.*?)</script>',
                r'<script type="application/json">window\.__market__\s*=\s*(.*?);</script>',
            ]
            data = None
            for pat in patterns:
                match = re.search(pat, html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        break
                    except:
                        continue
            if data:
                title = None
                price = None
                image_url = None
                if 'product' in data:
                    p = data['product']
                    title = p.get('name')
                    if 'offers' in p and p['offers']:
                        price_val = p['offers'][0].get('price')
                        if price_val:
                            price = f"{price_val} ₽"
                    if 'images' in p and p['images']:
                        image_url = p['images'][0]
                elif 'offers' in data:
                    title = data.get('name')
                    if data['offers']:
                        price_val = data['offers'][0].get('price')
                        if price_val:
                            price = f"{price_val} ₽"
                    if 'images' in data and data['images']:
                        image_url = data['images'][0]
                if title:
                    return title, price, image_url
        except Exception as e:
            print(f"[Яндекс] Ошибка: {e}")

    return None, None, None

# ========== API ==========
@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    try:
        if 'photo' not in request.files:
            return jsonify({'error': 'Нет файла'}), 400
        file = request.files['photo']
        if file.filename == '':
            return jsonify({'error': 'Пустое имя файла'}), 400
        filename = secure_filename(f"{int(time.time())}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # Возвращаем относительный путь, без домена
        relative_path = f"/uploads/{filename}"
        return jsonify({'url': relative_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parse', methods=['POST'])
def parse_link():
    data = request.json
    user_id = data.get('user_id')
    if user_id not in ALLOWED_USERS:
        return jsonify({'error': 'Доступ запрещён'}), 403
    raw_url = data.get('url', '')
    clean_url = extract_url_from_text(raw_url)
    if not clean_url.startswith('http'):
        fallback_title = raw_url.split('https')[0].strip()
        if fallback_title:
            return jsonify({'title': fallback_title, 'price': '', 'image_url': '', 'fallback': True})
        return jsonify({'error': 'Некорректная ссылка'}), 200
    title, price, image_url = parse_product(clean_url)
    if title:
        return jsonify({'title': title, 'price': price, 'image_url': image_url})
    else:
        fallback_title = raw_url.split('https')[0].strip()
        if fallback_title:
            return jsonify({'title': fallback_title, 'price': '', 'image_url': '', 'fallback': True})
        return jsonify({'error': 'Не удалось распознать товар. Заполните поля вручную.'}), 200

@app.route('/api/add_item', methods=['POST'])
def add_item():
    try:
        data = request.json
        user_id = data.get('user_id')
        if user_id not in ALLOWED_USERS:
            return jsonify({'error': 'Доступ запрещён'}), 403

        url = data.get('url', '')
        title = data.get('title', 'Без названия')
        conn = sqlite3.connect('zakupki.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM items WHERE url=? AND created_at > datetime('now', '-5 seconds')", (url,))
        count = c.fetchone()[0]
        if count > 0:
            conn.close()
            return jsonify({'error': 'Такой товар уже добавлялся только что'}), 409

        priority = data.get('priority', 'medium')
        price = data.get('price', 'Цена не указана')
        image_url = data.get('image_url', 'https://via.placeholder.com/300')
        notes = data.get('notes', '')
        author = data.get('author', 'Гость')
        c.execute('''INSERT INTO items (url, title, price, image_url, priority, status, notes, author, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (url, title, price, image_url, priority, 'active', notes, author, datetime.now().isoformat()))
        conn.commit()
        conn.close()

        send_notification = data.get('send_notification', False)
        if send_notification and user_id:
            msg = f"🛍 <b>Добавлен товар:</b>\n📦 {title}\n💰 {price}\n🔔 Приоритет: {priority}"
            send_telegram_notification(user_id, msg)

        return jsonify({'status': 'ok'})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_items', methods=['POST'])
def get_items():
    try:
        data = request.json
        user_id = data.get('user_id')
        if user_id not in ALLOWED_USERS:
            return jsonify({'error': 'Доступ запрещён'}), 403
        status = data.get('status')
        author_filter = data.get('author_filter', 'all')
        conn = sqlite3.connect('zakupki.db')
        c = conn.cursor()
        query = 'SELECT id, title, price, image_url, priority, notes, created_at, author FROM items WHERE status=?'
        params = [status]
        if author_filter != 'all':
            query += ' AND author=?'
            params.append(author_filter)
        query += ' ORDER BY created_at DESC'
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        items = []
        for r in rows:
            # Не преобразуем URL на сервере, оставляем как есть (относительный или абсолютный)
            items.append({
                'id': r[0], 'title': r[1], 'price': r[2], 'image_url': r[3],
                'priority': r[4], 'notes': r[5], 'created_at': r[6], 'author': r[7]
            })
        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/toggle_status', methods=['POST'])
def toggle_status():
    try:
        data = request.json
        user_id = data.get('user_id')
        if user_id not in ALLOWED_USERS:
            return jsonify({'error': 'Доступ запрещён'}), 403
        item_id = data.get('item_id')
        new_status = data.get('new_status')
        conn = sqlite3.connect('zakupki.db')
        c = conn.cursor()
        c.execute('UPDATE items SET status=? WHERE id=?', (new_status, item_id))
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_item', methods=['POST'])
def delete_item():
    try:
        data = request.json
        user_id = data.get('user_id')
        if user_id not in ALLOWED_USERS:
            return jsonify({'error': 'Доступ запрещён'}), 403
        item_id = data.get('item_id')
        conn = sqlite3.connect('zakupki.db')
        c = conn.cursor()
        c.execute('DELETE FROM items WHERE id=?', (item_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_item_detail', methods=['POST'])
def get_item_detail():
    try:
        data = request.json
        user_id = data.get('user_id')
        if user_id not in ALLOWED_USERS:
            return jsonify({'error': 'Доступ запрещён'}), 403
        item_id = data.get('item_id')
        conn = sqlite3.connect('zakupki.db')
        c = conn.cursor()
        c.execute('SELECT title, price, image_url, priority, url, notes, created_at, author FROM items WHERE id=?', (item_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return jsonify({
                'title': row[0], 'price': row[1], 'image_url': row[2], 'priority': row[3],
                'url': row[4], 'notes': row[5], 'created_at': row[6], 'author': row[7]
            })
        else:
            return jsonify({'error': 'Не найдено'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== ОБНОВЛЕНИЕ ТОВАРА ==========
@app.route('/api/update_item', methods=['POST'])
def update_item():
    try:
        data = request.json
        user_id = data.get('user_id')
        if user_id not in ALLOWED_USERS:
            return jsonify({'error': 'Доступ запрещён'}), 403
        item_id = data.get('id')
        title = data.get('title')
        price = data.get('price')
        image_url = data.get('image_url')
        priority = data.get('priority')
        notes = data.get('notes')
        url = data.get('url')
        conn = sqlite3.connect('zakupki.db')
        c = conn.cursor()
        c.execute('''UPDATE items SET title=?, price=?, image_url=?, priority=?, notes=?, url=? WHERE id=?''',
                  (title, price, image_url, priority, notes, url, item_id))
        conn.commit()
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)