import os
import re
import pandas as pd
from Bio import Entrez

# Configuration
Entrez.email = "manavvanga@gmail.com" 
Entrez.api_key = os.environ.get('NCBI_API_KEY') 

def fetch_data(query):
    full_query = f"({query}) AND (last 5 years[dp])"
    
    # Increased retmax to 500 for more leads
    search_handle = Entrez.esearch(db="pubmed", term=full_query, retmax=500)
    id_list = Entrez.read(search_handle)["IdList"]

    if not id_list:
        return []

    fetch_handle = Entrez.efetch(db="pubmed", id=id_list, retmode="xml")
    records = Entrez.read(fetch_handle)
    
    results = []
    for article in records['PubmedArticle']:
        try:
            title = article['MedlineCitation']['Article'].get('ArticleTitle', 'N/A')
            keywords = article['MedlineCitation'].get('KeywordList', [[]])
            interest = ", ".join([str(k) for k in keywords[0]]) if keywords else "N/A"
            
            for author in article['MedlineCitation']['Article'].get('AuthorList', []):
                name = f"{author.get('ForeName', '')} {author.get('LastName', '')}"
                affils = author.get('AffiliationInfo', [])
                
                email = "N/A"
                if affils:
                    affiliation_text = affils[0].get('Affiliation', '')
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affiliation_text)
                    email = email_match.group(0) if email_match else "N/A"
                
                if email != "N/A":
                    results.append({
                        "Title": title,
                        "Author": name,
                        "Email": email.lower(), # Save in lowercase for better de-duplication
                        "Area of Interest": interest,
                        "Affiliation": affiliation_text
                    })
        except Exception:
            continue
    return results

if __name__ == "__main__":
    user_query = '("immuno-oncology" OR "tumor immunology" OR "cancer immunotherapy" OR "T-cell killing" OR "NK cell" OR "CAR-T" OR "cytotoxicity") AND ("in vitro" OR "cell culture" OR "monolayer" OR "2D" OR "3D" OR "co-culture" OR "organoid" OR "spheroid")'
    
    # 1. Fetch new data
    new_data = fetch_data(user_query)
    new_df = pd.DataFrame(new_data)

    # 2. De-duplication Logic
    if os.path.exists("leads.csv"):
        # Load existing leads
        existing_df = pd.read_csv("leads.csv")
        # Combine new and old data
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        # Remove duplicates based on the Email column, keeping the first instance
        final_df = combined_df.drop_duplicates(subset=['Email'], keep='first')
    else:
        final_df = new_df

    # 3. Save the clean list
    final_df.to_csv("leads.csv", index=False)
    print(f"leads.csv updated. Total unique contacts: {len(final_df)}")
