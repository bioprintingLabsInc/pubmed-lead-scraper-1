import os
import csv
from Bio import Entrez

# --- CONFIGURATION ---
Entrez.email = "manavvanga@gmail.com"
CHECKPOINT_FILE = "checkpoint.txt"
OUTPUT_FILE = "leads.csv"
QUERY_FILE = "last_query.txt"
BATCH_SIZE = 500

def get_checkpoint():
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
                if row.get("Email"): emails.add(row["Email"].lower().strip())
    return emails

def scrape():
    # Load query from file
    if not os.path.exists(QUERY_FILE):
        print("No query found in last_query.txt. Please start a search first.")
        return
    with open(QUERY_FILE, "r") as f:
        query = f.read().strip()

    start_index = get_checkpoint()
    existing_emails = load_existing_emails()
    
    # 1. Get Total Count
    search_handle = Entrez.esearch(db="pubmed", term=query, retmax=0)
    total_count = int(Entrez.read(search_handle)["Count"])
    
    if start_index >= total_count:
        print(f"FINISHED: All {total_count} papers scanned.")
        return

    print(f"Batch: {start_index} to {start_index + BATCH_SIZE} | Total: {total_count}")

    # 2. Fetch Data
    fetch_handle = Entrez.esearch(db="pubmed", term=query, retstart=start_index, retmax=BATCH_SIZE)
    id_list = Entrez.read(fetch_handle)["IdList"]
    if not id_list: return

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
                        # Extract email
                        email = [w for w in aff_text.split() if "@" in w][0].strip('.,').lower().strip()
                        name = f"{author.get('ForeName', '')} {author.get('LastName', '')}"
                        # Deduplication logic
                        if email not in existing_emails and email not in batch_emails:
                            new_leads.append([title, name, email, "Immuno-Oncology"])
                            batch_emails.add(email)
                        break
        except: continue

    # 3. Save to leads.csv
    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Title", "Author Name", "Email", "Interest"])
        writer.writerows(new_leads)

    # 4. Update Checkpoint
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(start_index + BATCH_SIZE))
    
    print(f"Added {len(new_leads)} unique leads. Next checkpoint: {start_index + BATCH_SIZE}")

if __name__ == "__main__":
    scrape()
