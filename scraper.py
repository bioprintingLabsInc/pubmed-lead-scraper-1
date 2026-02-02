import os, csv
from Bio import Entrez

Entrez.api_key = os.getenv("NCBI_API_KEY") 
Entrez.email = "bioprintinglabsinc@gmail.com" 

def scrape():
    if not os.path.exists("last_query.txt"): return
    with open("last_query.txt", "r") as f: base_query = f.read().strip()
    
    try: 
        with open("year_checkpoint.txt", "r") as f: year = int(f.read().strip())
    except: year = 2026
    try:
        with open("checkpoint.txt", "r") as f: start = int(f.read().strip())
    except: start = 0

    if year < 2021: 
        with open("output.log", "w") as f: f.write("FINISHED")
        return

    query = f"({base_query}) AND {year}[dp]"
    handle = Entrez.esearch(db="pubmed", term=query, retstart=start, retmax=500)
    search_results = Entrez.read(handle)
    total_results = int(search_results["Count"])
    id_list = search_results["IdList"]

    if not id_list or start >= total_results:
        with open("year_checkpoint.txt", "w") as f: f.write(str(year - 1))
        with open("checkpoint.txt", "w") as f: f.write("0")
        return

    fetch = Entrez.efetch(db="pubmed", id=",".join(id_list), retmode="xml")
    articles = Entrez.read(fetch)
    
    new_data = []
    for art in articles.get('PubmedArticle', []):
        try:
            med = art['MedlineCitation']['Article']
            title = med.get('ArticleTitle', '')
            for auth in med.get('AuthorList', []):
                for aff in auth.get('AffiliationInfo', []):
                    if "@" in aff['Affiliation']:
                        email = [w for w in aff['Affiliation'].split() if "@" in w][0].strip('.,').lower()
                        new_data.append([title, f"{auth.get('ForeName','')} {auth.get('LastName','')}", email])
                        break
        except: continue

    file_exists = os.path.isfile("leads.csv")
    with open("leads.csv", "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Title", "Author Name", "Email"])
        writer.writerows(new_data)

    with open("checkpoint.txt", "w") as f: f.write(str(start + 500))

if __name__ == "__main__": scrape()
