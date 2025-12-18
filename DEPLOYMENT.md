# Deployment Guide

## Pre-Deployment Checklist

Before deploying, ensure:

- [ ] All environment variables are set in `.env` file
- [ ] Database is created and accessible
- [ ] MySQL server is running
- [ ] All dependencies are installed (`pip install -r requirements.txt`)
- [ ] Test script passes (`python test_deployment.py`)
- [ ] Session secret key is changed from default
- [ ] Database credentials are secure

## Quick Start

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your settings:**
   - Database credentials
   - Session secret key
   - Email settings (if needed)

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run tests:**
   ```bash
   python test_deployment.py
   ```

5. **Start the application:**
   ```bash
   python app.py
   ```

## Deployment Options

### Option 1: Heroku

1. **Install Heroku CLI** and login
2. **Create Heroku app:**
   ```bash
   heroku create your-app-name
   ```

3. **Add MySQL addon:**
   ```bash
   heroku addons:create cleardb:ignite
   ```

4. **Set environment variables:**
   ```bash
   heroku config:set SESSION_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
   heroku config:set DB_NAME=your_db_name
   heroku config:set DB_USER=your_db_user
   heroku config:set DB_PASSWORD=your_db_password
   heroku config:set DB_HOST=your_db_host
   heroku config:set DB_PORT=3306
   ```

5. **Deploy:**
   ```bash
   git push heroku main
   ```

### Option 2: Docker

1. **Build image:**
   ```bash
   docker build -t attendance-app .
   ```

2. **Run container:**
   ```bash
   docker run -d \
     --name attendance \
     -p 8000:8000 \
     --env-file .env \
     attendance-app
   ```

### Option 3: Linux Server (systemd)

1. **Create service file** `/etc/systemd/system/attendance.service`:
   ```ini
   [Unit]
   Description=Zugo Attendance Management System
   After=network.target mysql.service

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/var/www/attendance
   Environment="PATH=/var/www/attendance/venv/bin"
   EnvironmentFile=/var/www/attendance/.env
   ExecStart=/var/www/attendance/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

2. **Enable and start:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable attendance
   sudo systemctl start attendance
   sudo systemctl status attendance
   ```

### Option 4: Nginx Reverse Proxy

1. **Install Nginx:**
   ```bash
   sudo apt-get install nginx
   ```

2. **Create Nginx config** `/etc/nginx/sites-available/attendance`:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static {
           alias /var/www/attendance/static;
       }
   }
   ```

3. **Enable site:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

## Environment Variables Reference

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DB_NAME` | MySQL database name | Yes | `attendance_db` |
| `DB_USER` | MySQL username | Yes | `root` |
| `DB_PASSWORD` | MySQL password | Yes | `` |
| `DB_HOST` | MySQL host | Yes | `localhost` |
| `DB_PORT` | MySQL port | Yes | `3306` |
| `SESSION_SECRET_KEY` | Secret key for sessions | Yes | `change_me_in_production` |
| `HOST` | Server host | No | `0.0.0.0` |
| `PORT` | Server port | No | `8000` |
| `DEBUG` | Debug mode | No | `False` |
| `HR_EMAIL` | HR email address | No | `zugopvtnetwork@gmail.com` |
| `HR_PASSWORD` | HR default password | No | `zugo@123` |

## Security Checklist

- [ ] Change `SESSION_SECRET_KEY` to a strong random value
- [ ] Use strong database passwords
- [ ] Enable HTTPS/SSL in production
- [ ] Set `DEBUG=False` in production
- [ ] Restrict database access (firewall rules)
- [ ] Keep dependencies updated
- [ ] Regular database backups
- [ ] Use environment variables, never hardcode secrets

## Troubleshooting

### Application won't start
- Check if port is already in use: `lsof -i :8000`
- Verify environment variables are set
- Check database connection

### Database connection errors
- Verify MySQL is running: `sudo systemctl status mysql`
- Check credentials in `.env`
- Test connection: `mysql -u $DB_USER -p -h $DB_HOST`

### Static files not loading
- Verify `static/` directory exists
- Check file permissions
- Ensure Nginx/webserver is configured correctly

### 500 Internal Server Error
- Check application logs
- Verify database tables exist
- Check environment variables

## Monitoring

### View logs (systemd):
```bash
sudo journalctl -u attendance -f
```

### View logs (Docker):
```bash
docker logs -f attendance
```

### Health check endpoint:
Add to `app.py`:
```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

## Backup

### Database backup:
```bash
mysqldump -u $DB_USER -p $DB_NAME > backup_$(date +%Y%m%d).sql
```

### Restore:
```bash
mysql -u $DB_USER -p $DB_NAME < backup_YYYYMMDD.sql
```

## Updates

1. Pull latest code
2. Install new dependencies: `pip install -r requirements.txt`
3. Run migrations if any
4. Restart service: `sudo systemctl restart attendance`

