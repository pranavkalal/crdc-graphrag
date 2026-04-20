import os
import requests
import csv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import time

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
    output_csv = os.path.join(repo_root, "data", "pdf_verification_mapping.csv")
    
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/123.0.0.0 Safari/537.36")
    }

    pub_pages = []
    print("Fetching list pages to find publications...")
    for url in url_list:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                text = link.get_text(strip=True)
                if not text:
                    continue
                href_lower = href.lower()
                
                # Exclude 'Read More' or pagination links, try to get actual titles
                if '/publications/' in href_lower and text.lower() != 'read more':
                    full_url = urljoin(base_url, href)
                    if not any(p['url'] == full_url for p in pub_pages):
                        pub_pages.append({'url': full_url, 'title': text})
        except Exception as e:
            print(f"Error: {e}")

    print(f"Found {len(pub_pages)} publication pages. Fetching PDF links...")
    
    mapping = []
    for idx, pub in enumerate(pub_pages, 1):
        try:
            response = requests.get(pub['url'], headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                if '.pdf' in href.lower():
                    full_pdf_url = urljoin(base_url, href)
                    filename = clean_filename(full_pdf_url)
                    mapping.append({
                        'Publication Title': pub['title'],
                        'Filename on Disk': filename,
                        'Is Downloaded': os.path.exists(os.path.join(repo_root, "data", "raw", filename)),
                        'Publication URL': pub['url'],
                        'PDF URL': full_pdf_url
                    })
        except Exception as e:
            print(f"Error on {pub['url']}: {e}")

    # Remove duplicates
    unique_mapping = []
    seen = set()
    for m in mapping:
        key = (m['Publication Title'], m['Filename on Disk'])
        if key not in seen:
            seen.add(key)
            unique_mapping.append(m)

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Publication Title', 'Filename on Disk', 'Is Downloaded', 'Publication URL', 'PDF URL'])
        writer.writeheader()
        writer.writerows(unique_mapping)
        
    print(f"Mapping successfully saved to {output_csv}")

if __name__ == "__main__":
    main()
