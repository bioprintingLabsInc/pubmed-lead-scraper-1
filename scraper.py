"""
=============================================================
BPL SNIPER V2000 — Full Rebuild
PubMed Lead Scraper with Abstract-Based Category Detection
=============================================================
"""

import os, requests, datetime, re, time
import pandas as pd
from Bio import Entrez

# ── CONFIG ────────────────────────────────────────────────
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://script.google.com/macros/s/AKfycbz9xB0KC4I0Vj9bWWrZXfkb4hTvVMCYUIj2jiJPgXeLSpkS7eS43Sg4B3zJcN2jvHvObA/exec")
Entrez.email = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY", "")

RETMAX = 100  # results per year per run

# ── CATEGORY KEYWORD MAP (title + abstract) ───────────────
CATEGORY_KEYWORDS = {
    "MPS":              ["mps", "organ-on-chip", "organ on chip", "microphysiological", "microfluidic organ"],
    "NAMS":             ["nam", "nams", "new approach method", "non-animal model", "alternative method"],
    "Microbiology":     ["microbiome", "microbial", "bacterio", "microorganism", "gut flora", "pathogen", "microbiota"],
    "Immuno Oncology":  ["immuno-oncology", "immunotherapy", "checkpoint inhibitor", "car-t", "tumor immunology",
                         "cancer immunology", "pd-l1", "pd-1", "ctla-4", "oncolytic", "immuno oncology"],
    "Organoid":         ["organoid", "tubuloïd", "tubuloid", "enteroid", "colonoid", "cerebroid",
                         "liver organoid", "intestinal organoid", "mini-gut", "mini gut"]
}

# ── JUNK FILTER ───────────────────────────────────────────
JUNK_KEYWORDS = [
    "hair follicle", "alopecia", "dental", "dentistry", "epilepsy",
    "cholesterol", "vision loss", "retinal degeneration", "systematic review",
    "meta-analysis", "narrative review", "scoping review"
]

# ── HELPERS ───────────────────────────────────────────────
def read_file(path, default=""):
    if os.path.exists(path):
        val = open(path).read().strip()
        return val if val else default
    return default

def write_file(path, val):
    with open(path, "w") as f:
        f.write(str(val))

def classify(title, abstract):
    """Return category name based on title + abstract keyword match."""
    text = (title + " " + abstract).lower()
    # Priority order matters — most specific first
    for category in ["MPS", "NAMS", "Microbiology", "Immuno Oncology", "Organoid"]:
        for kw in CATEGORY_KEYWORDS[category]:
            if kw in text:
                return category
    return "Organoid"  # fallback

def is_junk(title, abstract):
    text = (title + " " + abstract).lower()
    return any(j in text for j in JUNK_KEYWORDS)

def extract_email(affiliation_str):
    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', affiliation_str)
    for e in emails:
        e = e.lower()
        if "protected" not in e and "example" not in e:
            return e
    return None

# ── MAIN SCRAPE ───────────────────────────────────────────
def scrape():
    print("🎯 BPL Sniper V2000: Initializing...")

    query = read_file("last_query.txt")
    if not query:
        print("❌ No search keyword found. Halted.")
        return

    start_year = int(read_file("start_year_limit.txt", "2020"))
    current_year = int(read_file("year_checkpoint.txt", str(datetime.datetime.now().year)))

    if current_year < start_year:
        print("🏁 Full year range complete. Nothing more to do.")
        write_file("system_status.txt", "COMPLETED")
        return

    write_file("system_status.txt", "RUNNING")

    # Load existing leads for dedup
    existing_emails = set()
    if os.path.exists("leads.csv"):
        try:
            df_existing = pd.read_csv("leads.csv")
            existing_emails = set(df_existing["email"].str.lower().dropna().tolist())
        except Exception:
            pass

    search_term = f"({query}[Title/Abstract]) AND {current_year}[dp]"
    print(f"🔍 Query: {search_term}")

    try:
        handle = Entrez.esearch(db="pubmed", term=search_term, retmax=RETMAX)
        record = Entrez.read(handle)
        ids = record.get("IdList", [])
    except Exception as ex:
        print(f"❌ PubMed search error: {ex}")
        write_file("system_status.txt", "ERROR")
        return

    if not ids:
        print(f"📭 No results for {current_year}. Moving to previous year.")
        write_file("year_checkpoint.txt", str(current_year - 1))
        write_file("system_status.txt", "IDLE")
        return

    print(f"📄 Found {len(ids)} articles for {current_year}.")

    try:
        fetch_handle = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
        articles = Entrez.read(fetch_handle)
    except Exception as ex:
        print(f"❌ PubMed fetch error: {ex}")
        write_file("system_status.txt", "ERROR")
        return

    leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")

    for art in articles.get("PubmedArticle", []):
        try:
            med  = art["MedlineCitation"]["Article"]
            pmid = str(art["MedlineCitation"]["PMID"])

            # ── Title ──────────────────────────────────────
            title = str(med.get("ArticleTitle", "")).strip()
            if not title or title == "No Title":
                continue

            # ── Abstract ───────────────────────────────────
            abstract = ""
            ab_obj = med.get("Abstract", {})
            if ab_obj:
                ab_texts = ab_obj.get("AbstractText", [])
                if isinstance(ab_texts, list):
                    abstract = " ".join(str(x) for x in ab_texts)
                else:
                    abstract = str(ab_texts)

            # ── Junk check ─────────────────────────────────
            if is_junk(title, abstract):
                continue

            # ── Category ───────────────────────────────────
            category = classify(title, abstract)

            # ── Journal ────────────────────────────────────
            journal = med.get("Journal", {}).get("Title", "N/A")

            # ── Authors + emails ───────────────────────────
            for auth in med.get("AuthorList", []):
                for aff_info in auth.get("AffiliationInfo", []):
                    aff_str = aff_info.get("Affiliation", "")
                    email = extract_email(aff_str)
                    if not email:
                        continue
                    if email in existing_emails:
                        continue

                    author_name = f"{auth.get('ForeName', '')} {auth.get('LastName', '')}".strip()

                    leads.append({
                        "category":    category,
                        "title":       title,
                        "author":      author_name,
                        "email":       email,
                        "journal":     journal,
                        "year":        current_year,
                        "institution": aff_str[:250],
                        "sync_date":   today,
                        "pmid":        pmid,
                        "source":      "PubMed_API",
                        "area":        query,
                        "abstract":    abstract[:500]
                    })
                    existing_emails.add(email)
                    break  # one email per author

        except Exception as e:
            print(f"  ⚠️ Parse error on article: {e}")
            continue

    # ── Save & Push ────────────────────────────────────────
    if leads:
        df_new = pd.DataFrame(leads)

        # Merge with existing
        if os.path.exists("leads.csv"):
            df_old = pd.read_csv("leads.csv")
            df_all = pd.concat([df_old, df_new], ignore_index=True)
            df_all.drop_duplicates(subset=["email"], keep="first", inplace=True)
        else:
            df_all = df_new

        df_all.to_csv("leads.csv", index=False)
        print(f"✅ {len(leads)} new leads saved. Total: {len(df_all)}")

        # Push to Google Sheet
        if WEBAPP_URL:
            try:
                resp = requests.post(
                    WEBAPP_URL,
                    json={"action": "addLeads", "data": leads},
                    timeout=30
                )
                print(f"📤 Sheet sync: {resp.status_code}")
            except Exception as ex:
                print(f"⚠️ Sheet sync failed: {ex}")
        else:
            print("⚠️ WEBAPP_URL not set — skipping sheet sync.")
    else:
        print("🧐 No new unique leads with emails this year.")

    # ── Decrement year for next run ────────────────────────
    write_file("year_checkpoint.txt", str(current_year - 1))

    if current_year - 1 < start_year:
        write_file("system_status.txt", "COMPLETED")
        print("🏁 All years scraped. System COMPLETED.")
    else:
        write_file("system_status.txt", "IDLE")
        print(f"📅 Next run will search year: {current_year - 1}")

if __name__ == "__main__":
    scrape()
