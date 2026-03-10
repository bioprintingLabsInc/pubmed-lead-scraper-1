import os, requests, datetime, re, pandas as pd
from Bio import Entrez

# BPL CONFIGURATION
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwwMv_ZVR2FRdorWGLxpb7RiXuPduGVrPNTo3h8HnGrlJmtAq4W2t5FBFgjGysbosU0SA/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

# THE BLACKLIST: If these words appear in the Title, the lead is TRASHED.
JUNK_FILTER = [
    "epilepsy", "dental", "dentistry", "review", "meta-analysis", "soil", 
    "plant", "botanical", "neurology", "clinical trial protocol", "orthodontic",
    "case report", "systematic review", "recommendation", "guideline"
]

def get_param(file, default):
    if os.path.exists(file):
        with open(file, "r") as f: return f.read().strip()
    return default

def scrape():
    print("🎯 BPL Sniper V800: Initializing High-Precision Hunt...")
    
    # Read search parameters from the Handshake files
    query = get_param("last_query.txt", "Organoid")
    start_year = int(get_param("start_year_limit.txt", 2020))
    current_year = int(get_param("year_checkpoint.txt", 2026))

    if current_year < start_year:
        print("🏁 Target Year Range Reached. Mission Complete.")
        return

    # 1. THE SEARCH (Restricting to Title/Abstract for precision)
    search_term = f"({query}[Title/Abstract]) AND (human OR 3D OR drug screening) AND {current_year}[dp]"
    print(f"🔍 Searching: {search_term}")
    
    try:
        handle = Entrez.esearch(db="pubmed", term=search_term, retmax=50)
        ids = Entrez.read(handle)["IdList"]
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    if not ids:
        # Move to the next year if no results found
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 2. FETCH & DEEP CLEAN
    fetch = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
    articles = Entrez.read(fetch)
    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', 'No Title')
            
            # THE SNIPER FILTER: Check against the Blacklist
            if any(junk in title.lower() for junk in JUNK_FILTER):
                continue

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    aff_text = aff['Affiliation']
                    # Institutional Email Regex
                    found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', aff_text)
                    if found_emails:
                        email = found_emails[0].lower()
                        # Final check for masked/protected emails
                        if any(mask in email for mask in ["protected", "email@", "none@"]): continue
                        
                        leads.append({
                            "title": title,
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email, 
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": current_year, 
                            "institution": aff_text[:250],
                            "pmid": str(art['MedlineCitation']['PMID']),
                            "sync_date": today,
                            "area": query
                        })
                        break 
        except: continue

    # 3. CSV BACKUP & GOOGLE SYNC
    if leads:
        pd.DataFrame(leads).to_csv("leads.csv", index=False)
        print(f"✅ Success: Saved {len(leads)} high-quality leads.")
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})
    else:
        print("🧐 No high-quality leads found. Searching next batch...")
        # Move checkpoint if the entire batch was junk
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))

if __name__ == "__main__":
    scrape()
