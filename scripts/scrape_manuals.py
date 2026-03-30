import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import time
import random

def clean_filename(url):
    filename = url.split("/")[-1]
    filename = filename.split("?")[0]
    filename = unquote(filename)
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    return filename

def main():
    url_list = [
        "https://cottoninfo.com.au/publications-by-type/Manuals%20and%20Guides?page=0",
        "https://cottoninfo.com.au/publications-by-type/Manuals%20and%20Guides?page=1"
    ]
    base_url = "https://cottoninfo.com.au"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(repo_root, "data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/123.0.0.0 Safari/537.36")
    }

    pub_links = set()

    print(f"Targeting list pages: {url_list}")
    
    # Step 1: Scrape the list URLs for publication pages
    for url in url_list:
        try:
            print(f"Scraping list page: {url}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                text = link.get_text(strip=True).lower()
                href_lower = href.lower()
                
                # We're already on the "Manuals and Guides" list page, so any
                # link to a publication is inherently a manual or guide
                if '/publications/' in href_lower:
                    full_url = urljoin(base_url, href)
                    pub_links.add(full_url)
                        
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"Error retrieving list page {url}: {e}")

    # Step 2: Now visit each publication page and find the PDF link
    pdf_links = set()
    print(f"\nFound {len(pub_links)} publication pages. Looking for PDFs within them...")
    
    for idx, pub_url in enumerate(pub_links, 1):
        try:
            print(f"[{idx}/{len(pub_links)}] Inspecting {pub_url}...")
            response = requests.get(pub_url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                if '.pdf' in href.lower():
                    full_pdf_url = urljoin(base_url, href)
                    pdf_links.add(full_pdf_url)
                    print(f"  -> Found PDF: {unquote(full_pdf_url.split('/')[-1])}")
                    
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"Error retrieving pub page {pub_url}: {e}")

    # Step 3: Download the collected PDFs
    total_found = len(pdf_links)
    print(f"\nFound {total_found} unique Manual/Guide PDFs to download.")
    
    downloaded_count = 0
    
    for idx, pdf_url in enumerate(pdf_links, 1):
        filename = clean_filename(pdf_url)
        filepath = os.path.join(output_dir, filename)
        
        if os.path.exists(filepath):
            print(f"[{idx}/{total_found}] Skipped: '{filename}' (Already exists)")
            continue
            
        print(f"[{idx}/{total_found}] Downloading: '{filename}' from {pdf_url}")
        
        try:
            pdf_resp = requests.get(pdf_url, headers=headers, stream=True)
            pdf_resp.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in pdf_resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            downloaded_count += 1
            time.sleep(random.uniform(1, 2))
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to download '{filename}': {e}")
        except Exception as e:
            print(f"Error saving '{filename}': {e}")

    print(f"\n--- Download Summary ---")
    print(f"Successfully downloaded {downloaded_count} new files.")
    print(f"All files are stored in: {output_dir}")

if __name__ == "__main__":
    main()
