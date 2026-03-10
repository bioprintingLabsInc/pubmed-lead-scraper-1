import os, requests, datetime, re, pandas as pd
from Bio import Entrez

# BPL CONFIGURATION
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwwMv_ZVR2FRdorWGLxpb7RiXuPduGVrPNTo3h8HnGrlJmtAq4W2t5FBFgjGysbosU0SA/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

# EMAIL VALIDATION REGEX (Blocks junk and protected emails)
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def get_param(file, default):
    if os.path.exists(file):
        with open(file, "r") as f: return f.read().strip()
    return default

def scrape():
    print("🎯 BPL Sniper Mode: Initializing High-Impact Hunt...")
    
    query = get_param("last_query.txt", "Organoid")
    start_limit = int(get_param("start_year_limit.txt", 2020))
    current_year = int(get_param("year_checkpoint.txt", 2026))

    if current_year < start_limit: return

    # 1. SNIPER SEARCH: We target the Title/Abstract specifically for "human" or "3D" relevance
    # This prevents getting irrelevant plant or chemistry papers
    search_term = f"({query}[Title/Abstract]) AND (human OR 3D OR patient-derived) AND {current_year}[dp]"
    print(f"🔍 Precision Searching: {search_term}")
    
    handle = Entrez.esearch(db="pubmed", term=search_term, retmax=50)
    ids = Entrez.read(handle)["IdList"]

    if not ids:
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 2. FETCH & CLEAN
    fetch = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
    articles = Entrez.read(fetch)
    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            pmid = str(art['MedlineCitation']['PMID'])
            title = med.get('ArticleTitle', 'No Title')

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    aff_text = aff['Affiliation']
                    
                    # EXTRACT USING REGEX
                    found_emails = re.findall(EMAIL_REGEX, aff_text)
                    if found_emails:
                        email = found_emails[0].lower()
                        
                        # FILTER OUT FAKE/PROTECTED EMAILS
                        if any(x in email for x in ["protected", "email@", "none@", "example"]):
                            continue
                        
                        leads.append({
                            "title": title,
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email, 
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": current_year, 
                            "institution": aff_text[:250],
                            "pmid": pmid,
                            "sync_date": today
                        })
                        break # Move to next paper once email is found
        except: continue

    # 3. CSV BACKUP & PUSH
    if leads:
        pd.DataFrame(leads).to_csv("leads.csv", index=False)
        print(f"✅ Success: {len(leads)} High-Quality leads captured.")
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})
    else:
        print("🧐 No high-quality leads with valid emails found. Check search precision.")

if __name__ == "__main__":
    scrape()
