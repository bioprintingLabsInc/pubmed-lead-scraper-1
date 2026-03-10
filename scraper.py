import os, csv, requests
from Bio import Entrez

def scrape():
    # 1. READ FROM LOCAL FILES
    if not os.path.exists("last_query.txt"): 
        print("Error: last_query.txt missing.")
        return
        
    with open("last_query.txt", "r") as f: base_query = f.read().strip()
    with open("start_year_limit.txt", "r") as f: limit_start = int(f.read().strip())
    with open("year_checkpoint.txt", "r") as f: current_year = int(f.read().strip())

    if current_year < limit_start:
        print("Mission Complete: All years reached.")
        return

    # 2. PubMed Hunt
    Entrez.email = "bioprintinglabsinc@gmail.com"
    Entrez.api_key = os.getenv("NCBI_API_KEY")
    query = f"({base_query}) AND {current_year}[dp]"
    
    print(f"Hunting PubMed for: {query}")
    handle = Entrez.esearch(db="pubmed", term=query, retmax=100)
    id_list = Entrez.read(handle)["IdList"]

    if not id_list:
        print(f"No more leads for {current_year}. Moving to {current_year - 1}")
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 3. Fetch & Clean
    fetch = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(fetch)
    new_leads = []
    
    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    if "@" in aff['Affiliation']:
                        email = [w for w in aff['Affiliation'].split() if "@" in w][0].strip('.,').lower()
                        new_leads.append({
                            "title": med.get('ArticleTitle', ''),
                            "name": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email,
                            "affiliation": aff['Affiliation'],
                            "journal": med.get('Journal', {}).get('Title'),
                            "year": current_year
                        })
                        break
        except: continue

    # 4. PUSH TO GOOGLE SHEET
    webapp_url = os.getenv("GOOGLE_WEBAPP_URL")
    if new_leads and webapp_url:
        print(f"Pushing {len(new_leads)} leads to Google Sheets...")
        r = requests.post(webapp_url, json={"action": "addLeads", "data": new_leads})
        print(f"Sheet Response: {r.status_code}")
    else:
        print("No leads found or GOOGLE_WEBAPP_URL is missing.")

if __name__ == "__main__":
    scrape()
