import os
import re
import pandas as pd
from Bio import Entrez

# Configuration
# NCBI requires a valid email for their API
Entrez.email = "manavvanga@gmail.com" 
# This pulls the key you saved in GitHub Secrets
Entrez.api_key = os.environ.get('NCBI_API_KEY') 

def fetch_data(query):
    # This adds the 5-year filter to your specific query
    full_query = f"({query}) AND (last 5 years[dp])"
    
    # We set retmax to 200 to start. You can increase this up to 500 later.
    search_handle = Entrez.esearch(db="pubmed", term=full_query, retmax=200)
    id_list = Entrez.read(search_handle)["IdList"]

    if not id_list:
        return []

    fetch_handle = Entrez.efetch(db="pubmed", id=id_list, retmode="xml")
    records = Entrez.read(fetch_handle)
    
    results = []
    for article in records['PubmedArticle']:
        try:
            title = article['MedlineCitation']['Article'].get('ArticleTitle', 'N/A')
            
            # Area of Interest (Keywords & MeSH Terms)
            keywords = article['MedlineCitation'].get('KeywordList', [[]])
            interest = ", ".join([str(k) for k in keywords[0]]) if keywords else "N/A"
            
            # Authors and Emails
            for author in article['MedlineCitation']['Article'].get('AuthorList', []):
                name = f"{author.get('ForeName', '')} {author.get('LastName', '')}"
                affils = author.get('AffiliationInfo', [])
                
                email = "N/A"
                affiliation_text = "N/A"
                if affils:
                    affiliation_text = affils[0].get('Affiliation', '')
                    # Regex to find the email address
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affiliation_text)
                    email = email_match.group(0) if email_match else "N/A"
                
                # Only add if an email was successfully extracted
                if email != "N/A":
                    results.append({
                        "Title": title,
                        "Author": name,
                        "Email": email,
                        "Area of Interest": interest,
                        "Affiliation": affiliation_text
                    })
        except Exception:
            continue
    return results

if __name__ == "__main__":
    # Your immuno-oncology and cell culture query
    user_query = '("immuno-oncology" OR "tumor immunology" OR "cancer immunotherapy" OR "T-cell killing" OR "NK cell" OR "CAR-T" OR "cytotoxicity") AND ("in vitro" OR "cell culture" OR "monolayer" OR "2D" OR "3D" OR "co-culture" OR "organoid" OR "spheroid")'
    
    data = fetch_data(user_query)
    
    df = pd.DataFrame(data)
    # Save results to the main leads file
    df.to_csv("leads.csv", index=False)
    print(f"leads.csv updated with {len(df)} professional contacts.")
