import os, csv, requests
from Bio import Entrez

# BPL CONFIGURATION
Entrez.api_key = os.getenv("NCBI_API_KEY") 
Entrez.email = "bioprintinglabsinc@gmail.com" 
# This is the Web App URL from your Google Sheet 'Deploy' menu
WEBAPP_URL = os.getenv("GOOGLE_WEBAPP_URL") 

def get_fortress_config():
    """
    Pulls live parameters from the Google Sheet Dashboard:
    - Keywords (Cell B8)
    - Start Year (Cell B11)
    - End Year (Cell B12)
    """
    try:
        response = requests.get(f"{WEBAPP_URL}?action=getSettings")
        config = response.json() 
        # Returns: {"query": "Organoid", "start_year": 2020, "end_year": 2026}
        return config
    except Exception as e:
        print(f"Connection Error: Could not reach the Fortress Dashboard. {e}")
        return None

def scrape():
    # 1. Sync with Google Sheet Dashboard
    config = get_fortress_config()
    if not config or not config['query']: 
        print("Waiting for valid Keywords in Google Sheet Cell B8...")
        return
    
    base_query = config['query']
    limit_start = int(config['start_year'])
    limit_end = int(config['end_year'])
    
    # 2. Year Checkpoint Management
    # We prioritize the spreadsheet, but keep a local checkpoint to avoid re-scraping the same year
    try: 
        with open("year_checkpoint.txt", "r") as f: 
            current_year = int(f.read().strip())
    except: 
        current_year = limit_end # Start from the most recent year (2026)

    # If the spreadsheet year is more recent than our checkpoint, override to the spreadsheet
    if limit_end > current_year:
        current_year = limit_end

    if current_year < limit_start: 
        print(f"Search range {limit_start}-{limit_end} complete. Update B11/B12 to expand.")
        return

    # 3. THE PubMed HUNT
    query = f"({base_query}) AND {current_year}[dp]"
    print(f"Hunting PubMed for: {query}")
    
    handle = Entrez.esearch(db="pubmed", term=query, retstart=0, retmax=100)
    search_results = Entrez.read(handle)
    id_list = search_results["IdList"]

    if not id_list:
        # Move to the previous year if current year is exhausted
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 4. FETCH & CLEAN (Strict 6-Column Structure)
    fetch = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(fetch)
    
    new_leads = []
    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', '')
            journal = med.get('Journal', {}).get('Title')
            pub_year = med.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {}).get('Year')

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    aff_text = aff['Affiliation']
                    if "@" in aff_text:
                        email = [w for w in aff_text.split() if "@" in w][0].strip('.,').lower()
                        name = f"{auth.get('ForeName','')} {auth.get('LastName','')}"
                        
                        new_leads.append({
                            "title": title,
                            "name": name,
                            "email": email,
                            "affiliation": aff_text,
                            "journal": journal,
                            "year": pub_year,
                            "status": "NEW" # Auto-triggers the E1 Drip in the Fortress
                        })
                        break 
        except: continue

    # 5. PUSH TO GOOGLE SHEET
    if new_leads:
        response = requests.post(WEBAPP_URL, json={"action": "addLeads", "data": new_leads})
        if response.status_code == 200:
            print(f"Success: {len(new_leads)} leads pushed to {base_query} tab.")
        else:
            print("Failed to push leads. Check Web App URL.")

if __name__ == "__main__":
    scrape()
