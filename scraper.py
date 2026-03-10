import os, csv, requests
from Bio import Entrez

def scrape():
    # 1. READ FROM LOCAL FILES (Created by YAML)
    if not os.path.exists("last_query.txt"): return
    with open("last_query.txt", "r") as f: base_query = f.read().strip()
    with open("start_year_limit.txt", "r") as f: limit_start = int(f.read().strip())
    with open("year_checkpoint.txt", "r") as f: current_year = int(f.read().strip())

    if current_year < limit_start: return

    # 2. PubMed Hunt
    Entrez.email = "bioprintinglabsinc@gmail.com"
    query = f"({base_query}) AND {current_year}[dp]"
    handle = Entrez.esearch(db="pubmed", term=query, retmax=100)
    id_list = Entrez.read(handle)["IdList"]

    if not id_list:
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 3. Fetch & Push (Direct to Sheet via WebApp)
    fetch = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(fetch)
    new_leads = []
    
    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    if "@" in aff['Affiliation']:
                        new_leads.append({
                            "title": med.get('ArticleTitle', ''),
                            "name": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": [w for w in aff['Affiliation'].split() if "@" in w][0].strip('.,').lower(),
                            "affiliation": aff['Affiliation'],
                            "journal": med.get('Journal', {}).get('Title'),
                            "year": current_year
                        })
                        break
        except: continue

    if new_leads:
        requests.post(os.getenv("GOOGLE_WEBAPP_URL"), json={"action": "addLeads", "data": new_leads})

if __name__ == "__main__":
    scrape()
