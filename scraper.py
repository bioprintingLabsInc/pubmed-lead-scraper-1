import os
import re
import pandas as pd
from Bio import Entrez

# Configuration
Entrez.email = "manavvanga@gmail.com" 
Entrez.api_key = os.environ.get('NCBI_API_KEY') 

def run_scraper():
    # Pull keyword from GitHub Action input or default to your immuno-oncology query
    query = os.environ.get('SEARCH_KEYWORD', '("immuno-oncology" OR "tumor immunology")')
    
    # 1. Manage Checkpoints & Reset
    start_index = 0
    if os.path.exists("last_query.txt"):
        with open("last_query.txt", "r") as f:
            if f.read().strip() != query:
                print("New keyword detected! Resetting checkpoint.")
                if os.path.exists("checkpoint.txt"): os.remove("checkpoint.txt")
    
    if os.path.exists("checkpoint.txt"):
        with open("checkpoint.txt", "r") as f:
            start_index = int(f.read().strip())

    # 2. Search for next 500
    search_handle = Entrez.esearch(db="pubmed", term=query, retstart=start_index, retmax=500)
    search_results = Entrez.read(search_handle)
    ids = search_results["IdList"]
    total_results = int(search_results.get("Count", 0))

    if not ids: return False

    # 3. Fetch, Parse, and De-duplicate (Simplified)
    fetch_handle = Entrez.efetch(db="pubmed", id=ids, retmode="xml")
    records = Entrez.read(fetch_handle)
    new_leads = []
    for article in records['PubmedArticle']:
        try:
            title = article['MedlineCitation']['Article'].get('ArticleTitle', 'N/A')
            for author in article['MedlineCitation']['Article'].get('AuthorList', []):
                affil = author.get('AffiliationInfo', [{}])[0].get('Affiliation', '')
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affil)
                if email_match:
                    new_leads.append({"Title": title, "Email": email_match.group(0).lower()})
        except: continue

    # 4. Save results
    pd.DataFrame(new_leads).to_csv("leads.csv", mode='a', header=not os.path.exists("leads.csv"), index=False)
    
    # 5. Save State
    with open("checkpoint.txt", "w") as f: f.write(str(start_index + 500))
    with open("last_query.txt", "w") as f: f.write(query)
    
    return (start_index + 500) < total_results

if __name__ == "__main__":
    run_scraper()
