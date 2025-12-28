# Implementation Details & Code Reference

## 📋 Overview

This document provides detailed code implementation for the new HR Management and Employee Communication System.

---

## 1️⃣ DATABASE SCHEMA CHANGES

### File: `schema.py`

#### Added: employee_comments Table

```python
# Lines added to initialize_database_schema()

# 3. Employee Comments/Messages Table (for employee-to-HR communication)
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_comments (
            id SERIAL PRIMARY KEY,
            employee_email VARCHAR(255) NOT NULL,
            comment_text TEXT NOT NULL,
            attendance_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT FALSE,
            read_by_hr_at TIMESTAMP NULL,
            FOREIGN KEY (employee_email) REFERENCES employee_details(email) ON DELETE CASCADE
        )
    """)
    print("Created/verified employee_comments table")
except psycopg2.Error as e:
    if "already exists" not in str(e):
        print(f"Error creating employee_comments table: {e}")

# Create index on employee_comments
try:
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_employee_date 
        ON employee_comments (employee_email, attendance_date)
    """)
    print("Created/verified comments index")
except psycopg2.Error as e:
    if "already exists" not in str(e):
        print(f"Error creating comments index: {e}")
```

**Key Features:**
- Auto-cascade delete when employee is deleted
- Indexed for fast queries
- Timestamp for audit trail
- Read status tracking with timestamp

---

## 2️⃣ DATA LAYER FUNCTIONS

### File: `data.py`

#### Function: submit_employee_comment()

```python
def submit_employee_comment(db, employee_email: str, comment_text: str, attendance_date: date = None) -> bool:
    """
    Submit a comment from employee to HR.
    
    Args:
        db: Database connection
        employee_email: Email of employee submitting comment
        comment_text: The comment text
        attendance_date: Date of the comment (default: today)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if attendance_date is None:
            attendance_date = date.today()
        
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO employee_comments 
               (employee_email, comment_text, attendance_date, is_read)
               VALUES (%s, %s, %s, %s)""",
            (employee_email, comment_text, attendance_date, False)
        )
        db.commit()
        cursor.close()
        return True
    except psycopg2.Error as e:
        print(f"Error submitting comment: {e}")
        return False
```

#### Function: get_employee_comments()

```python
def get_employee_comments(db, employee_email: str, limit: int = 10) -> List[Dict]:
    """Get all comments from a specific employee."""
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """SELECT * FROM employee_comments 
           WHERE employee_email = %s 
           ORDER BY created_at DESC 
           LIMIT %s""",
        (employee_email, limit)
    )
    comments = cursor.fetchall()
    cursor.close()
    return comments
```

#### Function: get_unread_comments_for_hr()

```python
def get_unread_comments_for_hr(db) -> List[Dict]:
    """Get all unread comments for HR (new notifications)."""
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """SELECT * FROM employee_comments 
           WHERE is_read = FALSE 
           ORDER BY created_at DESC"""
    )
    comments = cursor.fetchall()
    cursor.close()
    return comments
```

#### Function: get_all_comments_for_hr()

```python
def get_all_comments_for_hr(db, limit: int = 50, offset: int = 0) -> List[Dict]:
    """Get all comments for HR dashboard."""
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """SELECT c.*, e.name, e.photo 
           FROM employee_comments c
           LEFT JOIN employee_details e ON c.employee_email = e.email
           ORDER BY c.created_at DESC 
           LIMIT %s OFFSET %s""",
        (limit, offset)
    )
    comments = cursor.fetchall()
    cursor.close()
    return comments
```

#### Function: mark_comment_as_read()

```python
def mark_comment_as_read(db, comment_id: int) -> bool:
    """Mark a comment as read by HR."""
    try:
        cursor = db.cursor()
        cursor.execute(
            """UPDATE employee_comments 
               SET is_read = TRUE, read_by_hr_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (comment_id,)
        )
        db.commit()
        cursor.close()
        return True
    except psycopg2.Error as e:
        print(f"Error marking comment as read: {e}")
        return False
```

#### Function: get_unread_comment_count()

```python
def get_unread_comment_count(db) -> int:
    """Get count of unread comments for HR."""
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM employee_comments WHERE is_read = FALSE")
    count = cursor.fetchone()[0]
    cursor.close()
    return count
```

---

## 3️⃣ API ENDPOINTS

### File: `app.py`

#### Endpoint: POST /api/submit-comment

```python
@app.post("/api/submit-comment", summary="Submit a comment to HR")
async def submit_comment(
    request: Request,
    comment_text: str = Form(...),
    db = Depends(get_db_connection)
):
    """Allow employees to submit comments/messages to HR."""
    user_email = request.session.get("user_email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    if user_email == config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR cannot submit comments")
    
    if not comment_text or not comment_text.strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    
    success = submit_employee_comment(db, user_email, comment_text.strip())
    
    if success:
        return {"success": True, "message": "Comment submitted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to submit comment")
```

**Expected Requests:**
```
POST /api/submit-comment HTTP/1.1
Content-Type: application/x-www-form-urlencoded

comment_text=I%20need%20to%20request%20leave
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Comment submitted successfully"
}
```

---

#### Endpoint: GET /api/my-comments

```python
@app.get("/api/my-comments", summary="Get my submitted comments")
async def get_my_comments(request: Request, db = Depends(get_db_connection)):
    """Get all comments submitted by the logged-in employee."""
    user_email = request.session.get("user_email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    comments = get_employee_comments(db, user_email)
    return {"comments": comments}
```

**Expected Response:**
```json
{
  "comments": [
    {
      "id": 1,
      "employee_email": "john@example.com",
      "comment_text": "I need to request leave",
      "attendance_date": "2025-12-26",
      "created_at": "2025-12-26T10:30:00",
      "is_read": true,
      "read_by_hr_at": "2025-12-26T11:00:00"
    }
  ]
}
```

---

#### Endpoint: GET /api/hr/comments

```python
@app.get("/api/hr/comments", summary="Get all comments for HR")
async def get_hr_comments(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db_connection)
):
    """Get all employee comments for HR dashboard."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    comments = get_all_comments_for_hr(db, limit, offset)
    unread_count = get_unread_comment_count(db)
    
    return {
        "comments": comments,
        "unread_count": unread_count,
        "total": len(comments)
    }
```

---

#### Endpoint: POST /api/hr/edit-employee

```python
@app.post("/api/hr/edit-employee", summary="Edit employee details")
async def edit_employee_details(
    email: str = Form(...),
    name: str = Form(None),
    phone: str = Form(None),
    parent_phone: str = Form(None),
    dob: str = Form(None),
    gender: str = Form(None),
    employee_number: str = Form(None),
    aadhar: str = Form(None),
    joining_date: str = Form(None),
    native: str = Form(None),
    address: str = Form(None),
    job_role: str = Form(None),
    request: Request = None,
    db = Depends(get_db_connection)
):
    """Allow HR to edit employee details."""
    user_email = request.session.get("user_email") if request else None
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    # Build dynamic UPDATE query
    update_fields = []
    update_values = []
    
    if name is not None:
        update_fields.append("name = %s")
        update_values.append(name)
    # ... more fields ...
    
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(email)
    
    query = f"UPDATE employee_details SET {', '.join(update_fields)} WHERE email = %s"
    cursor.execute(query, update_values)
    db.commit()
    
    return {"success": True, "message": "Employee details updated"}
```

---

#### Endpoint: POST /api/hr/delete-employee

```python
@app.post("/api/hr/delete-employee", summary="Delete employee")
async def delete_employee_endpoint(
    email: str = Form(...),
    request: Request = None,
    db = Depends(get_db_connection)
):
    """Allow HR to delete an employee."""
    user_email = request.session.get("user_email") if request else None
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    if email == config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="Cannot delete HR account")
    
    cursor = db.cursor()
    cursor.execute("DELETE FROM employee_details WHERE email = %s", (email,))
    db.commit()
    cursor.close()
    
    return {"success": True, "message": "Employee deleted"}
```

---

## 4️⃣ FRONTEND - EMPLOYEE DASHBOARD

### File: `templates/dashboard.html`

#### HTML Structure

```html
<!-- Comment Box Section -->
{% if not is_hr %}
<div class="card" style="margin-top: 20px; background-color: #f8f9fa;">
  <h3 style="color: #221f1e; margin-top: 0;">Send Message to HR</h3>
  <p style="color: #666; font-size: 14px; margin-bottom: 15px;">
    Have any questions or concerns? Leave a message for your HR manager
  </p>
  
  <form id="commentForm" style="margin-bottom: 20px;">
    <textarea 
      id="commentBox" 
      name="comment_text" 
      placeholder="Type your message here..." 
      style="width: 100%; min-height: 120px; padding: 12px; border: 1px solid #ddd; border-radius: 6px;"
      required
    ></textarea>
    <button type="submit" style="margin-top: 10px; padding: 10px 20px; background-color: #3498db; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">
      📤 Send Message
    </button>
  </form>

  <div id="commentStatus" style="display: none; padding: 12px; border-radius: 6px; margin-bottom: 15px; font-weight: bold;"></div>

  <div style="border-top: 1px solid #ddd; padding-top: 15px;">
    <h4 style="color: #221f1e; margin-top: 0;">Your Messages</h4>
    <div id="commentsList" style="max-height: 300px; overflow-y: auto;">
      <p style="color: #999; text-align: center; padding: 20px;">Loading your messages...</p>
    </div>
  </div>
</div>
{% endif %}
```

#### JavaScript: Load Comments

```javascript
function loadComments() {
    fetch('/api/my-comments')
        .then(response => response.json())
        .then(data => {
            if (data.comments && data.comments.length > 0) {
                let html = '';
                data.comments.forEach(comment => {
                    const date = new Date(comment.created_at).toLocaleString();
                    const readStatus = comment.is_read ? '✅ Read by HR' : '⏳ Pending';
                    html += `
                        <div style="padding: 12px; border: 1px solid #e0e0e0; border-radius: 6px; margin-bottom: 10px; background-color: white;">
                            <div style="font-size: 13px; color: #666; margin-bottom: 8px;">
                                <strong>${date}</strong> - ${readStatus}
                            </div>
                            <div style="color: #333; word-wrap: break-word;">
                                ${comment.comment_text}
                            </div>
                        </div>
                    `;
                });
                commentsList.innerHTML = html;
            } else {
                commentsList.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">No messages yet</p>';
            }
        })
        .catch(error => {
            console.error('Error loading comments:', error);
        });
}
```

#### JavaScript: Submit Comment

```javascript
commentForm.addEventListener('submit', function(e) {
    e.preventDefault();

    const text = commentBox.value.trim();
    if (!text) {
        showStatus('Please enter a message', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('comment_text', text);

    fetch('/api/submit-comment', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showStatus('✅ Message sent successfully!', 'success');
            commentBox.value = '';
            setTimeout(() => {
                loadComments();
            }, 500);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showStatus('❌ Error sending message', 'error');
    });
});
```

---

## 5️⃣ FRONTEND - HR MANAGEMENT

### File: `templates/hr_management.html`

#### Message Button in Header

```html
<button class="btn-purple" onclick="toggleCommentsPanel()">
  📧 Messages 
  <span id="commentBadge" style="display: none; background: #e74c3c; color: white; border-radius: 50%; padding: 2px 6px; margin-left: 5px; font-size: 11px;">0</span>
</button>
```

#### Comments Panel HTML

```html
<div id="commentsPanel" style="display: none; padding: 20px; background-color: #f8f9fa; border-radius: 8px; margin-top: 20px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
    <h3 style="color: #221f1e; margin: 0;">📧 Employee Messages</h3>
    <button onclick="document.getElementById('commentsPanel').style.display='none'" style="background: #e74c3c; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer;">✕ Close</button>
  </div>
  <div id="commentsList" style="max-height: 500px; overflow-y: auto;">
    <p style="color: #999; text-align: center; padding: 20px;">Loading messages...</p>
  </div>
</div>
```

#### JavaScript: Toggle Panel

```javascript
function toggleCommentsPanel() {
    const panel = document.getElementById('commentsPanel');
    if (panel.style.display === 'none' || !panel.style.display) {
        panel.style.display = 'block';
        loadHRComments();
    } else {
        panel.style.display = 'none';
    }
}
```

#### JavaScript: Load HR Comments

```javascript
function loadHRComments() {
    fetch('/api/hr/comments')
        .then(res => res.json())
        .then(data => {
            const badge = document.getElementById('commentBadge');
            const list = document.getElementById('commentsList');
            
            // Update badge
            if (data.unread_count > 0) {
                badge.textContent = data.unread_count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }

            // Build comments list
            if (data.comments && data.comments.length > 0) {
                let html = '';
                data.comments.forEach(comment => {
                    const date = new Date(comment.created_at).toLocaleString();
                    const unreadClass = !comment.is_read ? 'background-color: #fff3cd; border-left: 4px solid #ffc107;' : '';
                    
                    html += `
                        <div style="padding: 12px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 10px; ${unreadClass}">
                            <div style="font-weight: bold; color: #221f1e; margin-bottom: 5px;">
                                ${comment.name || comment.employee_email}
                            </div>
                            <div style="font-size: 12px; color: #666; margin-bottom: 8px;">
                                ${date}
                            </div>
                            <div style="color: #333; word-wrap: break-word; margin-bottom: 10px;">
                                ${comment.comment_text}
                            </div>
                            <div style="display: flex; gap: 8px;">
                                ${!comment.is_read ? `<button onclick="markCommentAsRead(${comment.id})" style="background: #27ae60; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 11px;">✓ Mark as Read</button>` : ''}
                                <button onclick="deleteCommentFromPanel(${comment.id})" style="background: #e74c3c; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 11px;">🗑️ Delete</button>
                            </div>
                        </div>
                    `;
                });
                list.innerHTML = html;
            }
        });
}
```

---

## 6️⃣ STYLING

### File: `static/employee.css`

#### Button Styles Added

```css
.btn-blue {
  background: #3498db;
  color: white;
  border: none;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.3s;
}

.btn-blue:hover {
  background: #2980b9;
}

.btn-purple {
  background: #9b59b6;
  color: white;
  border: none;
  padding: 10px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.3s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-purple:hover {
  background: #8e44ad;
}
```

---

## 7️⃣ TESTING CHECKLIST

### Unit Tests for Comments

```python
# Test submit_employee_comment
employee_comment = submit_employee_comment(db, "john@example.com", "Test message")
assert employee_comment == True

# Test get_employee_comments
comments = get_employee_comments(db, "john@example.com")
assert len(comments) > 0

# Test get_unread_comment_count
count = get_unread_comment_count(db)
assert count >= 0

# Test mark_comment_as_read
success = mark_comment_as_read(db, 1)
assert success == True
```

### Integration Tests

```javascript
// Test submit comment via API
const formData = new FormData();
formData.append('comment_text', 'Test message');

fetch('/api/submit-comment', {
    method: 'POST',
    body: formData
})
.then(res => res.json())
.then(data => {
    console.assert(data.success === true, 'Comment submission failed');
});

// Test get comments via API
fetch('/api/my-comments')
    .then(res => res.json())
    .then(data => {
        console.assert(Array.isArray(data.comments), 'Comments not returned');
    });
```

---

## 8️⃣ PERFORMANCE CONSIDERATIONS

### Database Indexes

```sql
-- Index for fast queries by employee
CREATE INDEX idx_comments_employee_date 
ON employee_comments (employee_email, attendance_date);

-- This enables fast lookups like:
SELECT * FROM employee_comments 
WHERE employee_email = 'john@example.com' 
ORDER BY created_at DESC;
```

### Query Optimization

```python
# Bad: N+1 problem
for employee in employees:
    cursor.execute("SELECT * FROM employee_comments WHERE employee_email = %s", (employee['email'],))
    comments = cursor.fetchall()

# Good: Single query with JOIN
cursor.execute("""
    SELECT c.*, e.name, e.photo 
    FROM employee_comments c
    LEFT JOIN employee_details e ON c.employee_email = e.email
    ORDER BY c.created_at DESC
""")
```

---

## 9️⃣ SECURITY CONSIDERATIONS

### Input Validation

```python
# Validate comment text
if not comment_text or not comment_text.strip():
    raise HTTPException(status_code=400, detail="Comment cannot be empty")

# Sanitize input
comment_text = comment_text.strip()[:5000]  # Limit to 5000 chars

# Validate email
if email not in static_users:
    raise HTTPException(status_code=403, detail="Invalid employee")
```

### Access Control

```python
# Only HR can edit employees
if user_email != config.HR_EMAIL:
    raise HTTPException(status_code=403, detail="HR access required")

# HR cannot modify HR account
if email == config.HR_EMAIL:
    raise HTTPException(status_code=403, detail="Cannot delete HR account")
```

---

## 🔟 FUTURE ENHANCEMENTS

### Email Notifications
```python
def send_hr_notification(employee_email: str, comment_text: str):
    # Send email to HR about new comment
    message = f"New message from {employee_email}: {comment_text}"
    # Send via SMTP
```

### Message Categories
```sql
ALTER TABLE employee_comments 
ADD COLUMN category VARCHAR(50) DEFAULT 'General';
-- Categories: Leave Request, Issue Report, Feedback, Other
```

### Message Threading
```sql
CREATE TABLE comment_threads (
    id SERIAL PRIMARY KEY,
    parent_comment_id INT REFERENCES employee_comments(id),
    reply_text TEXT,
    created_at TIMESTAMP
);
```

---

**Implementation Complete!** ✅

