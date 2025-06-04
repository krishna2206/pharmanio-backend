# PharmAnio API 🏥

A FastAPI-based REST API for pharmacy and on-duty pharmacy information in Madagascar. This API provides endpoints to access pharmacy data, on-duty pharmacy schedules, and city information.

## Features

- **Pharmacy Management**: Get all pharmacies with location and contact information
- **On-Duty Tracking**: Track and retrieve current on-duty pharmacies
- **City-based Search**: Find pharmacies by city
- **Location Data**: Pharmacy coordinates for mapping services
- **Auto-scraping**: Automatic updates of on-duty pharmacy information

## API Endpoints

### 📍 Get All Pharmacies
```
GET /pharmacies
```
Returns all pharmacies with their city information, including coordinates and contact details.

### 🚨 Get On-Duty Pharmacies
```
GET /on-duty
```
Returns current on-duty pharmacies with duty period information.

### 🏙️ Get All Cities
```
GET /cities
```
Returns all cities with pharmacy counts.

### 🔍 Get Pharmacies by City
```
GET /pharmacies/city/{city_name}
```
Returns all pharmacies in a specific city.

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/krishna2206/pharmanio-backend.git
   cd pharmanio-backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the database**
   ```bash
   python database.py
   ```

4. **Convert dataset to database (if you have JSON data)**
   ```bash
   python dataset_converter.py dataset.json
   ```

5. **Run the API**
   ```bash
   python main.py
   ```
   Or using uvicorn directly:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:
- **Interactive API docs**: `http://localhost:8000/docs`
- **Alternative docs**: `http://localhost:8000/redoc`

## Database Schema

### Cities Table
- `id`: Primary key
- `name`: City name
- `created_at`: Creation timestamp

### Pharmacies Table
- `id`: Primary key
- `city_id`: Foreign key to cities
- `name`: Pharmacy name
- `address`: Physical address
- `phone`: Contact numbers (comma-separated)
- `latitude`: GPS latitude
- `longitude`: GPS longitude
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### On-Duty Pharmacies Table
- `id`: Primary key
- `start_date`: Duty period start date
- `end_date`: Duty period end date
- `pharmacy_ids`: JSON array of pharmacy IDs
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

## Response Examples

### Pharmacy Object
```json
{
  "id": 1,
  "name": "Pharmacie Centrale",
  "address": "Analakely - Antananarivo",
  "phone": ["034 12 345 67", "020 22 123 45"],
  "latitude": -18.8792,
  "longitude": 47.5079,
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T10:00:00",
  "city": {
    "id": 1,
    "name": "Antananarivo"
  }
}
```

### On-Duty Response
```json
{
  "duty_period": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-07",
    "created_at": "2024-01-01T10:00:00",
    "updated_at": "2024-01-01T10:00:00"
  },
  "pharmacies": [...],
  "total_count": 15,
  "pharmacy_ids": [1, 5, 12, 18, ...]
}
```

## Utilities

### Data Conversion
Convert JSON dataset to SQLite database:
```bash
python dataset_converter.py dataset.json --db-file pharmacies.db
```

### Coordinate Finder
Interactive tool to find and add GPS coordinates to pharmacies:
```bash
python coordinates_finder.py dataset.json
```

### Web Scraper
Update on-duty pharmacy information from external source:
```bash
python scraper.py
```

## Development

### Running in Development Mode
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Adding New Data
1. Add pharmacies to the JSON dataset
2. Run the coordinate finder to get GPS coordinates
3. Convert the updated JSON to database format
4. Restart the API

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request