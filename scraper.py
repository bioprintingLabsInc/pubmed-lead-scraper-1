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
    # 1. READ REMOTE COMMANDS (Sync with Spreadsheet B9, B11, B12)
    query = get_param("last_query.txt", "Organoid")
    start_year = int(get_param("start_year_limit.txt", 2020))
    current_year = int(get_param("year_checkpoint.txt", 2026))

    if current_year < start_year:
        print("🏁 Year range complete.")
        return

    print(f"🎯 BPL Sniper: Hunting '{query}' in {current_year}...")

    # 2. THE SEARCH (Restricted to Title/Abstract + Sniper Filter)
    search_term = f"({query}[Title/Abstract]) AND (human OR 3D OR drug screening) AND {current_year}[dp]"
    
    handle = Entrez.esearch(db="pubmed", term=search_term, retmax=50)
    ids = Entrez.read(handle)["IdList"]

    if not ids:
        print(f"📅 No results for {current_year}. Moving to {current_year - 1}...")
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
            
            # Junk Filter: Block the irrelevant domains we saw earlier
            if any(j in title.lower() for j in ["epilepsy", "dental", "dentistry", "review"]): 
                continue

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    # Regex for clean institutional emails
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

    # 4. SAVE & PUSH
    if leads:
        pd.DataFrame(leads).to_csv("leads.csv", index=False)
        print(f"✅ Success: Saved {len(leads)} leads to leads.csv.")
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})
    else:
        print("🧐 No high-quality leads found in this batch.")

if __name__ == "__main__":
    scrape()
