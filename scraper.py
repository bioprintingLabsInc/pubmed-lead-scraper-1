import os
import re
import pandas as pd
from Bio import Entrez

# Configuration
Entrez.email = "manavvanga@gmail.com" 
Entrez.api_key = os.environ.get('NCBI_API_KEY') 

def run_scraper():
    # Your specific immuno-oncology query
    query = os.environ.get('SEARCH_KEYWORD', '("immuno-oncology" OR "tumor immunology" OR "cancer immunotherapy" OR "T-cell killing" OR "NK cell" OR "CAR-T" OR "cytotoxicity") AND ("in vitro" OR "cell culture" OR "monolayer" OR "2D" OR "3D" OR "co-culture" OR "organoid" OR "spheroid") AND (last 5 years[dp])')
    
    # 1. Manage Checkpoints & Reset for new keywords
    start_index = 0
    if os.path.exists("last_query.txt"):
        with open("last_query.txt", "r") as f:
            if f.read().strip() != query:
                if os.path.exists("checkpoint.txt"): os.remove("checkpoint.txt")
    
    if os.path.exists("checkpoint.txt"):
        with open("checkpoint.txt", "r") as f:
            start_index = int(f.read().strip())

    # 2. Search PubMed for the next batch of 500
    search_handle = Entrez.esearch(db="pubmed", term=query, retstart=start_index, retmax=500)
    search_results = Entrez.read(search_handle)
    ids = search_results["IdList"]
    total_results = int(search_results.get("Count", 0))

    if not ids:
        print("No more results found.")
        return False

    # 3. Fetch Full XML and Parse 4 Key Fields
    fetch_handle = Entrez.efetch(db="pubmed", id=ids, retmode="xml")
    records = Entrez.read(fetch_handle)
    new_leads = []
    
    for article in records['PubmedArticle']:
        try:
            # Field 1: Title
            title = article['MedlineCitation']['Article'].get('ArticleTitle', 'N/A')
            
            # Field 2: Area of Interest (Keywords & MeSH Terms)
            k_list = article['MedlineCitation'].get('KeywordList', [[]])
            mesh_list = article['MedlineCitation'].get('MeshHeadingList', [])
            mesh_terms = [m['DescriptorName'] for m in mesh_list][:5] # Top 5 MeSH
            interest_tags = list(k_list[0]) + mesh_terms
            area_of_interest = ", ".join([str(k) for k in interest_tags]) if interest_tags else "N/A"
            
            # Field 3 & 4: Author Name & Email
            authors = article['MedlineCitation']['Article'].get('AuthorList', [])
            for author in authors:
                name = f"{author.get('ForeName', '')} {author.get('LastName', '')}"
                affils = author.get('AffiliationInfo', [])
                if affils:
                    affil_text = affils[0].get('Affiliation', '')
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affil_text)
                    if email_match:
                        email = email_match.group(0).lower()
                        new_leads.append({
                            "Title": title,
                            "Author Name": name,
                            "Email": email,
                            "Area of Interest": area_of_interest
                        })
        except Exception as e:
            continue

    # 4. Save and De-duplicate by Email
    new_df = pd.DataFrame(new_leads)
    if os.path.exists("leads.csv") and os.path.getsize("leads.csv") > 0:
        old_df = pd.read_csv("leads.csv")
        # Combine and remove duplicates to keep the list clean
        final_df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset=['Email'], keep='first')
    else:
        final_df = new_df
    
    final_df.to_csv("leads.csv", index=False)
    
    # 5. Update State for the next loop
    with open("checkpoint.txt", "w") as f: f.write(str(start_index + 500))
    with open("last_query.txt", "w") as f: f.write(query)
    
    print(f"Batch complete. Unique leads: {len(final_df)}. Progress: {start_index + 500}/{total_results}")
    return (start_index + 500) < total_results

if __name__ == "__main__":
    run_scraper()
