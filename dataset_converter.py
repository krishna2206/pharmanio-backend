"""
JSON to SQLite Database Converter

This script converts the pharmacy dataset from JSON format to SQLite database.
"""

import json
import sqlite3
import argparse
from database import init_db


def convert_json_to_sqlite(json_file: str = "dataset.json", db_file: str = "pharmacies.db") -> bool:
    """Convert JSON dataset to SQLite database."""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        conn = sqlite3.connect(db_file)
        conn.execute("PRAGMA foreign_keys = ON")

        init_db()
        cursor = conn.cursor()

        total_pharmacies = 0
        inserted_pharmacies = 0

        print(f"🔄 Converting {json_file} to {db_file}...")

        for city_data in data:
            city_name = city_data.get("city", "").strip()
            if not city_name:
                continue

            cursor.execute(
                "INSERT OR IGNORE INTO cities (name) VALUES (?)", (city_name,)
            )
            cursor.execute("SELECT id FROM cities WHERE name = ?", (city_name,))
            city_id = cursor.fetchone()[0]

            pharmacies = city_data.get("pharmacies", [])
            total_pharmacies += len(pharmacies)

            print(f"  📍 Processing {city_name}: {len(pharmacies)} pharmacies")

            for pharmacy in pharmacies:
                name = pharmacy.get("name", "").strip()
                if not name:
                    continue

                address = pharmacy.get("address", "") or None

                phone_data = pharmacy.get("phone", "") or None
                if isinstance(phone_data, list):
                    phone = ", ".join(str(p) for p in phone_data if p) or None
                elif phone_data:
                    phone = str(phone_data)
                else:
                    phone = None

                coordinates = pharmacy.get("coordinates", {})
                latitude = coordinates.get("lat") if coordinates else None
                longitude = coordinates.get("lon") if coordinates else None

                if latitude is not None:
                    try:
                        latitude = float(latitude)
                    except (ValueError, TypeError):
                        latitude = None

                if longitude is not None:
                    try:
                        longitude = float(longitude)
                    except (ValueError, TypeError):
                        longitude = None

                cursor.execute(
                    """
                    INSERT INTO pharmacies 
                    (city_id, name, address, phone, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (city_id, name, address, phone, latitude, longitude),
                )

                inserted_pharmacies += 1

        conn.commit()
        conn.close()

        print(f"✅ Conversion completed!")
        print(f"📊 Total pharmacies processed: {total_pharmacies}")
        print(f"💾 Pharmacies inserted: {inserted_pharmacies}")
        print(f"🗄️  Database saved as: {db_file}")

        return True

    except FileNotFoundError:
        print(f"❌ Error: {json_file} not found!")
        return False
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON in {json_file}")
        return False
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main entry point for the converter."""
    parser = argparse.ArgumentParser(
        description="Convert JSON dataset to SQLite database"
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="dataset.json",
        help="JSON dataset file (default: dataset.json)",
    )
    parser.add_argument(
        "--db-file",
        default="pharmacies.db",
        help="SQLite database file (default: pharmacies.db)",
    )

    args = parser.parse_args()
    convert_json_to_sqlite(args.json_file, args.db_file)


if __name__ == "__main__":
    main()