"""
Data validators and sanitizers for the Student Management System.
"""

import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from app.utils.exceptions import ValidationError

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^[+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]{6,15}$")
ROLL_REGEX = re.compile(r"^[a-zA-Z0-9_\-\/]{2,30}$")

VALID_GENDERS = {"Male", "Female", "Other"}
VALID_STUDENT_STATUSES = {"Active", "Inactive", "Suspended", "Graduated"}
VALID_EXAM_TYPES = {"Quiz", "Assignment", "Midterm", "Final", "Practical"}
VALID_ATTENDANCE_STATUSES = {"Present", "Absent", "Late", "Excused"}


def parse_date(date_str: Any, field_name: str = "date") -> date:
    """Validate and parse ISO date string (YYYY-MM-DD)."""
    if isinstance(date_str, date) and not isinstance(date_str, datetime):
        return date_str
    if isinstance(date_str, datetime):
        return date_str.date()

    if not isinstance(date_str, str) or not date_str.strip():
        raise ValidationError(f"Field '{field_name}' must be a valid date in YYYY-MM-DD format.")

    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"Field '{field_name}' format must be YYYY-MM-DD.")


def validate_student_payload(data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
    """Validate and sanitize student creation or update payload."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    errors = {}
    cleaned = {}

    # Roll Number
    if "roll_number" in data or not is_update:
        roll = str(data.get("roll_number", "")).strip()
        if not roll:
            errors["roll_number"] = "Roll number is required."
        elif not ROLL_REGEX.match(roll):
            errors["roll_number"] = "Roll number must be 2-30 characters (alphanumeric, hyphens, slashes)."
        else:
            cleaned["roll_number"] = roll

    # First Name
    if "first_name" in data or not is_update:
        first = str(data.get("first_name", "")).strip()
        if not first or len(first) > 50:
            errors["first_name"] = "First name is required and cannot exceed 50 characters."
        else:
            cleaned["first_name"] = first

    # Last Name
    if "last_name" in data or not is_update:
        last = str(data.get("last_name", "")).strip()
        if not last or len(last) > 50:
            errors["last_name"] = "Last name is required and cannot exceed 50 characters."
        else:
            cleaned["last_name"] = last

    # Email
    if "email" in data or not is_update:
        email = str(data.get("email", "")).strip().lower()
        if not email:
            errors["email"] = "Email is required."
        elif len(email) > 100 or not EMAIL_REGEX.match(email):
            errors["email"] = "A valid email address (max 100 characters) is required."
        else:
            cleaned["email"] = email

    # Phone (Optional)
    if "phone" in data:
        phone = data.get("phone")
        if phone is not None and str(phone).strip():
            phone_str = str(phone).strip()
            if not PHONE_REGEX.match(phone_str) or len(phone_str) > 20:
                errors["phone"] = "Invalid phone number format."
            else:
                cleaned["phone"] = phone_str
        else:
            cleaned["phone"] = None
    elif not is_update:
        cleaned["phone"] = None

    # Date of Birth
    if "date_of_birth" in data or not is_update:
        dob_raw = data.get("date_of_birth")
        try:
            dob = parse_date(dob_raw, "date_of_birth")
            today = date.today()
            if dob > today:
                errors["date_of_birth"] = "Date of birth cannot be in the future."
            elif (today - dob).days < 365 * 10:
                errors["date_of_birth"] = "Student must be at least 10 years of age."
            else:
                cleaned["date_of_birth"] = dob.isoformat()
        except ValidationError as e:
            errors["date_of_birth"] = str(e)

    # Gender
    if "gender" in data or not is_update:
        gender = str(data.get("gender", "")).strip().capitalize()
        if gender not in VALID_GENDERS:
            errors["gender"] = f"Gender must be one of {sorted(list(VALID_GENDERS))}."
        else:
            cleaned["gender"] = gender

    # Current Semester ID (Optional)
    if "current_semester_id" in data:
        sem_id = data.get("current_semester_id")
        if sem_id is not None:
            try:
                sem_id = int(sem_id)
                if sem_id <= 0:
                    errors["current_semester_id"] = "Semester ID must be a positive integer."
                else:
                    cleaned["current_semester_id"] = sem_id
            except (ValueError, TypeError):
                errors["current_semester_id"] = "Semester ID must be an integer."
        else:
            cleaned["current_semester_id"] = None
    elif not is_update:
        cleaned["current_semester_id"] = None

    # Enrollment Date
    if "enrollment_date" in data or not is_update:
        enroll_raw = data.get("enrollment_date") or date.today().isoformat()
        try:
            enroll_d = parse_date(enroll_raw, "enrollment_date")
            cleaned["enrollment_date"] = enroll_d.isoformat()
        except ValidationError as e:
            errors["enrollment_date"] = str(e)

    # Status
    if "status" in data:
        status = str(data.get("status", "")).strip().capitalize()
        if status not in VALID_STUDENT_STATUSES:
            errors["status"] = f"Status must be one of {sorted(list(VALID_STUDENT_STATUSES))}."
        else:
            cleaned["status"] = status
    elif not is_update:
        cleaned["status"] = "Active"

    # Address
    if "address" in data:
        addr = data.get("address")
        cleaned["address"] = str(addr).strip() if addr is not None else None
    elif not is_update:
        cleaned["address"] = None

    if errors:
        raise ValidationError("Student payload validation failed.", details=errors)

    return cleaned


def validate_subject_payload(data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
    """Validate and sanitize subject payload."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    errors = {}
    cleaned = {}

    # Subject Code
    if "subject_code" in data or not is_update:
        code = str(data.get("subject_code", "")).strip().upper()
        if not code or len(code) > 20:
            errors["subject_code"] = "Subject code is required (max 20 characters)."
        else:
            cleaned["subject_code"] = code

    # Name
    if "name" in data or not is_update:
        name = str(data.get("name", "")).strip()
        if not name or len(name) > 100:
            errors["name"] = "Subject name is required (max 100 characters)."
        else:
            cleaned["name"] = name

    # Credits
    if "credits" in data or not is_update:
        raw_credits = data.get("credits", 3.0)
        try:
            credits_val = float(raw_credits)
            if credits_val <= 0 or credits_val > 12:
                errors["credits"] = "Credits must be a number between 0.5 and 12.0."
            else:
                cleaned["credits"] = round(credits_val, 1)
        except (ValueError, TypeError):
            errors["credits"] = "Credits must be a valid decimal number."

    # Department
    if "department" in data or not is_update:
        dept = str(data.get("department", "")).strip()
        if not dept or len(dept) > 100:
            errors["department"] = "Department is required (max 100 characters)."
        else:
            cleaned["department"] = dept

    # Semester ID (Optional)
    if "semester_id" in data:
        sem_id = data.get("semester_id")
        if sem_id is not None:
            try:
                sem_id = int(sem_id)
                if sem_id <= 0:
                    errors["semester_id"] = "Semester ID must be a positive integer."
                else:
                    cleaned["semester_id"] = sem_id
            except (ValueError, TypeError):
                errors["semester_id"] = "Semester ID must be an integer."
        else:
            cleaned["semester_id"] = None
    elif not is_update:
        cleaned["semester_id"] = None

    if errors:
        raise ValidationError("Subject payload validation failed.", details=errors)

    return cleaned


def validate_semester_payload(data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
    """Validate and sanitize semester payload."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    errors = {}
    cleaned = {}

    # Name
    if "name" in data or not is_update:
        name = str(data.get("name", "")).strip()
        if not name or len(name) > 50:
            errors["name"] = "Semester name is required (max 50 characters)."
        else:
            cleaned["name"] = name

    # Semester Number
    if "semester_number" in data or not is_update:
        raw_num = data.get("semester_number")
        try:
            num = int(raw_num)
            if num < 1 or num > 12:
                errors["semester_number"] = "Semester number must be an integer between 1 and 12."
            else:
                cleaned["semester_number"] = num
        except (ValueError, TypeError):
            errors["semester_number"] = "Semester number must be an integer."

    # Academic Year
    if "academic_year" in data or not is_update:
        year = str(data.get("academic_year", "")).strip()
        if not year or len(year) > 20:
            errors["academic_year"] = "Academic year is required (e.g., '2025-2026')."
        else:
            cleaned["academic_year"] = year

    # Start Date and End Date
    start_d = None
    end_d = None
    if "start_date" in data or not is_update:
        try:
            start_d = parse_date(data.get("start_date"), "start_date")
            cleaned["start_date"] = start_d.isoformat()
        except ValidationError as e:
            errors["start_date"] = str(e)

    if "end_date" in data or not is_update:
        try:
            end_d = parse_date(data.get("end_date"), "end_date")
            cleaned["end_date"] = end_d.isoformat()
        except ValidationError as e:
            errors["end_date"] = str(e)

    if start_d and end_d and end_d < start_d:
        errors["end_date"] = "End date must be on or after start date."

    # Is Active
    if "is_active" in data:
        cleaned["is_active"] = bool(data.get("is_active"))
    elif not is_update:
        cleaned["is_active"] = False

    if errors:
        raise ValidationError("Semester payload validation failed.", details=errors)

    return cleaned


def validate_mark_payload(data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
    """Validate and sanitize a single marks entry."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    errors = {}
    cleaned = {}

    for id_field in ("student_id", "subject_id", "semester_id"):
        if id_field in data or not is_update:
            try:
                val = int(data.get(id_field))
                if val <= 0:
                    errors[id_field] = f"{id_field} must be a positive integer."
                else:
                    cleaned[id_field] = val
            except (ValueError, TypeError):
                errors[id_field] = f"{id_field} is required and must be an integer."

    # Exam Type
    if "exam_type" in data or not is_update:
        exam = str(data.get("exam_type", "")).strip().capitalize()
        if exam not in VALID_EXAM_TYPES:
            errors["exam_type"] = f"Exam type must be one of {sorted(list(VALID_EXAM_TYPES))}."
        else:
            cleaned["exam_type"] = exam

    # Max Marks
    max_m = None
    if "max_marks" in data or not is_update:
        raw_max = data.get("max_marks", 100.0)
        try:
            max_m = float(raw_max)
            if max_m <= 0:
                errors["max_marks"] = "Maximum marks must be greater than zero."
            else:
                cleaned["max_marks"] = round(max_m, 2)
        except (ValueError, TypeError):
            errors["max_marks"] = "Maximum marks must be a valid number."

    # Marks Obtained
    if "marks_obtained" in data or not is_update:
        raw_obt = data.get("marks_obtained")
        try:
            obt = float(raw_obt)
            if obt < 0:
                errors["marks_obtained"] = "Marks obtained cannot be negative."
            elif max_m is not None and obt > max_m:
                errors["marks_obtained"] = f"Marks obtained ({obt}) cannot exceed maximum marks ({max_m})."
            else:
                cleaned["marks_obtained"] = round(obt, 2)
        except (ValueError, TypeError):
            errors["marks_obtained"] = "Marks obtained must be a valid number."

    # Remarks
    if "remarks" in data:
        remarks = data.get("remarks")
        cleaned["remarks"] = str(remarks).strip()[:255] if remarks is not None else None
    elif not is_update:
        cleaned["remarks"] = None

    if errors:
        raise ValidationError("Marks payload validation failed.", details=errors)

    return cleaned


def validate_attendance_payload(data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
    """Validate and sanitize a single attendance entry."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    errors = {}
    cleaned = {}

    for id_field in ("student_id", "subject_id"):
        if id_field in data or not is_update:
            try:
                val = int(data.get(id_field))
                if val <= 0:
                    errors[id_field] = f"{id_field} must be a positive integer."
                else:
                    cleaned[id_field] = val
            except (ValueError, TypeError):
                errors[id_field] = f"{id_field} is required and must be an integer."

    # Date
    if "date" in data or not is_update:
        try:
            att_date = parse_date(data.get("date"), "date")
            if att_date > date.today():
                errors["date"] = "Attendance cannot be marked for future dates."
            else:
                cleaned["date"] = att_date.isoformat()
        except ValidationError as e:
            errors["date"] = str(e)

    # Status
    if "status" in data or not is_update:
        status = str(data.get("status", "")).strip().capitalize()
        if status not in VALID_ATTENDANCE_STATUSES:
            errors["status"] = f"Status must be one of {sorted(list(VALID_ATTENDANCE_STATUSES))}."
        else:
            cleaned["status"] = status

    # Remarks
    if "remarks" in data:
        remarks = data.get("remarks")
        cleaned["remarks"] = str(remarks).strip()[:255] if remarks is not None else None
    elif not is_update:
        cleaned["remarks"] = None

    if errors:
        raise ValidationError("Attendance payload validation failed.", details=errors)

    return cleaned


def parse_pagination(page: Any, per_page: Any) -> tuple[int, int]:
    """Validate and sanitize pagination parameters."""
    try:
        p = int(page) if page is not None else 1
        if p < 1:
            p = 1
    except (ValueError, TypeError):
        p = 1

    try:
        pp = int(per_page) if per_page is not None else 10
        if pp < 1:
            pp = 10
        elif pp > 100:
            pp = 100
    except (ValueError, TypeError):
        pp = 10

    return p, pp
