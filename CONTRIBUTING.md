# Contributing to WSU ERP System

Thank you for showing interest in contributing!  
This project is part of **WSU CS665 (Enterprise Software Development)**  
and follows clean and collaborative development practices.

---

## 🛠 Development Setup

1. Clone the repository  
```bash
git clone https://github.com/dheeraj2804/wsu_erp_system.git
cd wsu_erp_system
```

2. Create & activate virtual environment  
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies  
```bash
pip install -r requirements.txt
```

4. Run the app  
```bash
python app.py
```

---

## 🚧 Branch Strategy

- `main` → stable, production-ready code  
- `feature/*` → new feature development  
- `fix/*` → bug fixes  

Example:
```
feature/react-ticket-dashboard
fix/loan-due-date-bug
```

---

## 📝 Commit Message Style

Follow the conventional format:

```
feat: add multiple-equipment selection for reservations
fix: overdue fee calculation bug
ui: improve ticket list layout
refactor: move loan logic to service layer
docs: add ERD diagram
```

---

## 🔀 Pull Request Guidelines

Before submitting a PR:

1. Ensure code runs without errors  
2. Test changes manually  
3. Write clear description of what was added/changed  
4. Reference related issues if any  
5. Keep PRs focused — avoid mixing unrelated features  

---

## 🧪 Testing (Manual Only)

Because this is an academic project, testing is manual:

- Create/edit/delete equipment  
- Create reservations as Student  
- Approve reservations as Staff  
- Create & return loans  
- Create/edit service tickets  

---

## 🤝 Code Style

- Follow Python PEP8  
- Use descriptive variable names  
- Keep functions readable (avoid very long functions)  
- Separate UI logic, DB logic, and business logic where possible  

---

Thank you for contributing to this project! 🎉
