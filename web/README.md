# Validation Failures Review Portal

A web-based portal for reviewing validation failures in the Bill Review System.

## Features

- View all validation failures in a card-based layout
- Search failures by Order ID, Patient Name, or Date
- Filter failures by critical/non-critical status
- View detailed information for each failure
- Real-time data refresh
- Modern, responsive UI using Bootstrap 5

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

1. The main page displays all validation failures in a card layout
2. Use the search box to filter failures by Order ID, Patient Name, or Date
3. Use the status dropdown to filter by critical/non-critical issues
4. Click on any failure card to view detailed information
5. Use the "Refresh Data" button to update the list with the latest failures

## Development

The application is built using:
- Flask (Python web framework)
- Bootstrap 5 (UI framework)
- Vanilla JavaScript (no Node.js required)

## File Structure

```
web/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── templates/
    └── index.html     # Main template file
``` 