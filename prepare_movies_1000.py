from pathlib import Path
from urllib.request import Request, urlopen
import csv, io, zipfile, shutil, sys

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
OUT = DATA / 'movies.csv'
URL = 'https://www.kaggle.com/api/v1/datasets/download/harshitshankhdhar/imdb-dataset-of-top-1000-movies-and-tv-shows'

def current_count():
    try:
        with OUT.open(encoding='utf-8-sig', newline='') as f:
            return sum(1 for _ in csv.DictReader(f))
    except Exception:
        return 0

def prepare(force=False):
    if current_count() >= 1000 and not force:
        print('Movies database already contains 1000+ records.')
        return True
    print('Preparing the 1000-movie offline database (one-time download)...')
    try:
        req = Request(URL, headers={'User-Agent':'Mozilla/5.0 AURAVIS/13.5'})
        with urlopen(req, timeout=45) as r:
            payload = r.read()
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            csv_name = next((n for n in z.namelist() if n.lower().endswith('.csv')), None)
            if not csv_name:
                raise RuntimeError('Movie CSV was not found in downloaded archive.')
            raw = z.read(csv_name).decode('utf-8-sig', errors='replace')
        src = list(csv.DictReader(io.StringIO(raw)))
        rows=[]
        seen=set()
        for r in src:
            title=(r.get('Series_Title') or '').strip()
            if not title or title.casefold() in seen:
                continue
            seen.add(title.casefold())
            genre=(r.get('Genre') or 'Movie').strip()
            overview=(r.get('Overview') or '').strip()
            rating=(r.get('IMDB_Rating') or '').strip()
            director=(r.get('Director') or '').strip()
            year=(r.get('Released_Year') or '').strip()
            if year and year not in title:
                overview = (overview + (f' Released in {year}.' if overview else f'Released in {year}.')).strip()
            rows.append({
                'id':len(rows)+1,
                'title':title,
                'genre':genre,
                'description':overview,
                'rating':rating,
                'director':director,
                'url':'https://www.imdb.com/find/?q=' + title.replace(' ','+').replace('&','%26') + '&s=tt&ttype=ft',
                'resource_label':'Open Movie Page'
            })
            if len(rows) == 1000:
                break
        if len(rows) < 950:
            raise RuntimeError(f'Downloaded source yielded only {len(rows)} unique movie records.')
        DATA.mkdir(parents=True, exist_ok=True)
        if OUT.exists():
            shutil.copy2(OUT, DATA / 'movies_150_backup.csv')
        with OUT.open('w', encoding='utf-8-sig', newline='') as f:
            w=csv.DictWriter(f, fieldnames=['id','title','genre','description','rating','director','url','resource_label'])
            w.writeheader(); w.writerows(rows)
        print(f'READY: {len(rows)} real movie records saved to data\\movies.csv')
        print('The file is now local and continues working offline.')
        return True
    except Exception as e:
        print('Could not download the 1000-movie dataset:', e)
        print('AURAVIS will keep using the bundled offline movie database.')
        return False

if __name__ == '__main__':
    prepare('--force' in sys.argv)
