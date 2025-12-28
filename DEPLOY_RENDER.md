# 🚀 Quick Start: Deploy to Render.com

## Step-by-Step Guide (15 minutes)

### Prerequisites
- GitHub account
- Your code ready

---

## Step 1: Push Code to GitHub (5 min)

1. **Create GitHub repository:**
   - Go to https://github.com/new
   - Name: `zugo-attendance`
   - Make it **Public** (required for free tier)
   - Click "Create repository"

2. **Push your code:**
   ```bash
   # In your project folder
   git init
   git add .
   git commit -m "Ready for deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/zugo-attendance.git
   git push -u origin main
   ```

---

## Step 2: Create Render Account (2 min)

1. Go to https://render.com
2. Click **"Get Started for Free"**
3. Sign up with **GitHub** (easiest)
4. Authorize Render

---

## Step 3: Create Database (3 min)

1. In Render dashboard, click **"New +"**
2. Select **"PostgreSQL"** (or MySQL if available)
3. Settings:
   - **Name:** `zugo-attendance-db`
   - **Database:** `zugo_attendance`
   - **User:** `zugoweb`
   - **Region:** Choose closest
   - **Plan:** Free
4. Click **"Create Database"**
5. **IMPORTANT:** Copy the **Internal Database URL** (you'll need it)

---

## Step 4: Deploy Web Service (5 min)

1. Click **"New +"** → **"Web Service"**
2. **Connect Repository:**
   - Select your GitHub account
   - Choose `zugo-attendance` repository
   - Click **"Connect"**

3. **Configure Service:**
   - **Name:** `zugo-attendance-app`
   - **Region:** Same as database
   - **Branch:** `main`
   - **Root Directory:** (leave empty)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free

4. **Add Environment Variables:**
   Click "Add Environment Variable" for each:
   
   ```
   DB_NAME=zugo_attendance
   DB_USER=zugoweb  
   DB_HOST=<from database connection string>
   DB_PORT=5432
   SESSION_SECRET_KEY=<generate random string>
   HOST=0.0.0.0
   PORT=10000
   DEBUG=False
   HR_EMAIL=zugopvtnetwork@gmail.com
   ```

   **To generate SESSION_SECRET_KEY:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

5. Click **"Create Web Service"**

---

## Step 5: Wait for Deployment (5-10 min)

- Render will automatically:
  - Install dependencies
  - Build your app
  - Start the service
- Watch the logs in real-time
- When you see "Your service is live", you're done!

---

## Step 6: Access Your App

Your app will be available at:
```
https://zugo-attendance-app.onrender.com
```

**Note:** Free tier apps "spin down" after 15 minutes of inactivity. First request may take 30-60 seconds to wake up.

---

## 🔧 Troubleshooting

### Build Fails:
- Check build logs
- Verify `requirements.txt` is correct
- Ensure Python version is compatible

### Database Connection Error:
- Verify database credentials match
- Check DB_HOST and DB_PORT are correct
- Ensure database is running

### App Crashes:
- Check runtime logs
- Verify all environment variables are set
- Test locally first

---

## 📝 Next Steps

1. **Custom Domain** (optional):
   - Go to service settings
   - Add your domain

2. **Upgrade Plan** (for production):
   - Free tier has limitations
   - Starter plan: $7/month (always on, faster)

3. **Set up Monitoring** (optional):
   - Render provides basic monitoring
   - Add external monitoring for production

---

## ✅ Success Checklist

- [ ] Code pushed to GitHub
- [ ] Render account created
- [ ] Database created
- [ ] Web service deployed
- [ ] Environment variables set
- [ ] App is live and accessible
- [ ] Can login and use the app

---

**Congratulations! Your app is now live on the internet! 🎉**

