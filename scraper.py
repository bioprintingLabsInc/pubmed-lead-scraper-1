import os, requests, datetime, pandas as pd
from Bio import Entrez

# BPL CONFIGURATION
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwwMv_ZVR2FRdorWGLxpb7RiXuPduGVrPNTo3h8HnGrlJmtAq4W2t5FBFgjGysbosU0SA/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

def get_param(file, default):
    if os.path.exists(file):
        with open(file, "r") as f: return f.read().strip()
    return default

def scrape():
    print("🚀 Starting BPL Fortress Scraper (CSV Backup Enabled)...")
    query = get_param("last_query.txt", "Organoid")
    start_limit = int(get_param("start_year_limit.txt", 2020))
    current_year = int(get_param("year_checkpoint.txt", 2026))

    if current_year < start_limit:
        print("🏁 Timeline complete.")
        return

    # 1. Search PubMed
    search_term = f"({query}) AND {current_year}[dp]"
    print(f"🔍 Searching: {search_term}")
    handle = Entrez.esearch(db="pubmed", term=search_term, retmax=50)
    ids = Entrez.read(handle)["IdList"]

    if not ids:
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 2. Fetch & Process
    fetch = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
    articles = Entrez.read(fetch)
    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            pmid = str(art['MedlineCitation']['PMID'])
            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    if "@" in aff['Affiliation']:
                        email = [w for w in aff['Affiliation'].split() if "@" in w][0].strip('.,').lower()
                        leads.append({
                            "title": med.get('ArticleTitle', 'No Title'),
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email, 
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": current_year, 
                            "institution": aff['Affiliation'][:250],
                            "pmid": pmid,
                            "sync_date": today
                        })
                        break
        except: continue

    # 3. CSV BACKUP (The "leads.csv" you remembered)
    if leads:
        df = pd.DataFrame(leads)
        df.to_csv("leads.csv", index=False)
        print(f"💾 Saved {len(leads)} leads to leads.csv backup.")

        # 4. PUSH TO GOOGLE SHEET
        print("📤 Delivering to Google Sheets Command Center...")
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})
    else:
        print("🧐 No valid leads found in this batch.")

if __name__ == "__main__":
    scrape()
