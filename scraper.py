import os, requests, datetime
from Bio import Entrez

# BPL MASTER CONFIGURATION
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbz_ISRCUV5iIHbN5h2XeiAPX5NnAPldGa2Q7bLJDCDXk8x4RwpSi8TzGYANT-nqxcNSTQ/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

def get_param(filename, default_value):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: return f.read().strip()
    except: pass
    return default_value

def scrape():
    print("🚀 Starting BPL Scientific Lead Hunt (17-Column Sync)...")
    base_query = get_param("last_query.txt", "Organoid")
    limit_start = int(get_param("start_year_limit.txt", 2020))
    current_year = int(get_param("year_checkpoint.txt", 2026))

    if current_year < limit_start: return

    query = f"({base_query}) AND {current_year}[dp]"
    handle = Entrez.esearch(db="pubmed", term=query, retmax=50)
    id_list = Entrez.read(handle)["IdList"]

    if not id_list:
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(fetch_handle)
    new_leads = []
    
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            pmid = str(art['MedlineCitation']['PMID'])
            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    if "@" in aff['Affiliation']:
                        email = [w for w in aff['Affiliation'].split() if "@" in w][0].strip('.,').lower()
                        
                        # 17-COLUMN MAPPING FOR BPL MASTER
                        # Title, Author, Email, Area, Journal, Year, Institution, Status, Bouncer, Sync Date, etc.
                        new_leads.append({
                            "title": med.get('ArticleTitle', 'No Title'),
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email,
                            "area": base_query, # Uses your search term as the area
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": current_year,
                            "institution": aff['Affiliation'][:200], # Keep it clean
                            "status": "NEW",
                            "bouncer": "Pending",
                            "sync_date": today,
                            "pmid": pmid,
                            "source": "GitHub_Scraper_V380"
                        })
                        break
        except: continue

    if new_leads:
        print(f"📤 Pushing {len(new_leads)} leads to BPL Fortress...")
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": new_leads})

if __name__ == "__main__":
    scrape()
