import cloudscraper
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urlparse

# --- AYARLAR ---
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_scraper():
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

def get_video_source(scraper, movie_url):
    """Filmin detay sayfasina girer ve iframe video linkini alir."""
    try:
        # Detay sayfasina git
        response = scraper.get(movie_url, timeout=10)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Iframe'i bul (Eski kodundaki mantik)
        iframe = soup.find('iframe', id='iframe')
        if iframe and 'src' in iframe.attrs:
            return iframe['src']
            
        return None
    except Exception as e:
        print(f"Video linki alinamadi ({movie_url}): {e}")
        return None

def parse_films(soup, base_domain):
    """Sadece listedeki temel bilgileri alir."""
    films = []
    elements = soup.select('li.movie-item') or soup.select('li.item') or soup.find_all('li')

    for el in elements:
        try:
            link_el = el.find('a')
            if not link_el: continue
            
            movie_id = link_el.get('data-id')
            href = link_el.get('href', '')
            
            if href and not href.startswith('http'):
                full_url = base_domain + href
            else:
                full_url = href

            title_el = el.find('span', class_='title') or el.find('h2') or el.find('h3')
            title = title_el.text.strip() if title_el else "Isimsiz"

            img_el = el.find('img')
            image = img_el.get('data-src') or img_el.get('src') or ""

            imdb_el = el.find('span', class_='imdb')
            imdb = imdb_el.text.strip() if imdb_el else "-"
            
            year_el = el.find('span', class_='year')
            year = year_el.text.strip() if year_el else ""

            if title != "Isimsiz" and "dizipal" in full_url:
                films.append({
                    "id": movie_id,
                    "title": title,
                    "image": image,
                    "url": full_url, # Sayfa linki (Video linki asagida alinacak)
                    "imdb": imdb,
                    "year": year
                })
        except:
            continue
    return films

def get_all_films():
    scraper = get_scraper()
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"Derin Tarama Baslatiliyor: {BASE_URL}")
    print("Her filmin icine girilecegi icin islem uzun sürebilir...")
    print("------------------------------------------------")

    # --- 1. SAYFA ---
    try:
        response = scraper.get(BASE_URL, timeout=30)
        if response.status_code != 200:
            print("Siteye girilemedi.")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        new_films = parse_films(soup, base_domain)
        
        # Her bulunan filmin icine girip video linkini alalim
        for f in new_films:
            if f['title'] not in processed_titles:
                print(f"Video aranıyor: {f['title']}...")
                # Burasi filmin icine girdigimiz yer
                video_src = get_video_source(scraper, f['url'])
                
                # Eger video linki bulduysak onu kaydet, bulamazsak sayfa linkini birak
                f['videoUrl'] = video_src if video_src else f['url']
                
                all_films.append(f)
                processed_titles.add(f['title'])
                time.sleep(0.5) # Hizli istek atip engellenmemek icin bekleme
                
        print(f"Sayfa 1 Tamam. ({len(all_films)} Film)")
        
    except Exception as e:
        print(f"Hata: {e}")
        return []

    # --- 2. API DONGUSU ---
    page = 1
    # Test icin sayfa limiti (Istersen 50 yapabilirsin ama sure uzar)
    MAX_PAGES = 100 
    
    while page < MAX_PAGES:
        if not all_films: break
        
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id: break
            
        print(f"Siradaki sayfa listesi cekiliyor (Ref: {last_id})...")
        
        try:
            payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
            response = scraper.post(api_url, data=payload, timeout=20)
            
            try:
                data = response.json()
            except:
                break
                
            if not data or not data.get('html'):
                break
                
            html_part = BeautifulSoup(data['html'], 'html.parser')
            more_films = parse_films(html_part, base_domain)
            
            added_count = 0
            for f in more_films:
                if f['title'] not in processed_titles:
                    # YENI KISIM: Her yeni gelen filmin de içine gir
                    print(f">> Video cekiliyor: {f['title']}")
                    video_src = get_video_source(scraper, f['url'])
                    f['videoUrl'] = video_src if video_src else f['url']
                    
                    all_films.append(f)
                    processed_titles.add(f['title'])
                    added_count += 1
                    time.sleep(0.5) # Bekleme
            
            if added_count == 0:
                print("Yeni film yok. Bitti.")
                break
                
            page += 1
            print(f"--- Sayfa {page} Tamamlandi. Toplam: {len(all_films)} ---")
            
        except Exception as e:
            print(f"Dongu hatasi: {e}")
            break

    return all_films

def create_html(films):
    films_json = json.dumps(films, ensure_ascii=False)
    
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dizipal Ozel Arsiv</title>
    <style>
        body {{ background-color: #141414; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; }}
        .header {{ background: #000; padding: 15px; position: sticky; top:0; z-index:999; display: flex; flex-direction: column; align-items: center; border-bottom: 1px solid #333; }}
        h1 {{ margin: 5px 0; font-size: 1.5rem; color: #E50914; text-transform: uppercase; letter-spacing: 2px; }}
        #searchInput {{ padding: 12px; border-radius: 4px; border: none; width: 90%; max-width: 500px; margin-top: 10px; background: #333; color: white; font-size: 1rem; }}
        
        .container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; padding: 15px; }}
        
        .card {{ background: #1f1f1f; border-radius: 4px; overflow: hidden; position: relative; transition: transform 0.3s; cursor: pointer; }}
        .card:hover {{ transform: scale(1.05); z-index: 10; box-shadow: 0 0 10px rgba(0,0,0,0.5); }}
        .card img {{ width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }}
        
        .info {{ padding: 10px; position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(0,0,0,0.9), transparent); opacity: 0; transition: opacity 0.3s; }}
        .card:hover .info {{ opacity: 1; }}
        
        .title {{ font-weight: bold; font-size: 0.9rem; text-align: center; margin-bottom: 5px; text-shadow: 1px 1px 2px black; }}
        .meta {{ font-size: 0.8rem; color: #ddd; display: flex; justify-content: space-between; padding: 0 5px; }}
        
        .btn-watch {{ display: block; background: #E50914; color: white; text-align: center; text-decoration: none; padding: 8px; margin-top: 5px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }}
        
        #loadMoreBtn {{ display: block; margin: 30px auto; padding: 15px 50px; background: #E50914; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1.1rem; }}
        #loadMoreBtn:hover {{ background: #b20710; }}
        #totalCount {{ font-size: 0.9rem; color: #888; margin-top: 5px; }}
    </style>
</head>
<body>

<div class="header">
    <h1>Dizipal Arsiv</h1>
    <span id="totalCount">Yukleniyor...</span>
    <input type="text" id="searchInput" placeholder="Film, Dizi veya Oyuncu Ara..." oninput="handleSearch()">
</div>

<div class="container" id="filmContainer"></div>
<button id="loadMoreBtn" onclick="loadMore()">Daha Fazla Yukle</button>

<script>
    const allFilms = {films_json};
    let displayedCount = 0;
    const itemsPerPage = 30;
    let currentList = allFilms;

    const container = document.getElementById('filmContainer');
    const loadBtn = document.getElementById('loadMoreBtn');
    const countLabel = document.getElementById('totalCount');

    function createCard(film) {{
        const div = document.createElement('div');
        div.className = 'card';
        // videoUrl varsa onu kullan, yoksa normal url'yi kullan
        const targetLink = film.videoUrl ? film.videoUrl : film.url;
        
        div.innerHTML = `
            <img src="${{film.image}}" loading="lazy" onerror="this.src='https://via.placeholder.com/200x300?text=Resim+Yok'">
            <div class="info">
                <div class="title">${{film.title}}</div>
                <div class="meta">
                    <span>${{film.year}}</span>
                    <span>★ ${{film.imdb}}</span>
                </div>
                <a href="${{targetLink}}" target="_blank" class="btn-watch">IZLE</a>
            </div>
        `;
        // Kartın tamamına tıklayınca git
        div.onclick = function(e) {{
             if(e.target.tagName !== 'A') window.open(targetLink, '_blank');
        }};
        return div;
    }}

    function render() {{
        const nextBatch = currentList.slice(displayedCount, displayedCount + itemsPerPage);
        nextBatch.forEach(film => container.appendChild(createCard(film)));
        displayedCount += nextBatch.length;
        
        loadBtn.style.display = displayedCount >= currentList.length ? 'none' : 'block';
        countLabel.innerText = `Arsivdeki Toplam Icerik: ${{allFilms.length}}`;
    }}

    function loadMore() {{ render(); }}

    function handleSearch() {{
        const query = document.getElementById('searchInput').value.toLowerCase();
        container.innerHTML = '';
        displayedCount = 0;
        currentList = query ? allFilms.filter(f => f.title.toLowerCase().includes(query)) : allFilms;
        render();
    }}

    render();
</script>
</body>
</html>"""
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html_template)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(films, f, ensure_ascii=False)

if __name__ == "__main__":
    data = get_all_films()
    if data:
        create_html(data)
    else:
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write("<h1>Hata: Film verileri alinamadi.</h1>")
