# Zugo Attendance Management System

A FastAPI-based attendance management system with location-based check-in/check-out functionality.

## Features

- Employee check-in/check-out with GPS location validation
- HR management dashboard
- Attendance reports and CSV export
- Mobile-responsive design
- Employee profile management
- Working days and leave tracking

## Prerequisites

- Python 3.8+
- MySQL 5.7+ or MariaDB 10.3+
- pip (Python package manager)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd attendance
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv env
   # On Windows:
   env\Scripts\activate
   # On Linux/Mac:
   source env/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file with your database credentials and settings
   ```

5. **Configure database**
   - Create a MySQL database
   - Update `.env` file with your database credentials
   - The application will automatically create tables on first run

6. **Run the application**
   ```bash
   python app.py
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

7. **Access the application**
   - Open your browser and navigate to `http://localhost:8000`
   - Default HR email: Set in `.env` file (HR_EMAIL)
   - Default HR password: Set in `.env` file (HR_PASSWORD) or "zugo@123"

## Environment Variables

See `.env.example` for all available environment variables.

### Required Variables:
- `DB_NAME`: MySQL database name
- `DB_USER`: MySQL username
- `DB_PASSWORD`: MySQL password
- `DB_HOST`: MySQL host (default: localhost)
- `DB_PORT`: MySQL port (default: 3306)
- `SESSION_SECRET_KEY`: Secret key for session management (use a strong random key in production)

## Deployment

### Heroku

1. Install Heroku CLI
2. Login: `heroku login`
3. Create app: `heroku create your-app-name`
4. Set environment variables:
   ```bash
   heroku config:set DB_NAME=your_db_name
   heroku config:set DB_USER=your_db_user
   heroku config:set DB_PASSWORD=your_db_password
   heroku config:set DB_HOST=your_db_host
   heroku config:set DB_PORT=3306
   heroku config:set SESSION_SECRET_KEY=your_secret_key
   ```
5. Deploy: `git push heroku main`

### Docker

1. Build image:
   ```bash
   docker build -t attendance-app .
   ```

2. Run container:
   ```bash
   docker run -p 8000:8000 --env-file .env attendance-app
   ```

### Linux Server (using systemd)

1. Create service file `/etc/systemd/system/attendance.service`:
   ```ini
   [Unit]
   Description=Zugo Attendance Management System
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/attendance
   Environment="PATH=/path/to/venv/bin"
   ExecStart=/path/to/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start:
   ```bash
   sudo systemctl enable attendance
   sudo systemctl start attendance
   ```

## Project Structure

```
attendance/
├── app.py                 # Main FastAPI application
├── config.py              # Configuration settings
├── data.py                # Database functions
├── services.py            # Business logic
├── schema.py              # Database schema initialization
├── employees.py           # Static employee data
├── requirements.txt       # Python dependencies
├── Procfile              # Heroku deployment config
├── .env.example          # Environment variables template
├── static/               # Static files (CSS, JS, images)
│   ├── styles.css
│   ├── report.css
│   ├── dashboard.css
│   └── ...
└── templates/            # HTML templates
    ├── login.html
    ├── report.html
    ├── dashboard.html
    └── ...
```

## Security Notes

- **Change the session secret key** in production
- Use strong database passwords
- Enable HTTPS in production
- Keep dependencies updated
- Use environment variables for sensitive data
- Regularly backup your database

## Troubleshooting

### Database Connection Issues
- Verify MySQL is running
- Check database credentials in `.env`
- Ensure database exists
- Check firewall settings

### Port Already in Use
- Change `PORT` in `.env` or use: `uvicorn app:app --port 8001`

### Static Files Not Loading
- Ensure `static/` directory exists
- Check file permissions

## License

[Your License Here]

## Support

For issues and questions, please contact [your-email@example.com]

