import os
import csv
from Bio import Entrez

# --- CONFIGURATION ---
Entrez.email = "manavvanga@gmail.com"  
# The full query that yields 111,947 results
SEARCH_QUERY = '("immuno-oncology" OR "tumor immunology" OR "cancer immunotherapy" OR "T-cell killing" OR "NK cell" OR "CAR-T" OR "cytotoxicity") AND ("in vitro" OR "cell culture" OR "monolayer" OR "2D" OR "3D" OR "co-culture" OR "organoid" OR "spheroid")'
BATCH_SIZE = 500
CHECKPOINT_FILE = "checkpoint.txt"
OUTPUT_FILE = "leads.csv"

def get_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except:
                return 0
    return 0

def save_checkpoint(new_val):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(new_val))

def load_existing_emails():
    """Reads leads.csv to prevent duplicates across runs."""
    existing_emails = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Email"):
                    existing_emails.add(row["Email"].lower().strip())
    return existing_emails

def scrape():
    start_index = get_checkpoint()
    existing_emails = load_existing_emails()
    
    print(f"Loaded {len(existing_emails)} existing unique leads.")
    
    # Get total count from PubMed
    search_handle = Entrez.esearch(db="pubmed", term=SEARCH_QUERY, retmax=0)
    search_results = Entrez.read(search_handle)
    total_count = int(search_results["Count"])
    
    if start_index >= total_count:
        print(f"FINISHED: All {total_count} papers scanned.")
        return False

    print(f"Processing batch: {start_index} to {start_index + BATCH_SIZE} (Total: {total_count})")

    # Fetch IDs
    fetch_handle = Entrez.esearch(db="pubmed", term=SEARCH_QUERY, retstart=start_index, retmax=BATCH_SIZE)
    id_list = Entrez.read(fetch_handle)["IdList"]
    
    if not id_list:
        return False

    # Fetch details
    details_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(details_handle)
    
    new_leads = []
    current_batch_emails = set()

    for article in articles.get('PubmedArticle', []):
        try:
            medline = article['MedlineCitation']['Article']
            title = medline.get('ArticleTitle', 'No Title')
            authors = medline.get('AuthorList', [])
            interest = "Immuno-Oncology / 3D Models"
            
            for author in authors:
                affiliations = author.get('AffiliationInfo', [])
                for aff in affiliations:
                    aff_text = aff.get('Affiliation', '')
                    if "@" in aff_text:
                        # Extract email
                        email = [word for word in aff_text.split() if "@" in word][0].strip('.,').lower().strip()
                        name = f"{author.get('ForeName', '')} {author.get('LastName', '')}"
                        
                        # Deduplication Logic
                        if email not in existing_emails and email not in current_batch_emails:
                            new_leads.append([title, name, email, interest])
                            current_batch_emails.add(email)
                        break 
        except Exception:
            continue

    # Save data
    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Title", "Author Name", "Email", "Area of Interest"])
        writer.writerows(new_leads)

    save_checkpoint(start_index + BATCH_SIZE)
    print(f"Added {len(new_leads)} UNIQUE leads in this batch.")
    return True

if __name__ == "__main__":
    scrape()
