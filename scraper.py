import os
import requests
from Bio import Entrez

# BPL MASTER CONFIGURATION
# ---------------------------------------------------------
# We are hard-coding the URL here because GitHub Secrets is rejecting the paste.
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbz_ISRCUV5iIHbN5h2XeiAPX5NnAPldGa2Q7bLJDCDXk8x4RwpSi8TzGYANT-nqxcNSTQ/exec"
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY") 

def scrape():
    print("🚀 Starting BPL Scientific Lead Hunt...")

    # 1. READ SEARCH PARAMETERS FROM LOCAL FILES (Created by GitHub YAML)
    if not os.path.exists("last_query.txt"): 
        print("❌ Error: No search query found. Flip the switch in Google Sheets first.")
        return
        
    with open("last_query.txt", "r") as f: 
        base_query = f.read().strip()
    with open("start_year_limit.txt", "r") as f:
        limit_start = int(f.read().strip())
    with open("year_checkpoint.txt", "r") as f:
        current_year = int(f.read().strip())

    # Stop if we've reached the end of the requested timeline
    if current_year < limit_start:
        print(f"🏁 Mission Complete: Reached the start year limit ({limit_start}).")
        return

    # 2. THE PubMed SEARCH
    # We hunt by specific year to keep data manageable and structured
    search_term = f"({base_query}) AND {current_year}[dp]"
    print(f"🔍 Hunting PubMed for: {search_term}")
    
    try:
        handle = Entrez.esearch(db="pubmed", term=search_term, retmax=100)
        search_results = Entrez.read(handle)
        id_list = search_results["IdList"]
    except Exception as e:
        print(f"⚠️ PubMed Search Error: {e}")
        return

    # If no results for this year, move the checkpoint to the previous year for the next run
    if not id_list:
        print(f"📅 No more leads for {current_year}. Moving back to {current_year - 1}")
        with open("year_checkpoint.txt", "w") as f: 
            f.write(str(current_year - 1))
        return

    # 3. FETCH & DATA EXTRACTION
    print(f"📥 Found {len(id_list)} IDs. Extracting contact info...")
    fetch_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(fetch_handle)
    
    new_leads = []
    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', 'No Title Available')
            journal = med.get('Journal', {}).get('Title', 'N/A')
            
            for auth in med.get('AuthorList', []):
                # We only want authors with visible emails in their affiliation info
                for aff in auth.get('AffiliationInfo', []):
                    aff_text = aff['Affiliation']
                    if "@" in aff_text:
                        # Extract the email string
                        email = [w for w in aff_text.split() if "@" in w][0].strip('.,').lower()
                        name = f"{auth.get('ForeName','')} {auth.get('LastName','')}"
                        
                        new_leads.append({
                            "title": title,
                            "name": name,
                            "email": email,
                            "affiliation": aff_text,
                            "journal": journal,
                            "year": current_year
                        })
                        break # Found the lead for this article, move to next
        except:
            continue

    # 4. PUSH TO GOOGLE SHEET COMMAND CENTER
    if new_leads:
        print(f"📤 Pushing {len(new_leads)} scientific leads to the BPL Fortress...")
        try:
            r = requests.post(WEBAPP_URL, json={"action": "addLeads", "data": new_leads})
            if r.status_code == 200:
                print("✅ Success: Leads delivered to Google Sheets.")
            else:
                print(f"❌ Delivery Failed: Server responded with code {r.status_code}")
        except Exception as e:
            print(f"❌ Connection Error: Could not reach the Sheet. {e}")
    else:
        print("🧐 No leads with valid emails found in this batch.")

if __name__ == "__main__":
    scrape()
