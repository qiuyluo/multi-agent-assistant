import os
import re
import requests
from datetime import datetime
from typing import List

PDF_KNOWLEDGE_BASE_PATH = "/Users/smu_cs_dsi/Documents/multi-agent-assistant/knowledge_base"  # change this to your path

# This cache should be filled after recommendations are made
RECOMMENDATION_CACHE = []  # Each item: {"title": ..., "url": ...}

def list_local_pdfs(base_path: str = PDF_KNOWLEDGE_BASE_PATH) -> dict:
    '''
    Find all PDF files names in the user's local knowledge base directory, including subfolders.

    Returns:
    - dict: A dictionary with relative folder paths as keys, and list of PDFs as values.
    '''
    tree = {}

    try:
        entries = os.listdir(base_path)
    except FileNotFoundError:
        return tree

    for entry in entries:
        
        full_path = os.path.join(base_path, entry)

        if os.path.isdir(full_path):
            tree[entry] = list_local_pdfs(full_path) 
        elif os.path.isfile(full_path) and entry.lower().endswith(".pdf"):
            tree[entry] = None

    print(f"🔍 Found {len(tree)} PDF files in {base_path}")

    return tree


def download_pdf_to_local(url: str, title: str, base_path: str = PDF_KNOWLEDGE_BASE_PATH) -> str:
    '''
    Downloads a PDF file from an arXiv URL using the paper's title as filename.

    Returns:
    - str: Confirmation message with the save path or error message.
    '''
    if "arxiv.org" not in url:
        return "Only arXiv links are supported for now."

    match = re.search(r'arxiv.org/(abs|pdf)/([0-9\.]+)', url)
    if not match:
        return "Invalid arXiv link format."

    arxiv_id = match.group(2)
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    response = requests.get(pdf_url)
    if response.status_code != 200:
        return f"Failed to download PDF from {pdf_url}"

    os.makedirs(base_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{title}_{timestamp}.pdf"
    save_path = os.path.join(base_path, filename)

    with open(save_path, "wb") as f:
        f.write(response.content)

    return f"✅ PDF saved to: {save_path}"


def resolve_user_selection_and_download(user_reply: str) -> List[str]:
    '''
    Parses user reply to identify which papers to download, and saves them using the paper title.

    Returns:
    - List of success/error messages for each download.
    '''
    lowered = user_reply.lower()
    selected_indices = []

    if "all" in lowered or "save all" in lowered:
        selected_indices = list(range(len(RECOMMENDATION_CACHE)))

    matches = re.findall(r"(\d+)", lowered)
    if matches:
        selected_indices += [int(idx) - 1 for idx in matches]

    results = []
    for i in selected_indices:
        if 0 <= i < len(RECOMMENDATION_CACHE):
            paper = RECOMMENDATION_CACHE[i]
            title = paper.get("title", f"paper_{i}")
            url = paper.get("url")
            result = download_pdf_to_local(url, title)
            results.append(result)

    return results