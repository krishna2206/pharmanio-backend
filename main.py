from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
import sqlite3
import json
from contextlib import contextmanager
from database import DB_FILE, init_db
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from datetime import datetime, date
from scraper import scrape_pharmacies, process_scraped_pharmacies

app = FastAPI(
    title="PharmAnio API",
    description="API for pharmacy and on-duty pharmacy information",
    version="1.0.0",
)
scheduler = AsyncIOScheduler()


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()


async def check_and_update_on_duty():
    """Check if current on-duty period has expired and update if needed."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT end_date FROM on_duty_pharmacies 
                ORDER BY id DESC LIMIT 1
            """
            )

            result = cursor.fetchone()
            if result:
                end_date = datetime.strptime(result[0], "%Y-%m-%d").date()
                today = date.today()

                if today > end_date:
                    logging.info("On-duty period expired, running scraper...")
                    pharmacies, start_date, end_date = scrape_pharmacies()
                    process_scraped_pharmacies(pharmacies, start_date, end_date)
                    logging.info("Scraper completed successfully")
                else:
                    logging.info(f"On-duty period still valid until {end_date}")
            else:
                logging.info("No on-duty data found, running scraper...")
                pharmacies, start_date, end_date = scrape_pharmacies()
                process_scraped_pharmacies(pharmacies, start_date, end_date)

    except Exception as e:
        logging.error(f"Error in scheduled scraper: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on startup."""
    init_db()

    scheduler.start()

    # Schedule the check to run daily at 6 AM
    scheduler.add_job(
        check_and_update_on_duty,
        CronTrigger(hour=6, minute=0),
        id="check_on_duty_expiry",
        replace_existing=True,
    )

    # Run an initial check
    await check_and_update_on_duty()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler."""
    scheduler.shutdown()


@app.get("/pharmacies", response_model=List[Dict[str, Any]])
async def get_all_pharmacies():
    """Get all pharmacies with their city information."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    p.id,
                    p.name,
                    p.address,
                    p.phone,
                    p.latitude,
                    p.longitude,
                    p.created_at,
                    p.updated_at,
                    c.name as city_name,
                    c.id as city_id
                FROM pharmacies p
                JOIN cities c ON p.city_id = c.id
                ORDER BY c.name, p.name
            """
            )

            pharmacies = []
            for row in cursor.fetchall():
                phone_list = []
                if row["phone"]:
                    phone_list = [
                        phone.strip()
                        for phone in row["phone"].split(",")
                        if phone.strip()
                    ]

                pharmacy = {
                    "id": row["id"],
                    "name": row["name"],
                    "address": row["address"],
                    "phone": phone_list,
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "city": {"id": row["city_id"], "name": row["city_name"]},
                }
                pharmacies.append(pharmacy)

            return pharmacies

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/on-duty", response_model=Dict[str, Any])
async def get_on_duty_pharmacies():
    """Get current on-duty pharmacies with complete details."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT start_date, end_date, pharmacy_ids, created_at, updated_at
                FROM on_duty_pharmacies
                ORDER BY id DESC
                LIMIT 1
            """
            )

            duty_record = cursor.fetchone()

            if not duty_record:
                return {
                    "message": "No on-duty pharmacy data available",
                    "duty_period": None,
                    "pharmacies": [],
                    "total_count": 0,
                }

            try:
                pharmacy_ids = json.loads(duty_record["pharmacy_ids"])
            except (json.JSONDecodeError, TypeError):
                pharmacy_ids = []

            pharmacies = []
            if pharmacy_ids:
                # Get pharmacy details for on-duty pharmacies
                placeholders = ",".join("?" * len(pharmacy_ids))
                cursor.execute(
                    f"""
                    SELECT 
                        p.id,
                        p.name,
                        p.address,
                        p.phone,
                        p.latitude,
                        p.longitude,
                        c.name as city_name,
                        c.id as city_id
                    FROM pharmacies p
                    JOIN cities c ON p.city_id = c.id
                    WHERE p.id IN ({placeholders})
                    ORDER BY c.name, p.name
                """,
                    pharmacy_ids,
                )

                for row in cursor.fetchall():
                    phone_list = []
                    if row["phone"]:
                        phone_list = [
                            phone.strip()
                            for phone in row["phone"].split(",")
                            if phone.strip()
                        ]

                    pharmacy = {
                        "id": row["id"],
                        "name": row["name"],
                        "address": row["address"],
                        "phone": phone_list,
                        "latitude": row["latitude"],
                        "longitude": row["longitude"],
                        "city": {"id": row["city_id"], "name": row["city_name"]},
                    }
                    pharmacies.append(pharmacy)

            return {
                "duty_period": {
                    "start_date": duty_record["start_date"],
                    "end_date": duty_record["end_date"],
                    "created_at": duty_record["created_at"],
                    "updated_at": duty_record["updated_at"],
                },
                "pharmacies": pharmacies,
                "total_count": len(pharmacies),
                "pharmacy_ids": pharmacy_ids,
            }

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/cities", response_model=List[Dict[str, Any]])
async def get_all_cities():
    """Get all cities with pharmacy counts."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    c.id,
                    c.name,
                    c.created_at,
                    COUNT(p.id) as pharmacy_count
                FROM cities c
                LEFT JOIN pharmacies p ON c.id = p.city_id
                GROUP BY c.id, c.name, c.created_at
                ORDER BY c.name
            """
            )

            cities = []
            for row in cursor.fetchall():
                city = {
                    "id": row["id"],
                    "name": row["name"],
                    "created_at": row["created_at"],
                    "pharmacy_count": row["pharmacy_count"],
                }
                cities.append(city)

            return cities

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/pharmacies/city/{city_name}", response_model=List[Dict[str, Any]])
async def get_pharmacies_by_city(city_name: str):
    """Get all pharmacies in a specific city."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    p.id,
                    p.name,
                    p.address,
                    p.phone,
                    p.latitude,
                    p.longitude,
                    p.created_at,
                    p.updated_at,
                    c.name as city_name,
                    c.id as city_id
                FROM pharmacies p
                JOIN cities c ON p.city_id = c.id
                WHERE LOWER(c.name) = LOWER(?)
                ORDER BY p.name
            """,
                (city_name,),
            )

            pharmacies = []
            for row in cursor.fetchall():
                phone_list = []
                if row["phone"]:
                    phone_list = [
                        phone.strip()
                        for phone in row["phone"].split(",")
                        if phone.strip()
                    ]

                pharmacy = {
                    "id": row["id"],
                    "name": row["name"],
                    "address": row["address"],
                    "phone": phone_list,
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "city": {"id": row["city_id"], "name": row["city_name"]},
                }
                pharmacies.append(pharmacy)

            if not pharmacies:
                raise HTTPException(
                    status_code=404, detail=f"No pharmacies found in city: {city_name}"
                )

            return pharmacies

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
