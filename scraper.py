import os
import csv
import time
from Bio import Entrez

# --- CONFIGURATION ---
Entrez.email = "your-email@example.com" # Required by NCBI
# Use your full 31,065-result query here:
SEARCH_QUERY = '("immuno-oncology" OR "tumor immunology" OR "cancer immunotherapy" OR "T-cell killing" OR "NK cell" OR "CAR-T" OR "cytotoxicity") AND ("in vitro" OR "cell culture" OR "monolayer" OR "2D" OR "3D" OR "co-culture" OR "organoid" OR "spheroid")'
BATCH_SIZE = 500
CHECKPOINT_FILE = "checkpoint.txt"
OUTPUT_FILE = "leads.csv"

def get_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return int(f.read().strip())
    return 0

def save_checkpoint(new_val):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(new_val))

def scrape():
    start_index = get_checkpoint()
    
    # 1. Get total count to see if we are finished
    print(f"Checking PubMed for: {SEARCH_QUERY}")
    search_handle = Entrez.esearch(db="pubmed", term=SEARCH_QUERY, retmax=0)
    search_results = Entrez.read(search_handle)
    total_count = int(search_results["Count"])
    
    if start_index >= total_count:
        print(f"FINISHED: Checkpoint ({start_index}) reached total results ({total_count}).")
        return False # Signal to stop looping

    print(f"Processing batch: {start_index} to {start_index + BATCH_SIZE} (Total: {total_count})")

    # 2. Fetch IDs for the current batch
    fetch_handle = Entrez.esearch(db="pubmed", term=SEARCH_QUERY, retstart=start_index, retmax=BATCH_SIZE)
    id_list = Entrez.read(fetch_handle)["IdList"]
    
    if not id_list:
        return False

    # 3. Fetch details & extract emails
    details_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(details_handle)
    
    new_leads = []
    for article in articles.get('PubmedArticle', []):
        try:
            medline = article['MedlineCitation']['Article']
            title = medline.get('ArticleTitle', 'No Title')
            authors = medline.get('AuthorList', [])
            
            # Simple area of interest based on your search
            interest = "Immuno-Oncology / 3D Models"
            
            for author in authors:
                affiliations = author.get('AffiliationInfo', [])
                for aff in affiliations:
                    aff_text = aff.get('Affiliation', '')
                    if "@" in aff_text:
                        # Extract email using simple split (or regex)
                        email = [word for word in aff_text.split() if "@" in word][0].strip('.,')
                        name = f"{author.get('ForeName', '')} {author.get('LastName', '')}"
                        new_leads.append([title, name, email, interest])
                        break # Found one email for this article, move to next article
        except Exception as e:
            continue

    # 4. Save to CSV
    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Title", "Author Name", "Email", "Area of Interest"])
        writer.writerows(new_leads)

    save_checkpoint(start_index + BATCH_SIZE)
    print(f"Saved {len(new_leads)} new leads. Next checkpoint: {start_index + BATCH_SIZE}")
    return True

if __name__ == "__main__":
    scrape()
