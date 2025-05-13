import os
import re
import requests
import shutil
import difflib
from typing import Dict, List
from datetime import datetime

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
    Downloads a PDF file from an arXiv URL by replacing "abs" with "pdf" in the original link.

    Returns:
    - str: Confirmation message with the save path or error message.
    '''
    if "arxiv.org" not in url:
        return "Only arXiv links are supported for now."

    # Replace "abs" with "pdf" to get the direct PDF link
    pdf_url = url.replace("/abs/", "/pdf/")
    if not pdf_url.endswith(".pdf"):
        pdf_url += ".pdf"

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
    Parses the user reply to identify which papers to download, and saves them using the paper title.

    Returns:
    - List of success/error messages for each download.
    '''
    lowered = user_reply.lower()
    selected_indices = []

    # Handle "save all" command
    if "all" in lowered or "save all" in lowered:
        selected_indices = list(range(len(RECOMMENDATION_CACHE)))

    # Handle index-based input like "save 1st/2nd/3rd paper"
    matches = re.findall(r"(\d+)", lowered)
    if matches:
        selected_indices += [int(idx) - 1 for idx in matches]

    # Handle fuzzy matching by checking if any keyword in the paper title exists in the user reply
    for i, paper in enumerate(RECOMMENDATION_CACHE):
        title = paper.get("title", "").lower()
        title_keywords = re.findall(r'\w+', title)  # extract all words from title
        if any(kw in lowered for kw in title_keywords):
            selected_indices.append(i)

    # Remove duplicates and filter out-of-range indices
    selected_indices = sorted(set(i for i in selected_indices if 0 <= i < len(RECOMMENDATION_CACHE)))

    results = []
    for i in selected_indices:
        paper = RECOMMENDATION_CACHE[i]
        title = paper.get("title", f"paper_{i}")
        url = paper.get("url")
        result = download_pdf_to_local(url, title)
        results.append(result)

    return results

def organize_files_by_mapping(topic_instruction: str) -> List[str]:
    """
    Organizes PDF files into folders based on classification themes and paper titles provided by a language model.

    Input format example (theme could be topic, year, method, etc.):
    Theme A
    "Title 1"
    "Title 2"

    Theme B
    "Title 3"
    ...

    This function will:
    - Recursively scan all PDF files in PDF_KNOWLEDGE_BASE_PATH (including subfolders)
    - Match paper titles to filenames using fuzzy matching
    - Move each PDF into a new folder based on its associated theme
    - Remove any empty folders left behind during reorganization
    """
    print(f"[📃 organize_files_by_mapping] Working...")

    actions = []
    topic_map: Dict[str, List[str]] = {}
    current_topic = None

    # Parse topic → title mapping from instruction
    for line in topic_instruction.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        elif line.startswith('"') and line.endswith('"'):
            if current_topic:
                topic_map.setdefault(current_topic, []).append(line.strip('"'))
        else:
            current_topic = line

    # Recursively find all PDF files
    title_to_fullpath = {}
    for root, _, files in os.walk(PDF_KNOWLEDGE_BASE_PATH):
        for f in files:
            if not f.endswith(".pdf"):
                continue
            full_path = os.path.join(root, f)
            title_key = f.rsplit('_', 1)[0].replace('_', ' ').lower()
            title_to_fullpath[title_key] = full_path

    # Move files into new topic folders
    for topic, titles in topic_map.items():
        folder_path = os.path.join(PDF_KNOWLEDGE_BASE_PATH, topic.replace(" ", "_"))
        os.makedirs(folder_path, exist_ok=True)

        for title in titles:
            candidates = list(title_to_fullpath.keys())
            closest = difflib.get_close_matches(title.lower(), candidates, n=1, cutoff=0.85)
            matched_key = closest[0] if closest else None

            if matched_key:
                src = title_to_fullpath[matched_key]
                dst = os.path.join(folder_path, os.path.basename(src))

                if not os.path.exists(dst):
                    shutil.move(src, dst)
                    actions.append(f"Moved '{os.path.basename(src)}' to '{folder_path}/'")
            else:
                actions.append(f"❗ Warning: Title not found in files: {title}")

    # Optional: remove old empty folders (excluding new topic folders)
    for root, dirs, _ in os.walk(PDF_KNOWLEDGE_BASE_PATH, topdown=False):
        for d in dirs:
            folder = os.path.join(root, d)
            if folder not in [os.path.join(PDF_KNOWLEDGE_BASE_PATH, t.replace(" ", "_")) for t in topic_map.keys()]:
                try:
                    if not os.listdir(folder):
                        os.rmdir(folder)
                        actions.append(f"🧹 Removed empty folder: {folder}")
                except Exception as e:
                    actions.append(f"⚠️ Could not remove folder {folder}: {e}")

    return actions