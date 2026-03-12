"""
=============================================================
BPL SNIPER V2000 — Sheet-Driven Keywords Edition
3D Cell Culture Platform Lead Scraper
Wet lab researchers only — reviews excluded at API level
All keywords come from Google Sheet (JSON files)
=============================================================
"""

import os, re, time, datetime, json
import requests
import pandas as pd
from Bio import Entrez

# ── CONFIG ────────────────────────────────────────────────
WEBAPP_URL     = os.getenv("WEBAPP_URL", "https://script.google.com/macros/s/AKfycbz9xB0KC4I0Vj9bWWrZXfkb4hTvVMCYUIj2jiJPgXeLSpkS7eS43Sg4B3zJcN2jvHvObA/exec")
Entrez.email   = "bioprintinglabsinc@gmail.com"
Entrez.api_key = os.getenv("NCBI_API_KEY", "")
RETMAX         = 200  # per year

# ── ALWAYS-EXCLUDED PUBLICATION TYPES (not user-editable) ─
# These are PubMed [pt] field filters — objective publication type tags
# Reviews, editorials etc. are always excluded — these are not wet lab researchers
PUBMED_EXCLUDE_TYPES = [
    "Review[pt]",
    "Systematic Review[pt]",
    "Meta-Analysis[pt]",
    "Editorial[pt]",
    "Letter[pt]",
    "Comment[pt]",
    "News[pt]",
    "Case Reports[pt]",
    "Retracted Publication[pt]",
    "Preprint[pt]",
]

# These strings appear in the XML PublicationType list — secondary filter
BLOCKED_PUB_TYPE_STRINGS = {
    "review", "systematic review", "meta-analysis", "editorial",
    "letter", "comment", "news", "case reports", "retracted publication",
    "preprint", "published erratum", "expression of concern",
    "guideline", "practice guideline", "lecture",
    "consensus development conference",
}

# ── HELPERS ───────────────────────────────────────────────
def read_file(path, default=""):
    if os.path.exists(path):
        v = open(path).read().strip()
        return v if v else default
    return default

def write_file(path, val):
    open(path, "w").write(str(val))

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def classify(title, abstract, category_keywords):
    """Route to category tab using sheet-provided keywords. First match wins."""
    text = (title + " " + abstract).lower()
    for cat, keywords in category_keywords.items():
        for kw in keywords:
            if kw.lower().strip() in text:
                return cat
    # Fallback to first category
    return list(category_keywords.keys())[0] if category_keywords else "Organoid"

def is_junk(title, abstract, junk_subjects):
    """Skip article if any junk keyword appears in title or abstract."""
    text = (title + " " + abstract).lower()
    return any(j.lower().strip() in text for j in junk_subjects)

def is_review_by_pubtype(article_xml):
    """Secondary check: scan XML PublicationType list."""
    try:
        pub_types = article_xml.get("PubmedData", {}).get("PublicationTypeList", [])
        for pt in pub_types:
            if str(pt).lower() in BLOCKED_PUB_TYPE_STRINGS:
                return True
    except Exception:
        pass
    return False

def extract_email_from_text(text):
    """
    Extract best email from affiliation string.
    Priority 1: 'Electronic address:' — PubMed's explicit corresponding author marker
    Priority 2: Any valid institutional email
    """
    if not text:
        return None
    text = str(text)

    # Priority 1: Electronic address marker
    ea = re.search(
        r'[Ee]lectronic\s+address[:\s]+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
        text
    )
    if ea:
        return ea.group(1).lower().strip(".")

    # Priority 2: Any email
    candidates = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    for email in candidates:
        email = email.lower().strip(".")
        if any(bad in email for bad in ["protected", "example", "doi.org", "elsevier", "springer", "wiley"]):
            continue
        if re.search(r'\.(edu|com|org|net|gov|ac\.[a-z]{2}|[a-z]{2})$', email):
            return email
    return None

def get_abstract(med):
    ab = med.get("Abstract", {})
    if not ab:
        return ""
    texts = ab.get("AbstractText", [])
    if isinstance(texts, list):
        return " ".join(str(x) for x in texts)
    return str(texts)

def get_email_and_author(med):
    """
    4-tier email extraction strategy:
    1. 'Electronic address:' anywhere in any affiliation (most reliable)
    2. Last author affiliations (usually PI / corresponding author)
    3. All authors front-to-back
    4. Combined affiliation string scan
    Returns (email, author_name, affiliation) or (None, None, None)
    """
    authors = med.get("AuthorList", [])
    if not authors:
        return None, None, None

    all_pairs = []  # (author_name, affiliation_string)
    for auth in authors:
        name = f"{auth.get('ForeName', '')} {auth.get('LastName', '')}".strip()
        for aff_info in auth.get("AffiliationInfo", []):
            aff_str = aff_info.get("Affiliation", "")
            if aff_str:
                all_pairs.append((name, aff_str))

    if not all_pairs:
        return None, None, None

    # Tier 1: Electronic address marker
    for name, aff in all_pairs:
        if "lectronic address" in aff:
            email = extract_email_from_text(aff)
            if email:
                return email, name, aff[:300]

    # Tier 2: Last author first (corresponding author convention)
    for name, aff in reversed(all_pairs):
        email = extract_email_from_text(aff)
        if email:
            return email, name, aff[:300]

    # Tier 3: Front-to-back
    for name, aff in all_pairs:
        email = extract_email_from_text(aff)
        if email:
            return email, name, aff[:300]

    # Tier 4: Combined scan
    combined = " ".join(aff for _, aff in all_pairs)
    email = extract_email_from_text(combined)
    if email:
        for name, aff in all_pairs:
            if email in aff.lower():
                return email, name, aff[:300]
        return email, all_pairs[-1][0], combined[:300]

    return None, None, None

# ── MAIN ─────────────────────────────────────────────────
def scrape():
    print("🎯 BPL Sniper V2000 — Sheet-Driven Keywords")
    print("=" * 50)

    # Load query params
    query = read_file("last_query.txt")
    if not query:
        print("❌ No search keyword in last_query.txt — halted.")
        write_file("system_status.txt", "ERROR")
        return

    start_year = int(read_file("start_year_limit.txt", "2020"))
    end_year   = int(read_file("year_checkpoint.txt", str(datetime.datetime.now().year)))

    # Load keywords from sheet-generated JSON files
    if not os.path.exists("category_keywords.json"):
        print("❌ category_keywords.json not found — check Keywords tab in sheet")
        write_file("system_status.txt", "ERROR")
        return

    if not os.path.exists("exclude_keywords.json"):
        print("❌ exclude_keywords.json not found — check Keywords tab in sheet")
        write_file("system_status.txt", "ERROR")
        return

    try:
        category_keywords = load_json("category_keywords.json")
        exclude_data      = load_json("exclude_keywords.json")
        junk_subjects     = exclude_data.get("junk_subjects", [])

        print(f"✅ {len(category_keywords)} categories loaded:")
        for cat, kws in category_keywords.items():
            print(f"   {cat}: {len(kws)} keywords")
        print(f"✅ {len(junk_subjects)} junk filters loaded")
    except Exception as ex:
        print(f"❌ Failed to load keyword files: {ex}")
        write_file("system_status.txt", "ERROR")
        return

    print(f"\n📋 Query: '{query}'  |  Years: {start_year}–{end_year}")

    if end_year < start_year:
        print("🏁 All years already processed.")
        write_file("system_status.txt", "COMPLETED")
        return

    write_file("system_status.txt", "RUNNING")

    # Load existing for dedup
    existing_emails = set()
    existing_pmids  = set()
    if os.path.exists("leads.csv"):
        try:
            df_old = pd.read_csv("leads.csv")
            if "email" in df_old.columns:
                existing_emails = set(df_old["email"].str.lower().dropna().tolist())
            if "pmid" in df_old.columns:
                existing_pmids = set(df_old["pmid"].astype(str).tolist())
            print(f"📂 Existing: {len(df_old)} leads | {len(existing_emails)} known emails")
        except Exception as ex:
            print(f"⚠️  Could not read leads.csv: {ex}")

    # Build PubMed review exclusion string
    exclusion_str = " NOT (" + " OR ".join(PUBMED_EXCLUDE_TYPES) + ")"

    all_new_leads = []
    today = datetime.datetime.now().strftime("%m/%d/%Y")
    years = list(range(end_year, start_year - 1, -1))
    print(f"📅 Searching {len(years)} year(s): {years}\n")

    for year in years:
        # Layer 1: PubMed excludes reviews at search level
        term = f"({query}[Title/Abstract]) AND {year}[dp]{exclusion_str}"
        print(f"🔍 {year}...")

        try:
            h   = Entrez.esearch(db="pubmed", term=term, retmax=RETMAX)
            ids = Entrez.read(h).get("IdList", [])
        except Exception as ex:
            print(f"  ❌ Search error: {ex}")
            continue

        if not ids:
            print(f"  📭 0 results")
            continue

        print(f"  📄 {len(ids)} articles (reviews excluded at search level)")

        try:
            fh       = Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml")
            articles = Entrez.read(fh)
            time.sleep(0.35)  # NCBI rate limit
        except Exception as ex:
            print(f"  ❌ Fetch error: {ex}")
            continue

        found    = 0
        no_email = 0
        review   = 0
        junk     = 0
        dup      = 0

        for art in articles.get("PubmedArticle", []):
            try:
                med  = art["MedlineCitation"]["Article"]
                pmid = str(art["MedlineCitation"]["PMID"])

                if pmid in existing_pmids:
                    dup += 1
                    continue

                title    = str(med.get("ArticleTitle", "")).strip()
                abstract = get_abstract(med)
                if not title:
                    continue

                # Layer 2: XML publication type double-check
                if is_review_by_pubtype(art):
                    review += 1
                    continue

                # Layer 3: Junk subject filter (from sheet)
                if is_junk(title, abstract, junk_subjects):
                    junk += 1
                    continue

                # Email extraction
                email, author_name, affiliation = get_email_and_author(med)
                if not email:
                    no_email += 1
                    continue

                email = email.lower().strip()
                if email in existing_emails:
                    dup += 1
                    continue

                # Category routing using sheet keywords
                category = classify(title, abstract, category_keywords)
                journal  = med.get("Journal", {}).get("Title", "N/A")

                lead = {
                    "category":    category,
                    "area":        category,   # doPost reads "area" to route to correct tab
                    "title":       title,
                    "author":      author_name or "",
                    "email":       email,
                    "journal":     journal,
                    "year":        year,
                    "institution": affiliation or "",
                    "sync_date":   today,
                    "pmid":        pmid,
                    "source":      "PubMed_API",
                }

                all_new_leads.append(lead)
                existing_emails.add(email)
                existing_pmids.add(pmid)
                found += 1

            except Exception as ex:
                print(f"  ⚠️  Parse error: {ex}")
                continue

        print(f"  ✅ {found} leads  |  📧 {no_email} no-email  |  "
              f"📰 {review} review  |  🗑️  {junk} junk  |  🔁 {dup} dup")

    # Save
    print(f"\n📊 Total new leads this run: {len(all_new_leads)}")

    if all_new_leads:
        df_new = pd.DataFrame(all_new_leads)
        if os.path.exists("leads.csv"):
            try:
                df_all = pd.concat([pd.read_csv("leads.csv"), df_new], ignore_index=True)
                df_all.drop_duplicates(subset=["email"], keep="first", inplace=True)
            except Exception:
                df_all = df_new
        else:
            df_all = df_new

        df_all.to_csv("leads.csv", index=False)
        print(f"✅ leads.csv: {len(df_all)} total rows")

        # Push to Google Sheet
        if WEBAPP_URL:
            try:
                resp = requests.post(
                    WEBAPP_URL,
                    json={"action": "addLeads", "data": all_new_leads},
                    timeout=45
                )
                print(f"📤 Sheet sync → HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as ex:
                print(f"⚠️  Sheet sync failed: {ex}")
    else:
        print("🧐 No new leads with emails found this run.")
        print("   Tips: try broader search term | check Keywords tab has correct keywords")

    write_file("year_checkpoint.txt", str(start_year - 1))
    write_file("system_status.txt", "COMPLETED")
    print("\n🏁 Done — status: COMPLETED")

if __name__ == "__main__":
    scrape()
