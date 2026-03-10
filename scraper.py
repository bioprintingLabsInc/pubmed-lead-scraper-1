import os, requests, datetime
from Bio import Entrez

# BPL CONFIGURATION
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwwMv_ZVR2FRdorWGLxpb7RiXuPduGVrPNTo3h8HnGrlJmtAq4W2t5FBFgjGysbosU0SA/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

def detect_scientific_area(title):
    """Intelligently categorizes the lead based on the Paper Title."""
    t = title.lower()
    if "organoid" in t or "spheroid" in t:
        return "Organoid"
    if "mps" in t or "chip" in t or "microphysiological" in t:
        return "MPS"
    if "nam" in t or "new approach method" in t:
        return "NAMS"
    if "immune" in t or "tumor" in t or "oncology" in t or "cancer" in t:
        return "Immuno Oncology"
    if "microbio" in t or "bacteria" in t or "antimicrobial" in t:
        return "Microbiology"
    return "Organoid" # Default fallback

def scrape():
    print("🚀 Starting BPL Fortress Scraper (Smart Categorization V460)...")
    base_query = os.getenv("QUERY_TO_USE", "Organoid") # Fallback to ENV if file fails
    year = int(datetime.datetime.now().year) # Default to current year for demo speed

    # Search PubMed
    search = f"({base_query}) AND {year}[dp]"
    handle = Entrez.esearch(db="pubmed", term=search, retmax=50)
    ids = Entrez.read(handle)["IdList"]

    if not ids: return

    # Fetch & Map
    fetch = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
    articles = Entrez.read(fetch)
    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', 'No Title')
            
            # SMART CATEGORIZATION HAPPENS HERE
            smart_area = detect_scientific_area(title)
            
            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    if "@" in aff['Affiliation']:
                        email = [w for w in aff['Affiliation'].split() if "@" in w][0].strip('.,').lower()
                        leads.append({
                            "title": title,
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email, 
                            "area": smart_area, # Categorized by Title
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": year, 
                            "institution": aff['Affiliation'][:200], 
                            "status": "NEW",
                            "pmid": str(art['MedlineCitation']['PMID']), 
                            "sync_date": today, 
                            "source": "BPL_Smart_Scraper"
                        })
                        break
        except: continue

    if leads:
        print(f"📤 Pushing {len(leads)} leads...")
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})

if __name__ == "__main__":
    scrape()
