"""Discover result seasons from the site's results menu, not guessed URLs."""
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


def seasons(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    menu = next(a for a in soup.find_all('a') if a.get_text(strip=True) == 'Αποτελεσματα').parent
    return list(dict.fromkeys((a.get_text(' ', strip=True), urljoin(base, a['href']))
        for a in menu.find_all('a', href=True) if re.fullmatch(r'20\d{2}-20\d{2}', a.get_text(strip=True))))


def content_links(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#wsite-content') or soup
    found = {}
    for a in main.find_all('a', href=True):
        url = urljoin(base, a['href'])
        label = ' '.join(a.get_text(' ', strip=True).replace('\u200b', '').split())
        if label:
            found.setdefault(url, label)
    return [(label, url) for url, label in found.items()]
