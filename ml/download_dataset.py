import os
import sys
import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')
MOVIES_CSV = os.path.join(DATA_RAW_DIR, 'tmdb_5000_movies.csv')
CREDITS_CSV = os.path.join(DATA_RAW_DIR, 'tmdb_5000_credits.csv')

# Candidate URLs for both files
MOVIES_URLS = [
    "https://huggingface.co/datasets/Adpacci/tmdb-5000/resolve/main/tmdb_5000_movies.csv",
    "https://raw.githubusercontent.com/rengalv/Movies-Data-Analysis-Grab-a-Popcorn/master/tmdb_5000_movies.csv",
    "https://raw.githubusercontent.com/andandandand/CSV-datasets/master/tmdb_5000_movies.csv"
]

CREDITS_URLS = [
    "https://huggingface.co/datasets/Adpacci/tmdb-5000/resolve/main/tmdb_5000_credits.csv",
    "https://raw.githubusercontent.com/andandandand/CSV-datasets/master/tmdb_5000_credits.csv"
]

def download_file(urls, dest_path, description):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000000:
        print(f"[OK] {description} already exists: {dest_path} ({os.path.getsize(dest_path) / (1024*1024):.2f} MB)")
        return True

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    for url in urls:
        print(f"[*] Attempting to download {description} from {url} ...")
        try:
            resp = requests.get(url, stream=True, timeout=60)
            if resp.status_code == 200:
                with open(dest_path, 'wb') as f:
                    downloaded = 0
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            print(f"\r    Downloaded {downloaded / (1024*1024):.2f} MB...", end="", flush=True)
                print(f"\n[SUCCESS] Saved {description} to {dest_path}")
                return True
            else:
                print(f"\n[-] HTTP {resp.status_code} from {url}")
        except Exception as e:
            print(f"\n[-] Failed connecting to {url}: {e}")
    return False

def main():
    print("=" * 60)
    print("TMDB 5000 Movie Dataset Downloader")
    print("=" * 60)
    
    ok_movies = download_file(MOVIES_URLS, MOVIES_CSV, "tmdb_5000_movies.csv")
    ok_credits = download_file(CREDITS_URLS, CREDITS_CSV, "tmdb_5000_credits.csv")
    
    if ok_movies and ok_credits:
        print("\nAll TMDB 5000 dataset files are ready in data/raw/!")
        sys.exit(0)
    else:
        print("\n[!] Could not automatically download TMDB files over network.")
        print("Please place 'tmdb_5000_movies.csv' and 'tmdb_5000_credits.csv' into 'data/raw/'.")
        sys.exit(1)

if __name__ == '__main__':
    main()

