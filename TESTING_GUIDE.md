# Quick Testing Guide - Zugo Attendance System Fixes

## 🚀 Getting Started

### 1. Start the Application
```bash
cd c:\Users\Hey! Zugo\project\Attendance\attendance
python app.py
```

Open browser: `http://localhost:8000`

---

## 👤 Login Credentials

### HR Account
- **Email:** `zugopvtnetwork@gmail.com`
- **Password:** `zugo@123`
- **Role:** HR Manager
- **Features:** Can add/edit/delete employees, add manual attendance

### Employee Account
- **Email:** `sugunazugopvt@gmail.com`
- **Password:** `zugo@123`
- **Role:** AI & ML Developer
- **Features:** Can check in/out, view attendance

---

## ✅ Test Cases

### Test 1: Login Access Control
**Goal:** Verify only authorized employees can login

1. Try to login with unauthorized email (e.g., `test@gmail.com`)
   - **Expected:** Error message "Access Denied: Not an authorized employee"
   
2. Try to signup with unauthorized email
   - **Expected:** Error message "Email not authorized. Contact HR."

3. Login with `zugopvtnetwork@gmail.com`
   - **Expected:** Redirects to HR Management page

4. Login with `sugunazugopvt@gmail.com`
   - **Expected:** Redirects to Report/Attendance page

---

### Test 2: Add New Employee (HR Only)
**Goal:** Verify HR can add new employees

1. Login as HR (`zugopvtnetwork@gmail.com`)
2. Click "Management" in sidebar
3. Click "Add New Employee" button
4. Fill in the form:
   - **Full Name:** John Doe
   - **Email:** john.doe@example.com
   - **Password:** john@123
   - **Phone:** 9876543210
   - **Employee ID:** ZPL002
   - **Role:** Developer
   - **DOB:** 1995-05-15
5. Click "Save Employee"
   - **Expected:** Success message "Employee saved"
   - Employee appears in the table

---

### Test 3: Edit Employee (HR Only)
**Goal:** Verify HR can edit existing employees

1. Login as HR
2. Go to Management page
3. Find an employee and click the ✏️ (edit) button
4. Modify employee details
5. Click "Save Employee"
   - **Expected:** Success message
   - Changes are visible in the table

---

### Test 4: Delete Employee (HR Only)
**Goal:** Verify HR can delete employees

1. Login as HR
2. Go to Management page
3. Find an employee and click the 🗑️ (delete) button
4. Confirm deletion in popup
   - **Expected:** Employee removed from table
   - Success message appears

---

### Test 5: Manual Attendance (HR Only)
**Goal:** Verify HR can add manual attendance records

1. Login as HR
2. Go to Management page
3. Click "Manual Attendance" button
4. Fill in the form:
   - **Select Employee:** Choose any employee from dropdown
   - **Date:** 2024-12-23 (or any past date)
   - **Time:** 09:00 (9:00 AM)
   - **Action:** Check In
5. Click "Add Attendance"
   - **Expected:** Success message "Attendance record added successfully"

---

### Test 6: Mobile Notification Display
**Goal:** Verify notifications display properly on mobile

1. Open app on mobile device or use browser DevTools (F12)
2. Toggle mobile view (375px width for iPhone)
3. Trigger a notification by:
   - Attempting invalid login (shows error)
   - Successfully adding/editing/deleting employee (shows success)
4. Look at top-right corner for notification bell 🔔
5. Click bell icon
   - **Expected:** 
     - Dropdown appears within screen bounds
     - Notification text is readable
     - Colors are clear (green for success, red for error)
     - Doesn't go off-screen

---

### Test 7: Mobile Responsiveness
**Goal:** Verify UI works on small screens

1. Open app with mobile view (DevTools)
2. Check that:
   - Sidebar has hamburger menu ☰
   - Clicking hamburger toggles sidebar
   - Buttons are properly sized
   - Tables are scrollable
   - Modals fit on screen
   - Form inputs are readable

---

## 🧪 Mobile Testing Steps

### Using Chrome DevTools:
1. Open browser: F12 or Ctrl+Shift+I
2. Click device icon (toggle device toolbar)
3. Select "iPhone 12" or custom 375x667
4. Test all features in mobile view

### Using Real Mobile:
1. Find your computer's IP: `ipconfig` in PowerShell
2. Access app: `http://<YOUR_IP>:8000`
3. Test all features on actual device

---

## 📝 Feature Verification

### ✅ Features Working
- [x] Login access control (only authorized emails)
- [x] HR can add new employees
- [x] HR can edit existing employees
- [x] HR can delete employees
- [x] HR can add manual attendance
- [x] Mobile notifications display properly
- [x] Modals are responsive
- [x] Error/success messages show correctly
- [x] Buttons have proper access control

### 🎯 What Should NOT Work
- Regular employees cannot see "Add New Employee" button
- Regular employees cannot see "Manual Attendance" button
- Unauthorized emails cannot login or signup
- Non-HR users cannot access `/hr-management`

---

## 🐛 Troubleshooting

### If "Add New Employee" button doesn't appear:
- Make sure you're logged in as HR email (`zugopvtnetwork@gmail.com`)
- Check that `is_hr` variable is True in template

### If modals don't open:
- Check browser console (F12 > Console) for JavaScript errors
- Make sure modal divs have `id="employeeModal"` and `id="attendanceModal"`

### If notifications don't display on mobile:
- Clear browser cache
- Check that `position: fixed` is used in notification dropdown
- Verify media queries are applied

### If database errors appear:
- Make sure PostgreSQL is running
- Check `.env` file has correct database credentials
- Run `python app.py` to initialize schema

---

## 📊 Test Results Template

```
Test Case: [Name]
Date: [Date]
Device: [Desktop/Mobile/Tablet]
Browser: [Chrome/Safari/Firefox]

Expected Result: [What should happen]
Actual Result: [What actually happened]
Status: [✅ PASS / ❌ FAIL]

Notes: [Any additional observations]
```

---

## 🎉 Success Indicators

When all tests pass, you should see:
- ✅ Only authorized employees can login
- ✅ HR has full employee management capabilities
- ✅ Manual attendance can be added
- ✅ Notifications display properly on all devices
- ✅ No console errors in DevTools
- ✅ All success/error messages appear

---

**Ready to test! Good luck! 🚀**
