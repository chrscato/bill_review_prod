# Bill Review System

A comprehensive web portal for managing and processing medical bill reviews, with dedicated sections for mapping and processing functionalities.

## 🌟 Features

### Mapping Section
- **Unmapped Items Management**
  - Review and map unmapped medical records
  - Three-panel interface for efficient workflow
  - PDF viewer with region highlighting
  - Database search integration
  - File management system

- **OCR Corrections**
  - Review and correct OCR results
  - Edit patient information and service lines
  - PDF comparison view
  - Validation system for data integrity
  - Change tracking and history

### Processing Section
- **Unauthorized Services**
  - Review and process unauthorized medical services
  - Track authorization status

- **Non-Global Bills**
  - Process non-global bill submissions
  - Apply specific billing rules

- **Rate Issues**
  - Review and correct rate-related problems
  - Rate comparison tools

- **OTA Processing**
  - Handle OTA-specific requirements
  - Track processing status

- **Escalations**
  - Manage escalated cases
  - Track resolution progress

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Flask
- PostgreSQL
- Modern web browser

### Installation

1. Clone the repository
```bash
git clone https://github.com/chrscato/bill_review_prod.git
cd bill_review_prod
```

2. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r web/requirements.txt
```

4. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize the database
```bash
flask db upgrade
```

6. Run the application
```bash
flask run
```

## 🏗️ Project Structure

```
bill_review/
├── web/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   ├── templates/
│   │   ├── mapping/
│   │   └── processing/
│   ├── routes/
│   └── utils/
├── tests/
└── docs/
```

## 🔧 Configuration

The application can be configured using environment variables or a `.env` file:

- `FLASK_ENV`: Development/Production environment
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Application secret key
- `PDF_STORAGE_PATH`: Path for PDF storage
- `LOG_LEVEL`: Logging level configuration

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is proprietary and confidential. All rights reserved.

## 👥 Authors

- **Christopher Cato** - *Initial work*

## 🙏 Acknowledgments

- Flask framework and its contributors
- Bootstrap for the UI components
- All contributors to the project