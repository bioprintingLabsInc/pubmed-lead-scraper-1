import os
import re
import pandas as pd
from Bio import Entrez

# Configuration
Entrez.email = "manavvanga@gmail.com" 
Entrez.api_key = os.environ.get('NCBI_API_KEY') 

def run_scraper():
    query = '("immuno-oncology" OR "tumor immunology" OR "cancer immunotherapy" OR "T-cell killing" OR "NK cell" OR "CAR-T" OR "cytotoxicity") AND ("in vitro" OR "cell culture" OR "monolayer" OR "2D" OR "3D" OR "co-culture" OR "organoid" OR "spheroid") AND (last 5 years[dp])'
    
    # 1. Determine where we left off
    start_index = 0
    if os.path.exists("checkpoint.txt"):
        with open("checkpoint.txt", "r") as f:
            start_index = int(f.read().strip())

    print(f"Starting batch at index: {start_index}")

    # 2. Search for the next 500 IDs
    search_handle = Entrez.esearch(db="pubmed", term=query, retstart=start_index, retmax=500)
    search_results = Entrez.read(search_handle)
    ids = search_results["IdList"]
    total_results = int(search_results["Count"])

    if not ids:
        print("No more results found.")
        return False # Signal to stop the loop

    # 3. Fetch and Parse
    fetch_handle = Entrez.efetch(db="pubmed", id=ids, retmode="xml")
    records = Entrez.read(fetch_handle)
    
    new_leads = []
    for article in records['PubmedArticle']:
        try:
            title = article['MedlineCitation']['Article'].get('ArticleTitle', 'N/A')
            for author in article['MedlineCitation']['Article'].get('AuthorList', []):
                affils = author.get('AffiliationInfo', [])
                if affils:
                    affil_text = affils[0].get('Affiliation', '')
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affil_text)
                    if email_match:
                        new_leads.append({
                            "Title": title,
                            "Author": f"{author.get('ForeName', '')} {author.get('LastName', '')}",
                            "Email": email_match.group(0).lower(),
                            "Affiliation": affil_text
                        })
        except: continue

    # 4. Save and De-duplicate
    df_new = pd.DataFrame(new_leads)
    if os.path.exists("leads.csv"):
        df_old = pd.read_csv("leads.csv")
        df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Email'])
    else:
        df_final = df_new
    
    df_final.to_csv("leads.csv", index=False)

    # 5. Update Checkpoint
    next_index = start_index + 500
    with open("checkpoint.txt", "w") as f:
        f.write(str(next_index))

    print(f"Batch complete. Total leads collected: {len(df_final)}. Progress: {next_index}/{total_results}")
    
    # Return True if there are still more results to get
    return next_index < total_results

if __name__ == "__main__":
    run_scraper()
