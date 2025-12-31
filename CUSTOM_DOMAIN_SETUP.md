# 🌐 Buy a Custom Domain & Connect to Render

Your current URL: `https://zugo-attendance-k0sc.onrender.com`

Want to change to: `https://zugo-attendance.com` (or your chosen domain)

---

## Step 1: Buy a Domain Name (5 minutes)

### Popular Domain Registrars (Pick One):

| Platform | Price | Best For |
|----------|-------|----------|
| **GoDaddy** | $0.99-$15/year | Easiest, good support |
| **Namecheap** | $5-$10/year | Affordable |
| **Google Domains** | $12/year | Simple, integrates with Google |
| **Bluehost** | $2.95/year | Cheap first year |
| **Domain.com** | $8.99/year | Reliable |

### Recommended: **Namecheap** (Easiest & Affordable)

1. Go to https://namecheap.com
2. Search for your domain (e.g., `zugo-attendance.com`)
3. Choose available domain
4. Add to cart
5. Complete payment (usually $5-10/year)
6. You'll get login credentials

---

## Step 2: Connect Domain to Render

### In Render Dashboard:

1. Go to https://render.com
2. Click your **Web Service** (`zugo-attendance-app`)
3. Go to **Settings** tab (top right)
4. Scroll to **"Custom Domain"** section
5. Click **"Add Custom Domain"**

```
Enter your domain: zugo-attendance.com
```

6. Click **"Add Domain"**

Render will show you DNS records to add:

```
Type: CNAME
Name: www
Value: zugo-attendance-k0sc.onrender.com
```

---

## Step 3: Update DNS Records (In Your Domain Registrar)

### Go to Your Domain Registrar (Namecheap example):

1. Log in to **Namecheap**
2. Go to **"Dashboard"** → Your domain
3. Click **"Manage"**
4. Click **"Advanced DNS"** tab
5. Look for **"Host Records"** section

### Add These Records:

**Record 1 - For www (recommended):**
```
Type:   CNAME
Name:   www
Value:  zugo-attendance-k0sc.onrender.com
TTL:    3600
```
Click **"Save"**

**Record 2 - For root domain (optional but recommended):**
```
Type:   A
Name:   @
Value:  76.76.19.21
TTL:    3600
```
Click **"Save"**

---

## Step 4: Wait for DNS to Propagate (10-48 hours)

DNS changes take time:
- ⏱️ **5 minutes to 1 hour** - Usually works
- ⏱️ **2-48 hours** - Guaranteed (worst case)

### During this time:
- Your old URL still works: `https://zugo-attendance-k0sc.onrender.com`
- Your new URL will gradually start working
- Be patient!

### Check if DNS is ready:
Go to https://mxtoolbox.com/
- Search for your domain
- When it shows your Render IP, DNS is ready

---

## Step 5: Enable HTTPS/SSL Certificate

### In Render:

1. Go back to your Web Service → **Settings**
2. Under **"Custom Domain"**, you should see your domain
3. Render **automatically creates SSL certificate** (free!)
4. It takes a few minutes to generate

Check when it's ready:
- Your domain should show ✅ "SSL enabled"

---

## 🎉 Done! Your Live Website

Now you can access:
```
https://zugo-attendance.com
https://www.zugo-attendance.com
```

Both will work and redirect to your Render app!

---

## 📝 Complete Checklist

- [ ] Buy domain from Namecheap/GoDaddy/Google Domains
- [ ] Log in to domain registrar
- [ ] Go to DNS/Advanced DNS settings
- [ ] Add CNAME record for `www`
- [ ] Add A record for root `@` (optional)
- [ ] Wait 10-60 minutes for DNS to propagate
- [ ] Verify DNS at mxtoolbox.com
- [ ] Check Render for SSL certificate (auto-generated)
- [ ] Test: Visit `https://zugo-attendance.com`
- [ ] Celebrate! 🎉

---

## 💰 Cost Breakdown

| Item | Cost | Frequency |
|------|------|-----------|
| Domain Name | $5-15 | Per year |
| Render (Free) | $0 | Forever |
| SSL Certificate | Free | Included |
| **Total** | **$5-15** | **Per year** |

---

## 🔧 Troubleshooting

### Domain not working after 2 hours?

1. **Clear your browser cache:**
   ```
   Ctrl+Shift+Delete → Clear browsing data
   ```

2. **Check DNS propagation:**
   - Go to https://dnschecker.org/
   - Enter your domain
   - Wait until all servers show green ✅

3. **In Render, check Custom Domain status:**
   - Should show ✅ "Connected"
   - Should show 🔒 "SSL enabled"

4. **Verify DNS records:**
   - Go to mxtoolbox.com
   - Search your domain
   - Confirm CNAME and A records are there

### Still not working?

Check Render logs:
1. Go to **Web Service** → **Logs**
2. Look for errors
3. If you see "domain not resolving", wait more (DNS takes time)

---

## 📚 Complete Example

**You have:**
```
App on Render: zugo-attendance-k0sc.onrender.com
```

**You buy:**
```
Domain: zugo-attendance.com ($8/year from Namecheap)
```

**You add DNS:**
```
CNAME: www → zugo-attendance-k0sc.onrender.com
A:     @   → 76.76.19.21
```

**Result (after DNS propagates):**
```
✅ https://zugo-attendance.com
✅ https://www.zugo-attendance.com
(Both point to your Render app)
```

---

## 🚀 Next Steps

1. **Buy domain** (5 min) - Namecheap is easiest
2. **Add DNS records** (5 min) - In domain registrar
3. **Wait for propagation** (1-48 hours) - Be patient
4. **Test your website** - Visit your new domain
5. **Celebrate!** - Your live website is ready 🎉

**Questions?** Let me know in the next message!
