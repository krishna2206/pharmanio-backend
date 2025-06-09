from contextlib import contextmanager
from difflib import SequenceMatcher
import json
import logging
import sqlite3
from typing import List, Optional, Tuple
import requests
from bs4 import BeautifulSoup
import datetime
import re
from database import DB_FILE, init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TARGET_URL = "https://www.opham.com/urgence/pharmacie"
SIMILARITY_THRESHOLD = 0.4  # 60% similarity threshold
REQUEST_TIMEOUT = 10


# City name mapping from scraper to database
CITY_MAPPING = {
    "TANA": "Antananarivo",
    "ANTSIRABE": "Antsirabe", 
    "FIANARANTSOA": "Fianarantsoa",
    "TAMATAVE": "Toamasina",
    "DIEGO": "Antsiranana",
    "TULEAR": "Toliara",
    "MAJUNGA": "Mahajanga"
}

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()


def _map_city_name(scraped_city: str) -> str:
    """Map scraped city name to database city name."""
    return CITY_MAPPING.get(scraped_city.upper(), scraped_city)


def _find_pharmacy_match(pharmacy_name: str, city: str) -> Optional[int]:
    """Find the closest matching pharmacy in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        db_city = _map_city_name(city)
        
        cursor.execute("""
            SELECT p.id, p.name 
            FROM pharmacies p
            JOIN cities c ON p.city_id = c.id
            WHERE c.name = ?
        """, (db_city,))
        
        pharmacies = cursor.fetchall()
        
        if not pharmacies:
            logger.warning(f"No pharmacies found in city: {db_city}")
            return None
        
        # Find the best match using string similarity
        best_match = None
        best_ratio = 0
        
        for pharmacy_id, db_name in pharmacies:
            ratio = SequenceMatcher(None, pharmacy_name.lower(), db_name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = pharmacy_id
        
        # Only return match if similarity is above threshold
        if best_ratio > SIMILARITY_THRESHOLD:
            logger.info(f"Matched '{pharmacy_name}' with database pharmacy (similarity: {best_ratio:.2f})")
            return best_match
        else:
            logger.warning(f"No good match found for '{pharmacy_name}' (best similarity: {best_ratio:.2f})")
            return None


def _update_on_duty_pharmacies(start_date: str, end_date: str, pharmacy_ids: List[int]):
    """Update or insert the on-duty pharmacies record."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM on_duty_pharmacies ORDER BY id LIMIT 1")
        existing_record = cursor.fetchone()
        
        pharmacy_ids_json = json.dumps(pharmacy_ids)
        
        if existing_record:
            cursor.execute("""
                UPDATE on_duty_pharmacies 
                SET start_date = ?, end_date = ?, pharmacy_ids = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (start_date, end_date, pharmacy_ids_json, existing_record[0]))
            logger.info(f"Updated existing on-duty record with {len(pharmacy_ids)} pharmacies")
        else:
            cursor.execute("""
                INSERT INTO on_duty_pharmacies (start_date, end_date, pharmacy_ids)
                VALUES (?, ?, ?)
            """, (start_date, end_date, pharmacy_ids_json))
            logger.info(f"Created new on-duty record with {len(pharmacy_ids)} pharmacies")
        
        conn.commit()


def process_scraped_pharmacies(pharmacies: List[dict], start_date: str, end_date: str):
    """Process scraped pharmacy data and update the database."""
    matched_pharmacy_ids = []
    logger.info("Searching for pharmacy matches in database...")
    
    for pharmacy in pharmacies:
        pharmacy_name = pharmacy["name"]
        city = pharmacy["city"]
        
        if pharmacy_name and city:
            pharmacy_id = _find_pharmacy_match(pharmacy_name, city)
            if pharmacy_id:
                matched_pharmacy_ids.append(pharmacy_id)

    if start_date and end_date:
        logger.info("Updating on-duty pharmacies table...")
        _update_on_duty_pharmacies(start_date, end_date, matched_pharmacy_ids)
        
        logger.info(f"Summary - Total: {len(pharmacies)}, Matched: {len(matched_pharmacy_ids)}, Period: {start_date} to {end_date}")
    else:
        logger.warning("Could not extract valid date range, skipping database update")


def _extract_date_range(title: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract and convert date range from title."""
    date_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+au\s+(\d{2}/\d{2}/\d{4})', title)
    if not date_match:
        return None, None
    
    try:
        start_date_obj = datetime.datetime.strptime(date_match.group(1), '%d/%m/%Y')
        end_date_obj = datetime.datetime.strptime(date_match.group(2), '%d/%m/%Y')
        return start_date_obj.strftime('%Y-%m-%d'), end_date_obj.strftime('%Y-%m-%d')
    except ValueError:
        return None, None


def _parse_pharmacy_row(row) -> Optional[dict]:
    """Parse pharmacy data from a table row."""
    cells = row.find_all('td')
    if len(cells) < 3:
        return None
    
    # Extract pharmacy name
    pharmacy_cell = cells[0]
    name_element = pharmacy_cell.find('b')
    pharmacy_name = name_element.text.strip() if name_element else ""

    # Extract address
    address = cells[1].text.strip()
    
    # Extract contact numbers
    contact_cell = cells[2]
    contact_text = contact_cell.get_text(separator='\n').strip()
    contact_numbers = [num.strip() for num in contact_text.split('\n') if num.strip()]
    
    # Extract city from address
    city = ""
    if " - " in address:
        city = address.split(" - ")[0].strip()
    
    return {
        "name": pharmacy_name,
        "address": address,
        "city": city,
        "contact_numbers": contact_numbers
    }


def scrape_pharmacies():
    """Scrape pharmacy data from the target website."""
    try:
        response = requests.get(TARGET_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
    except requests.RequestException as e:
        logger.error(f"Error fetching data from {TARGET_URL}: {e}")
        return [], None, None
    except Exception as e:
        logger.error(f"Error parsing HTML: {e}")
        return [], None, None
    
    # Extract the title with date range
    title_element = soup.find('h1', class_='text-center')
    title = title_element.text.strip() if title_element else ""
    
    # Extract date range from title and convert to ISO format
    start_date, end_date = _extract_date_range(title)
    
    # Find the pharmacy table
    table = soup.find('table', {'id': 'datatable-buttons'})
    pharmacies = []
    
    if table:
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            
            for row in rows:
                pharmacy_data = _parse_pharmacy_row(row)
                if pharmacy_data:
                    pharmacies.append(pharmacy_data)
    
    return pharmacies, start_date, end_date


if __name__ == "__main__":
    init_db()
    pharmacies, start_date, end_date = scrape_pharmacies()
    process_scraped_pharmacies(pharmacies, start_date, end_date)
