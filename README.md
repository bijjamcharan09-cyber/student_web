### Student Management System


## 1. Project Title

Student Management System

## 2. Project Overview

Explain in simple technical language:

* What the project does: Manages student data, including registration, analytics, and reporting.
* Its main purpose: To provide a web-based platform for managing student information efficiently.
* Who it is designed for: Administrators, faculty, and students of educational institutions.
* Current development stage/version: v2.
* Main technologies used: python, Flask, MySQL, HTML/CSS/JavaScript.


## 3. Project Architecture

Show the high-level structure, for example:

```text
student_web/
│
├── README.md
│
└── student_system/
    ├── app/
    ├── schema/
    ├── run.py
    ├── requirements.txt
    ├── README.md
    └── ...
```

## 4. Technology Stack

Document the technologies actually used by the project.

For example, where applicable:

* Python
* Flask
* MySQL
* HTML/CSS/JavaScript
* Git

## 5. System Architecture

Give a simple high-level architecture diagram:

```text
User
  ↓
Frontend
  ↓
Flask Application
  ↓
Authentication / Authorization
  ↓
Application Logic
  ↓
MySQL Database
```

## 6. Current V2 Scope

For V2, document the implemented major areas such as:

* Role-Based Access Control
* Student Analytics Dashboard
* Reports
* Admin-controlled user registration


## 7. User Roles

* Admin
* Faculty
* Student

The detailed RBAC documentation:

```text
student_system/README.md
```

## 8. Security Overview

* Authentication
* Backend authorization
* Password hashing
* Session handling
* Admin-only account creation
* Environment variables for secrets
* MySQL access


## 9. Database
```
student_management_db
    semesters
    students
    subjects
    users
    student_subjects
    marks
    attendance
```

## 10. Project Status


```text
Current Version: V2
Status: Testing 
```

## 11. Running the Project


For example:

```text
cd student_system
```
```text
python run.py
```

Detailed installation/setup instructions remain in:

```text
student_system/README.md
```

## 12. Documentation

```text
student_web/README.md
    ↓
Project-level overview

student_web/student_system/README.md
    ↓
Detailed application documentation
```

Relative link from the root README to the detailed README:

```text
[Detailed Student Management System Documentation](./student_system/README.md)
```

## 13. Development Roadmap


Separate:

* Implemented
* In progress
* Planned

Do not invent future features.

---

```markdown