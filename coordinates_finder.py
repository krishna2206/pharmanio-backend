"""
Interactive Pharmacy Coordinate Finder

This script searches for pharmacy coordinates using OpenStreetMap's Nominatim API
and allows interactive validation before updating the dataset.
"""

import json
import requests
import time
import argparse
from typing import List, Dict, Optional, Tuple

# Global configuration
BASE_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "PharmacoordFinder/1.0 (pharmacy location service)"}
DELAY = 1  # Respect Nominatim's usage policy


def load_dataset(dataset_file: str) -> List[Dict]:
    """Load the pharmacy dataset from JSON file."""
    try:
        with open(dataset_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {dataset_file} not found!")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {dataset_file}")
        return []


def save_dataset(dataset_file: str, data: List[Dict]) -> None:
    """Save the updated dataset to JSON file."""
    try:
        with open(dataset_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Dataset saved to {dataset_file}")
    except Exception as e:
        print(f"❌ Error saving dataset: {e}")


def create_search_queries(pharmacy_name: str, address: str, city: str) -> List[str]:
    """Create multiple search query variations for better results."""
    name = pharmacy_name.strip()
    address = address.strip() if address else ""
    city = city.strip()

    search_queries = [
        f"pharmacie {name}, {address}, Madagascar",
        f"pharmacie {name}, {city}, Madagascar",
    ]

    # Filter out queries with empty address when address is not available
    if not address:
        search_queries = [q for q in search_queries if ", , " not in q]

    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for query in search_queries:
        if query not in seen:
            seen.add(query)
            unique_queries.append(query)

    return unique_queries


def search_coordinates(query: str) -> List[Dict]:
    """Search for coordinates using Nominatim API."""
    params = {
        "q": query,
        "format": "json",
        "limit": 5,
        "countrycodes": "mg",
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
    }

    try:
        response = requests.get(BASE_URL, params=params, headers=HEADERS)
        response.raise_for_status()

        results = response.json()

        # Filter results to pharmacy-related locations
        filtered_results = []
        for result in results:
            # Check if it's likely a pharmacy
            display_name = result.get("display_name", "") or ""
            name = result.get("name", "") or ""
            extratags = result.get("extratags") or {}
            amenity = extratags.get("amenity", "") or ""
            shop = extratags.get("shop", "") or ""

            # Convert to lowercase for comparison
            display_name = display_name.lower()
            name = name.lower()
            amenity = amenity.lower()
            shop = shop.lower()

            if (
                any(
                    keyword in display_name or keyword in name
                    for keyword in ["pharmac", "pharmacy", "drugstore", "apothek"]
                )
                or amenity == "pharmacy"
                or shop == "pharmacy"
            ):
                filtered_results.append(result)

        return (
            filtered_results or results
        )  # Return all if no pharmacy-specific results

    except requests.RequestException as e:
        print(f"❌ Error searching for '{query}': {e}")
        return []


def display_search_results(results: List[Dict], pharmacy_name: str) -> None:
    """Display search results in a formatted way."""
    if not results:
        print("❌ No results found")
        return

    print(f"\n🔍 Found {len(results)} result(s) for '{pharmacy_name}':")
    print("-" * 80)

    for i, result in enumerate(results, 1):
        name = result.get("name", "N/A")
        display_name = result.get("display_name", "N/A")
        lat = result.get("lat", "N/A")
        lon = result.get("lon", "N/A")
        extratags = result.get("extratags") or {}
        amenity = extratags.get("amenity", "N/A")

        print(f"{i}. {name}")
        print(f"   📍 {display_name}")
        print(f"   📌 Coordinates: {lat}, {lon}")
        print(f"   🏷️  Type: {amenity}")
        print()


def get_user_choice(results: List[Dict], pharmacy_name: str) -> Optional[Dict]:
    """Get user's choice for the correct pharmacy location."""
    if not results:
        return None

    while True:
        try:
            print(f"Options for '{pharmacy_name}':")
            print("0. Skip this pharmacy")
            for i in range(len(results)):
                print(f"{i+1}. Select result {i+1}")
            print("s. Skip all remaining pharmacies")

            choice = input("\nEnter your choice: ").strip().lower()

            if choice == "s":
                return "skip_all"
            elif choice == "0":
                return None
            else:
                idx = int(choice) - 1
                if 0 <= idx < len(results):
                    return results[idx]
                else:
                    print("❌ Invalid choice. Please try again.")

        except ValueError:
            print("❌ Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n👋 Operation cancelled by user.")
            return "skip_all"


def process_pharmacy(pharmacy: Dict, city: str) -> Optional[Tuple[float, float]]:
    """Process a single pharmacy to find its coordinates."""
    name = pharmacy.get("name", "")
    address = pharmacy.get("address", "") or ""

    print(f"\n🏥 Processing: {name}")
    if address:
        print(f"📍 Address: {address}")
    print(f"🏙️  City: {city}")

    if "coordinates" in pharmacy and pharmacy["coordinates"]:
        lat = pharmacy["coordinates"].get("lat")
        lon = pharmacy["coordinates"].get("lon")
        if lat and lon:
            print(f"✅ Coordinates already exist: {lat}, {lon}")
            return lat, lon

    queries = create_search_queries(name, address, city)

    all_results = []
    for query in queries:
        print(f"🔍 Searching: {query}")
        results = search_coordinates(query)

        if results:
            # Add unique results only
            for result in results:
                if not any(
                    r.get("lat") == result.get("lat")
                    and r.get("lon") == result.get("lon")
                    for r in all_results
                ):
                    all_results.append(result)

        time.sleep(DELAY)

        if len(all_results) >= 5:
            break

    if not all_results:
        print("❌ No coordinates found for this pharmacy.")
        return None

    # Display results and get user choice
    display_search_results(all_results, name)
    choice = get_user_choice(all_results, name)

    if choice == "skip_all":
        return "skip_all"
    elif choice is None:
        print("⏭️  Skipping this pharmacy.")
        return None
    else:
        lat = float(choice["lat"])
        lon = float(choice["lon"])
        print(f"✅ Selected coordinates: {lat}, {lon}")
        return lat, lon


def run_coordinate_finder(dataset_file: str) -> None:
    """Main execution function for coordinate finding."""
    print("🏥 Pharmacy Coordinate Finder")
    print("=" * 50)

    data = load_dataset(dataset_file)
    if not data:
        return

    total_pharmacies = sum(len(city_data["pharmacies"]) for city_data in data)
    processed = 0
    updated = 0

    print(f"📊 Found {len(data)} cities with {total_pharmacies} total pharmacies")

    for city_data in data:
        city = city_data["city"]
        pharmacies = city_data["pharmacies"]

        print(f"\n🏙️  Processing city: {city} ({len(pharmacies)} pharmacies)")

        for pharmacy in pharmacies:
            processed += 1
            print(f"\n📊 Progress: {processed}/{total_pharmacies}")

            result = process_pharmacy(pharmacy, city)

            if result == "skip_all":
                print("\n👋 Stopping as requested.")
                break
            elif result:
                lat, lon = result
                if "coordinates" not in pharmacy:
                    pharmacy["coordinates"] = {}
                pharmacy["coordinates"]["lat"] = lat
                pharmacy["coordinates"]["lon"] = lon
                updated += 1

            # Save progress periodically
            if processed % 5 == 0:
                save_dataset(dataset_file, data)
                print(f"💾 Progress saved ({updated} pharmacies updated so far)")

        if result == "skip_all":
            break

    save_dataset(dataset_file, data)

    print(f"\n✅ Process completed!")
    print(f"📊 Processed: {processed} pharmacies")
    print(f"🔄 Updated: {updated} pharmacies with coordinates")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Pharmacy Coordinate Finder"
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="dataset.json",
        help="JSON dataset file (default: dataset.json)",
    )

    args = parser.parse_args()
    run_coordinate_finder(args.json_file)


if __name__ == "__main__":
    main()
