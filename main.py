import os
import re
import sqlite3
import argparse
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# Base URL for resolving relative image paths
DEFAULT_BASE_URL = 'https://old.rybsvaz.cz/pages_cz'


def sanitize_table_name(name):
    """
    Convert a string into a safe SQLite table name.
    """
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip('_').lower()


def resolve_image_url(img_src, base_url):
    if img_src.startswith('http'):
        return img_src
    m = re.search(r"[^/]+_files/(.+)$", img_src)
    if m:
        filename = m.group(1)
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/pages_cz/testrz/obrazky/{filename}"
    return urljoin(base_url, img_src)


def download_image(img_src, images_dir, base_url=None):
    base = base_url or DEFAULT_BASE_URL
    img_url = resolve_image_url(img_src, base)
    filename = os.path.basename(urlparse(img_url).path)
    os.makedirs(images_dir, exist_ok=True)
    local_path = os.path.join(images_dir, filename)
    resp = requests.get(img_url)
    resp.raise_for_status()
    with open(local_path, 'wb') as f:
        f.write(resp.content)
    return local_path


def process_page(source, conn, images_dir, table_override=None):
    # Determine base_url and fetch HTML
    if source.startswith('http'):
        resp = requests.get(source)
        resp.raise_for_status()
        resp.encoding = 'cp1250'
        html = resp.text
        base_url = source
    else:
        # Read local HTML as Windows-1250
        with open(source, 'r', encoding='cp1250', errors='replace') as f:
            html = f.read()
        base_url = DEFAULT_BASE_URL

    # Determine table name
    if table_override:
        table_name = sanitize_table_name(table_override)
    else:
        table_name = sanitize_table_name(source)

    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_number INTEGER,
            question_text TEXT,
            answer_a TEXT,
            answer_b TEXT,
            answer_c TEXT,
            correct_answer TEXT,
            image_path TEXT
        )
    """)

    soup = BeautifulSoup(html, 'html.parser')
    qnum_tags = [b for b in soup.find_all('b') if re.match(r'^\d+\.$', b.get_text(strip=True))]

    for b in qnum_tags:
        qnum = int(b.get_text(strip=True).rstrip('.'))
        parent_td = b.find_parent('td')
        if not parent_td:
            continue
        q_td = parent_td.find_next_sibling('td')
        question_text = q_td.get_text(strip=True) if q_td else ''

        answers = {}
        correct = None
        answers_row = parent_td.find_parent('tr').find_next_sibling('tr')
        if answers_row:
            ans_tbl = answers_row.find('table')
            if ans_tbl:
                for row in ans_tbl.find_all('tr'):
                    letter_td = row.find('td')
                    if not letter_td:
                        continue
                    letter = letter_td.get_text(strip=True).rstrip(')')
                    span = row.find('span')
                    answers[letter] = span.get_text(strip=True) if span else ''
                    if 'spravna' in row.get('onclick', '').lower():
                        correct = letter
        img_tag = b.find_next('img', src=re.compile(r"[^/]+_files/.+\.(jpg|png|gif)$"))
        img_src = img_tag['src'] if img_tag else None
        local_img = download_image(img_src, images_dir, base_url) if img_src else None

        cur.execute(
            f"INSERT INTO {table_name} (question_number, question_text, answer_a, answer_b, answer_c, correct_answer, image_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (qnum, question_text, answers.get('a'), answers.get('b'), answers.get('c'), correct, local_img)
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description='Scrape fish license test pages into a sqlite database with optional table tagging'
    )
    parser.add_argument('sources', nargs='+',
                        help='List of sources in format url_or_path[=table_tag]')
    parser.add_argument('--db', default='fish_license.db', help='SQLite database file name')
    parser.add_argument('--images', default='images', help='Directory to save images')
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.text_factory = lambda b: b.decode('utf-8', 'ignore')

    for src in args.sources:
        if '=' in src:
            source, tag = src.split('=', 1)
        else:
            source, tag = src, None
        print(f"Processing {source} as table '{tag or source}'...")
        process_page(source, conn, args.images, table_override=tag)

    conn.close()
    print("Done.")

if __name__ == '__main__':
    main()

