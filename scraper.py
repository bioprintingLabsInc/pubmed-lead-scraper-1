import os, requests, datetime, re, pandas as pd
from Bio import Entrez

# BPL CONFIGURATION
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwwMv_ZVR2FRdorWGLxpb7RiXuPduGVrPNTo3h8HnGrlJmtAq4W2t5FBFgjGysbosU0SA/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

# MASSIVE JUNK-BLOCKER (Lexical Exclusion)
JUNK_FILTER = ["hair", "follicle", "vision", "cholesterol", "dental", "dentistry", "epilepsy", "review", "meta-analysis"]

def get_param(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            val = f.read().strip()
            return val if val else None
    return None

def scrape():
    print("🎯 BPL Sniper V1000: Initializing Guarded Hunt...")
    
    # READ REMOTE COMMANDS
    query = get_param("last_query.txt", None)
    if not query:
        print("❌ ERROR: No search keyword found in B8. System Halted.")
        return 

    start_year = int(get_param("start_year_limit.txt", 2025) or 2025)
    current_year = int(get_param("year_checkpoint.txt", 2026) or 2026)

    if current_year < start_year: 
        print("🏁 Year range complete.")
        return

    # 1. PRECISION SEARCH (Title/Abstract Only)
    search_term = f"({query}[Title/Abstract]) AND {current_year}[dp]"
    print(f"🔍 Searching PubMed for: {search_term}")
    
    handle = Entrez.esearch(db="pubmed", term=search_term, retmax=50)
    ids = Entrez.read(handle)["IdList"]

    if not ids:
        # Auto-decrement year if no results
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 2. FETCH & DEEP CLEANING
    fetch = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
    articles = Entrez.read(fetch)
    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', 'No Title')
            
            # Junk Filter check
            if any(junk in title.lower() for junk in JUNK_FILTER): continue

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    # Institutional Email Regex
                    found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', aff['Affiliation'])
                    if found_emails:
                        email = found_emails[0].lower()
                        if "protected" in email: continue
                        
                        leads.append({
                            "title": title,
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email, 
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": current_year, 
                            "institution": aff['Affiliation'][:200],
                            "pmid": str(art['MedlineCitation']['PMID']),
                            "sync_date": today,
                            "area": query
                        })
                        break 
        except: continue

    # 3. CSV BACKUP & SYNC ATTEMPT
    if leads:
        pd.DataFrame(leads).to_csv("leads.csv", index=False)
        print(f"✅ Success: {len(leads)} leads saved to leads.csv.")
        # Data is sent to the sheet; B1 Switch determines if it's accepted
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})
    else:
        print("🧐 No high-quality matches. Moving to previous year...")
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))

if __name__ == "__main__":
    scrape()
