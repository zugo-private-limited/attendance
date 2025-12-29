# Environment Variables - Correct Configuration Guide

## What to Use for Your Render Deployment

### ✅ Variables & Their Correct Values

| Variable | Value | Where to Get It | Example |
|----------|-------|-----------------|---------|
| **DB_NAME** | `zugo_attendance` | ✅ Use this exact value | `zugo_attendance` |
| **DB_USER** | `zugoweb` | ✅ Use this exact value | `zugoweb` |
| **DB_HOST** | From Render Database | 🔗 Copy from Render DB dashboard | `dpg-xxx.your-region.postgres.render.com` |
| **DB_PORT** | `5432` | ✅ Use this (PostgreSQL default) | `5432` |
| **SESSION_SECRET_KEY** | Generate random string | 🔑 Run the command below | `jF8x9mK2pL4vQ1wE0rT3yU5iO7aS6dF9...` |
| **HOST** | `0.0.0.0` | ✅ Use this exact value | `0.0.0.0` |
| **PORT** | `$PORT` | ✅ Use this (Render auto-assigns) | `$PORT` |
| **DEBUG** | `False` | ✅ Use this (production) | `False` |
| **HR_EMAIL** | `zugopvtnetwork@gmail.com` | ✅ Your HR email | `zugopvtnetwork@gmail.com` |

---

## Step-by-Step: Getting Actual Values

### 1️⃣ Get DB_HOST from Render

**In Render Dashboard:**
1. Go to your **PostgreSQL Database**
2. Click on **"Database"** page
3. Look for **"External Database URL"** or **"Connection"** section
4. Copy the **hostname** part

**Example URL looks like:**
```
postgresql://zugoweb:PASSWORD@dpg-xxx123abc.your-region.postgres.render.com:5432/zugo_attendance
```

**Extract this part as DB_HOST:**
```
dpg-xxx123abc.your-region.postgres.render.com
```

---

### 2️⃣ Generate SESSION_SECRET_KEY

**Run this command on your computer:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Output example:**
```
jF8x9mK2pL4vQ1wE0rT3yU5iO7aS6dF9gH0j1K2l3M4n5O6p7
```

**Copy this and use it as SESSION_SECRET_KEY value**

---

## Final Environment Variables - Ready to Use

```
DB_NAME=zugo_attendance
DB_USER=zugoweb
DB_HOST=dpg-xxx123abc.your-region.postgres.render.com
DB_PORT=5432
SESSION_SECRET_KEY=jF8x9mK2pL4vQ1wE0rT3yU5iO7aS6dF9gH0j1K2l3M4n5O6p7
HOST=0.0.0.0
PORT=$PORT
DEBUG=False
HR_EMAIL=zugopvtnetwork@gmail.com
```

---

## 🚨 Important Notes

### DO NOT USE:
- ❌ `<from database connection string>` - Replace with actual DB_HOST
- ❌ `<generate random string>` - Generate actual SESSION_SECRET_KEY
- ❌ `10000` for PORT - Use `$PORT` instead (Render assigns this automatically)

### MUST VERIFY:
1. **DB_HOST** is from your actual Render PostgreSQL database
2. **SESSION_SECRET_KEY** is randomly generated (run the command)
3. **DB_USER** matches the user you created in Render database
4. **DB_NAME** matches the database name in Render

---

## Where to Enter in Render

1. Go to your **Web Service** in Render dashboard
2. Click **"Environment"** tab
3. Click **"Add Environment Variable"** for each entry
4. Enter:
   - **Key:** (left side) - e.g., `DB_NAME`
   - **Value:** (right side) - e.g., `zugo_attendance`
5. Click **"Save"**

---

## ✅ Verification Checklist

Before clicking "Deploy":

- [ ] DB_HOST copied from Render PostgreSQL dashboard
- [ ] SESSION_SECRET_KEY is a long random string (run the Python command)
- [ ] DB_USER is `zugoweb` (matches your Render DB user)
- [ ] DB_NAME is `zugo_attendance` (matches your Render database name)
- [ ] PORT is set to `$PORT` (not 10000)
- [ ] DEBUG is `False` (production mode)
- [ ] HR_EMAIL is correct

---

## If Deployment Fails

**Common issues:**

1. **"Cannot connect to database"** → Check DB_HOST is correct
2. **"Authentication failed"** → Check DB_USER and DB_PASSWORD in connection string
3. **"Port error"** → Make sure PORT is `$PORT` (not a fixed number)
4. **"Session error"** → Check SESSION_SECRET_KEY is set and not empty

---

## Summary

| Setting | Status | Value |
|---------|--------|-------|
| DB_NAME | ✅ Fixed | `zugo_attendance` |
| DB_USER | ✅ Fixed | `zugoweb` |
| DB_HOST | 🔗 **Get from Render** | Your actual host |
| DB_PORT | ✅ Fixed | `5432` |
| SESSION_SECRET_KEY | 🔑 **Generate** | Run Python command |
| HOST | ✅ Fixed | `0.0.0.0` |
| PORT | ✅ Fixed | `$PORT` |
| DEBUG | ✅ Fixed | `False` |
| HR_EMAIL | ✅ Fixed | `zugopvtnetwork@gmail.com` |

**You only need to replace 2 values: DB_HOST (from Render) and SESSION_SECRET_KEY (generate)**
