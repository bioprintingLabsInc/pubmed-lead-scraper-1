import os, requests, datetime, re, pandas as pd
from Bio import Entrez

# BPL CONFIGURATION
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwwMv_ZVR2FRdorWGLxpb7RiXuPduGVrPNTo3h8HnGrlJmtAq4W2t5FBFgjGysbosU0SA/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

# BPL TARGET KEYWORDS (From image_41405f.png)
TARGET_KEYWORDS = [
    "miniature organoid culture", "miniature spheroid culture", "automated organoid culture",
    "organoid-based disease modeling", "liver organoids", "cerebral organoids",
    "intestinal organoids", "cardiac organoids", "standardized organoid assay",
    "3d cell-based toxicology assay", "3d cell-based high-throughput screening"
]

def scrape():
    print("🎯 BPL Sniper V700: Hunting Specific Research Targets...")
    year = 2026 # Focus on the freshest data for the meeting

    # 1. THE SEARCH: We search for "Organoid" generally first, then filter by your specific list
    search_term = f"(organoid OR spheroid OR 3d cell-based) AND {year}[dp]"
    print(f"🔍 Broad Search: {search_term}")
    
    handle = Entrez.esearch(db="pubmed", term=search_term, retmax=100)
    ids = Entrez.read(handle)["IdList"]

    if not ids: return

    # 2. FETCH & SMART FILTER
    fetch = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
    articles = Entrez.read(fetch)
    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', '').lower()
            
            # THE FILTER: Only keep if the title contains at least one of your BPL keywords
            # OR contains the core components of your keywords
            if not any(keyword in title for keyword in TARGET_KEYWORDS) and "organoid" not in title:
                continue

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    aff_text = aff['Affiliation']
                    # Use a clean regex to find emails
                    found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', aff_text)
                    if found_emails:
                        email = found_emails[0].lower()
                        if "protected" in email: continue
                        
                        leads.append({
                            "title": med.get('ArticleTitle', 'No Title'),
                            "author": f"{auth.get('ForeName','')} {auth.get('LastName','')}",
                            "email": email, 
                            "area": "Organoid",
                            "journal": med.get('Journal', {}).get('Title', 'N/A'),
                            "year": year, 
                            "institution": aff_text[:200],
                            "pmid": str(art['MedlineCitation']['PMID']),
                            "sync_date": today,
                            "source": "BPL_Sniper_V7"
                        })
                        break 
        except: continue

    # 3. CSV BACKUP & PUSH
    if leads:
        pd.DataFrame(leads).to_csv("leads.csv", index=False)
        print(f"✅ Success: Captured {len(leads)} High-Value leads from your list.")
        requests.post(WEBAPP_URL, json={"action": "addLeads", "data": leads})
    else:
        print("🧐 No papers found matching your specific BPL criteria.")

if __name__ == "__main__":
    scrape()
