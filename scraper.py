import os, requests, datetime
from Bio import Entrez

# BPL MASTER CONFIGURATION
# ---------------------------------------------------------
# UPDATED WEB APP URL (V410.0)
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwwMv_ZVR2FRdorWGLxpb7RiXuPduGVrPNTo3h8HnGrlJmtAq4W2t5FBFgjGysbosU0SA/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

def get_param(filename, default_value):
    """Safely reads parameter files from the GitHub environment."""
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: return f.read().strip()
    except: pass
    return default_value

def scrape():
    print("🚀 BPL Scientific Lead Hunt: V410.0 Live...")

    # 1. READ PARAMETERS (Sent from your Google Sheet B8, B11, B12)
    base_query = get_param("last_query.txt", "Organoid")
    limit_start = int(get_param("start_year_limit.txt", 2020))
    current_year = int(get_param("year_checkpoint.txt", 2026))

    if current_year < limit_start:
        print(f"🏁 Mission Complete: Reached the start year limit ({limit_start}).")
        return

    # 2. PubMed Hunt Logic
    search_term = f"({base_query}) AND {current_year}[dp]"
    print(f"🔍 Hunting PubMed for: {search_term}")
    
    try:
        handle = Entrez.esearch(db="pubmed", term=search_term, retmax=50)
        search_results = Entrez.read(handle)
        id_list = search_results["IdList"]
    except Exception as e:
        print(f"⚠️ PubMed API Error: {e}")
        return

    if not id_list:
        print(f"📅 No leads for {current_year}. Moving to {current_year - 1}")
        with open("year_checkpoint.txt", "w") as f: f.write(str(current_year - 1))
        return

    # 3. Data Extraction & 17-Column Formatting
    print(f"📥 Extracting contact info for {len(id_list)} scientists...")
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
                    aff_text = aff['Affiliation']
                    if "@" in aff_text:
                        email = [w for w in aff_text.split() if "@" in w][0].strip('.,').lower()
                        
                        # MAPPING TO YOUR 17-COLUMN SHEET (image_5c7058.jpg)
                        new_leads.append({
                            "title": med.get('ArticleTitle', 'No Title'),
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email,
                            "area": base_query,
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": current_year,
                            "institution": aff_text[:250],
                            "status": "NEW",
                            "pmid": pmid,
                            "sync_date": today,
                            "source": "BPL_Cloud_Scraper_V4"
                        })
                        break
        except: continue

    # 4. PUSH TO GOOGLE SHEET
    if new_leads:
        print(f"📤 Pushing {len(new_leads)} leads to the BPL Fortress...")
        try:
            r = requests.post(WEBAPP_URL, json={"action": "addLeads", "data": new_leads})
            print(f"✅ Sheet Status: {r.status_code}")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
    else:
        print("🧐 No valid leads found in this year's batch.")

if __name__ == "__main__":
    scrape()
