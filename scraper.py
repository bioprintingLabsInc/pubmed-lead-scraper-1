import re
import pandas as pd
from Bio import Entrez
import os

# Identify yourself to NCBI
Entrez.email = "manavvanga@gmail.com" 

def fetch_data(query_or_url):
    # Extract ID if URL is provided
    if "pubmed.ncbi.nlm.nih.gov" in query_or_url:
        pmid = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', query_or_url).group(1)
        id_list = [pmid]
    else:
        # Search by Keyword
        search_handle = Entrez.esearch(db="pubmed", term=query_or_url, retmax=10)
        id_list = Entrez.read(search_handle)["IdList"]

    if not id_list:
        return []

    fetch_handle = Entrez.efetch(db="pubmed", id=id_list, retmode="xml")
    records = Entrez.read(fetch_handle)
    
    results = []
    for article in records['PubmedArticle']:
        title = article['MedlineCitation']['Article'].get('ArticleTitle', 'N/A')
        
        # Area of Interest (Keywords)
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
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affiliation_text)
                email = email_match.group(0) if email_match else "N/A"
            
            results.append({
                "Title": title,
                "Author": name,
                "Email": email,
                "Area of Interest": interest,
                "Affiliation": affiliation_text
            })
    return results

if __name__ == "__main__":
    # Change your keywords/URLs here
    targets = ["CRISPR cancer therapy", "https://pubmed.ncbi.nlm.nih.gov/34251234/"]
    
    all_results = []
    for t in targets:
        all_results.extend(fetch_data(t))
    
    df = pd.DataFrame(all_results)
    df.to_csv("leads.csv", index=False)
    print("leads.csv updated.")
