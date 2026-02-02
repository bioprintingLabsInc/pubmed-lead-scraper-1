import os
import csv
from Bio import Entrez

# --- CONFIGURATION ---
# This line now correctly pulls your secret from the GitHub environment
Entrez.api_key = os.getenv("NCBI_API_KEY") 
Entrez.email = "bioprintinglabsinc@gmail.com" 

OUTPUT_FILE = "leads.csv"
QUERY_FILE = "last_query.txt"
CHECKPOINT_FILE = "checkpoint.txt" 
YEAR_CHECKPOINT = "year_checkpoint.txt" 
BATCH_SIZE = 500

def get_year_checkpoint():
    if os.path.exists(YEAR_CHECKPOINT):
        with open(YEAR_CHECKPOINT, "r") as f:
            try: return int(f.read().strip())
            except: return 2026
    return 2026

def get_batch_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            try: return int(f.read().strip())
            except: return 0
    return 0

def load_existing_emails():
    emails = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Email"):
                    emails.add(row["Email"].lower().strip())
    return emails

def scrape():
    if not os.path.exists(QUERY_FILE):
        print("No query found.")
        return
    
    with open(QUERY_FILE, "r") as f:
        base_query = f.read().strip()

    current_year = get_year_checkpoint()
    if current_year < 2021:
        print("FINISHED")
        return

    batch_start = get_batch_checkpoint()
    existing_emails = load_existing_emails()
    year_query = f"({base_query}) AND {current_year}[dp]"
    
    search_handle = Entrez.esearch(db="pubmed", term=year_query, retmax=0)
    total_for_year = int(Entrez.read(search_handle)["Count"])
    
    print(f"--- Year: {current_year} | Total: {total_for_year} | DB: {len(existing_emails)} ---")

    if batch_start >= total_for_year or batch_start >= 9999:
        with open(YEAR_CHECKPOINT, "w") as f: f.write(str(current_year - 1))
        with open(CHECKPOINT_FILE, "w") as f: f.write("0")
        return 

    fetch_handle = Entrez.esearch(db="pubmed", term=year_query, retstart=batch_start, retmax=BATCH_SIZE)
    id_list = Entrez.read(fetch_handle)["IdList"]

    if not id_list:
        with open(YEAR_CHECKPOINT, "w") as f: f.write(str(current_year - 1))
        with open(CHECKPOINT_FILE, "w") as f: f.write("0")
        return

    details_handle = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(details_handle)
    
    new_leads = []
    batch_emails = set()

    for article in articles.get('PubmedArticle', []):
        try:
            medline = article['MedlineCitation']['Article']
            title = medline.get('ArticleTitle', 'No Title')
            for author in medline.get('AuthorList', []):
                for aff in author.get('AffiliationInfo', []):
                    aff_text = aff.get('Affiliation', '')
                    if "@" in aff_text:
                        email = [w for w in aff_text.split() if "@" in w][0].strip('.,').lower().strip()
                        name = f"{author.get('ForeName', '')} {author.get('LastName', '')}"
                        if email not in existing_emails and email not in batch_emails:
                            new_leads.append([title, name, email, f"Bioprinting ({current_year})"])
                            batch_emails.add(email)
                        break
        except: continue

    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Title", "Author Name", "Email", "Area of Interest"])
        writer.writerows(new_leads)

    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(batch_start + BATCH_SIZE))
    
    print(f"Added {len(new_leads)} leads. Next: {batch_start + BATCH_SIZE}")

if __name__ == "__main__":
    scrape()
