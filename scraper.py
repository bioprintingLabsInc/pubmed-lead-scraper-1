import os
import requests
from Bio import Entrez

# BPL MASTER CONFIGURATION
# ---------------------------------------------------------
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbz_ISRCUV5iIHbN5h2XeiAPX5NnAPldGa2Q7bLJDCDXk8x4RwpSi8TzGYANT-nqxcNSTQ/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

def get_param(filename, default_value):
    """Safely reads a parameter file or returns a default."""
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return f.read().strip()
    except:
        pass
    return default_value

def scrape():
    print("🚀 Starting BPL Scientific Lead Hunt (Bulletproof V360)...")

    # 1. READ SEARCH PARAMETERS WITH SAFETY DEFAULTS
    # If the files don't exist, we use Organoid/2020/2026 as the baseline
    base_query = get_param("last_query.txt", "Organoid")
    limit_start = int(get_param("start_year_limit.txt", 2020))
    
    # Check the year_checkpoint first, then fall back to the end_year
    current_year = int(get_param("year_checkpoint.txt", 2026))

    print(f"📈 Settings: Query='{base_query}' | Range={limit_start}-{current_year}")

    if current_year < limit_start:
        print(f"🏁 Mission Complete: Reached the start year limit ({limit_start}).")
        return

    # 2. THE PubMed SEARCH
    search_term = f"({base_query}) AND {current_year}[dp]"
    print(f"🔍 Hunting PubMed for: {search_term}")
    
    try:
        handle = Entrez.esearch(db="pubmed", term=search_term, retmax=100)
        search_results = Entrez.read(handle)
        id_list = search_results["IdList"]
    except Exception as e:
        print(f"⚠️ PubMed Search Error: {e}")
        return

    if not id_list:
        print(f"📅 No more leads for {current_year}. Moving back to {current_year - 1}")
        with open("year_checkpoint.txt", "w") as f: 
            f.write(str(current_year - 1))
        return

    # 3. FETCH & DATA EXTRACTION
    print(f"📥 Found {len(id_list)} IDs. Extracting contact info...")
    try:
        fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
        articles = Entrez.read(fetch_handle)
    except Exception as e:
        print(f"⚠️ Fetch Error: {e}")
        return
    
    new_leads = []
    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', 'No Title')
            journal = med.get('Journal', {}).get('Title', 'N/A')
            
            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    aff_text = aff['Affiliation']
                    if "@" in aff_text:
                        email = [w for w in aff_text.split() if "@" in w][0].strip('.,').lower()
                        name = f"{auth.get('ForeName','')} {auth.get('LastName','')}"
                        new_leads.append({
                            "title": title, "name": name, "email": email,
                            "affiliation": aff_text, "journal": journal, "year": current_year
                        })
                        break 
        except:
            continue

    # 4. PUSH TO GOOGLE SHEET
    if new_leads:
        print(f"📤 Pushing {len(new_leads)} scientific leads to the BPL Fortress...")
        try:
            r = requests.post(WEBAPP_URL, json={"action": "addLeads", "data": new_leads})
            print(f"Sheet Response: {r.status_code}")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
    else:
        print("🧐 No valid leads found in this batch.")

if __name__ == "__main__":
    scrape()
