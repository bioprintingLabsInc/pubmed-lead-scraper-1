import os, csv
from Bio import Entrez

# SETUP
Entrez.api_key = os.getenv("NCBI_API_KEY") 
Entrez.email = "bioprintinglabsinc@gmail.com" 

def scrape():
    if not os.path.exists("last_query.txt"): return
    with open("last_query.txt", "r") as f: base_query = f.read().strip()
    if not base_query: return
    
    try: 
        with open("year_checkpoint.txt", "r") as f: year = int(f.read().strip())
    except: year = 2026
    try:
        with open("checkpoint.txt", "r") as f: start = int(f.read().strip())
    except: start = 0

    if year < 2021: return

    # SEARCH
    query = f"({base_query}) AND {year}[dp]"
    handle = Entrez.esearch(db="pubmed", term=query, retstart=start, retmax=500)
    search_results = Entrez.read(handle)
    id_list = search_results["IdList"]

    if not id_list:
        with open("year_checkpoint.txt", "w") as f: f.write(str(year - 1))
        with open("checkpoint.txt", "w") as f: f.write("0")
        return

    # FETCH
    fetch = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(fetch)
    
    new_data = []
    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            
            # 1. Extract Journal & Year
            journal = med.get('Journal', {}).get('Title')
            pub_date = med.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {})
            pub_year = pub_date.get('Year')

            # 2. Extract Title
            title = med.get('ArticleTitle', '')

            # STRICT CHECK: Skip if any core field is missing
            if not journal or not pub_year or not title:
                continue 

            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    affiliation_text = aff['Affiliation']
                    
                    # 3. Extract Email
                    if "@" in affiliation_text:
                        email = [w for w in affiliation_text.split() if "@" in w][0].strip('.,').lower()
                        
                        # 4. Extract Author Name
                        full_name = f"{auth.get('ForeName','')} {auth.get('LastName','')}"
                        
                        # 5. Build the 6-Column Row
                        new_data.append([
                            title,            # Column 1: Paper Title
                            full_name,        # Column 2: Author Name
                            email,            # Column 3: Email
                            affiliation_text, # Column 4: Institution/Affiliation
                            journal,          # Column 5: Journal Name
                            pub_year          # Column 6: Published Year
                        ])
                        break 
        except: continue

    # SAVE TO CSV
    file_exists = os.path.isfile("leads.csv")
    with open("leads.csv", "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Title", "Author Name", "Email", "Institution", "Journal", "Year"])
        writer.writerows(new_data)

    with open("checkpoint.txt", "w") as f: f.write(str(start + 500))

if __name__ == "__main__":
    scrape()
