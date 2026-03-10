import os, requests, datetime, re, pandas as pd
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
    # 1. READ REMOTE COMMANDS (From B8 and B11-12 in your Sheet)
    query = get_param("last_query.txt", "Organoid")
    start_limit = int(get_param("start_year_limit.txt", 2020))
    current_year = int(get_param("year_checkpoint.txt", 2026))

    if current_year < start_limit: return

    print(f"🎯 BPL Sniper: Hunting {query} in {current_year}...")

    # 2. PRECISION PubMed SEARCH
    # We search the keyword in the Title/Abstract specifically to avoid 'junk' papers
    search_term = f"({query}[Title/Abstract]) AND (human OR 3D OR patient-derived) AND {current_year}[dp]"
    
    handle = Entrez.esearch(db="pubmed", term=search_term, retmax=50)
    ids = Entrez.read(handle)["IdList"]

    if not ids:
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 3. FETCH & CLEAN
    fetch = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
    articles = Entrez.read(fetch)
    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', 'No Title')
            
            # Junk Filter: Skip papers that are just reviews or unrelated common junk
            if any(junk in title.lower() for junk in ["review", "meta-analysis", "dentistry", "epilepsy"]):
                continue

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    aff_text = aff['Affiliation']
                    found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', aff_text)
                    if found_emails:
                        email = found_emails[0].lower()
                        if "protected" in email: continue
                        
                        leads.append({
                            "title": title,
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email, 
                            "area": query, # Labels the lead by your B8 Keyword
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": current_year, 
                            "institution": aff_text[:250],
                            "pmid": str(art['MedlineCitation']['PMID']),
                            "sync_date": today
                        })
                        break 
        except: continue

    # 4. CSV BACKUP & PUSH
    if leads:
        pd.DataFrame(leads).to_csv("leads.csv", index=False)
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})
