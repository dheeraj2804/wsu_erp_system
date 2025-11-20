# 📚 WSU ERP System — Equipment Reservation & Maintenance Portal

This repository contains a fully functional **Equipment Reservation & Service Ticket Management System** built using **Python Flask**, **SQLite**, and **React-based UI components**.  
It simulates Wichita State University's internal equipment loan center and provides **role-based access** for Students and Tech Staff.

---

## 🚀 Features

### 👥 User Roles

#### **Student**
- Create new equipment reservations  
- View reservation history  
- Submit service tickets when equipment is damaged  
- Track the status of submitted tickets  

#### **Tech Staff / Admin**
- Approve or deny student reservations  
- Create loans from approved reservations  
- Set due dates and manage returns  
- Auto-calculate overdue fees  
- Manage equipment inventory  
- Assign and manage service tickets  
- Access analytics dashboard (React-powered charts)

---

## 🛠 Tech Stack

### Backend
- Python 3  
- Flask  
- Jinja2 Templates  
- Flask-Login  
- SQLAlchemy ORM  
- SQLite  

### Frontend
- Embedded React components  
- Chart.js analytics  
- Bootstrap 5 styling  

### Others
- Git / GitHub Version Control  
- Database seed script  

---

## 🔧 System Architecture

```
WSU_ERP_System/
│── app.py
│── models.py
│── seed.py
│── requirements.txt
│── static/
│── templates/
│── instance/
└── README.md
```

---

## ✨ Key Functional Modules

### Reservations
- Students choose multiple equipment items  
- Select start & end date  
- Submit for approval  

### Loans
- Staff converts reservations → loans  
- Staff selects custom due date  
- System auto-calculates overdue fees  
- Tracks loan status and returns  

### Service Tickets
- Students create maintenance tickets  
- Staff assigns and manages them  
- Supports status transitions  
- Includes update notes and timeline  

### Dashboard (React)
- Charts: Reservations per equipment  
- Stats: total reservations, equipment usage  
- UI changes based on user role  

---

## 🧪 How to Run Locally

### 1. Clone repository
```bash
git clone https://github.com/dheeraj2804/wsu_erp_system.git
cd wsu_erp_system
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize database
```bash
flask init-db
```

### 5. Seed the database
```bash
python seed.py
```

### 6. Start Flask server
```bash
python app.py
```

The app will run at:  
**http://127.0.0.1:5000**

---

## 🔐 Default Login Accounts

### Student
- Email: `student1@example.com`  
- Password: `123456`

### Tech Staff
- Email: `staff1@example.com`  
- Password: `123456`

---

## 📈 Future Enhancements
- Full React front-end  
- Docker support  
- JWT-based API  
- Role management UI  
- Equipment availability calendar  
- Email alerts and notifications  


---

## 📄 License
This project is for Educational purposes only.
