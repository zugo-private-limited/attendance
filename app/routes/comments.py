"""Employee comments and messaging routes."""
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import JSONResponse

import config
from data import (
    get_db_connection, submit_employee_comment, get_employee_comments, 
    get_unread_comments_for_hr, get_all_comments_for_hr, mark_comment_as_read, 
    get_unread_comment_count, delete_comment
)

router = APIRouter()

@router.post("/api/submit-comment", summary="Submit a comment to HR")
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

@router.get("/api/my-comments", summary="Get my submitted comments")
async def get_my_comments(request: Request, db = Depends(get_db_connection)):
    """Get all comments submitted by the logged-in employee."""
    user_email = request.session.get("user_email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    comments = get_employee_comments(db, user_email)
    return {"comments": comments}

@router.get("/api/hr/unread-comments-count", summary="Get unread comment count for HR")
async def get_unread_count(request: Request, db = Depends(get_db_connection)):
    """Get count of unread comments for HR notification badge."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    count = get_unread_comment_count(db)
    return {"unread_count": count}

@router.get("/api/hr/comments", summary="Get all comments for HR")
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

@router.post("/api/hr/mark-comment-read/{comment_id}", summary="Mark comment as read")
async def mark_read(
    comment_id: int,
    request: Request,
    db = Depends(get_db_connection)
):
    """Mark a comment as read by HR."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    success = mark_comment_as_read(db, comment_id)
    
    if success:
        return {"success": True, "message": "Comment marked as read"}
    else:
        raise HTTPException(status_code=500, detail="Failed to mark comment as read")

@router.delete("/api/hr/delete-comment/{comment_id}", summary="Delete a comment")
async def delete_comment_endpoint(
    comment_id: int,
    request: Request,
    db = Depends(get_db_connection)
):
    """Delete a comment (HR only)."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    success = delete_comment(db, comment_id)
    
    if success:
        return {"success": True, "message": "Comment deleted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete comment")
