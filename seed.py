# seed.py
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from app import (
    app,
    db,
    Role,
    User,
    Equipment,
    Reservation,
    ReservationItem,
    Loan,
    ServiceTicket,
    TicketUpdate,
)

with app.app_context():
    # Reset database
    db.drop_all()
    db.create_all()

    # ---- Roles ----
    student_role = Role(name="Student")
    tech_role = Role(name="Tech Staff")
    admin_role = Role(name="System Admin")

    db.session.add_all([student_role, tech_role, admin_role])
    db.session.commit()

    # ---- Users (10 students + 2 tech staff + 1 admin) ----
    users = []
    for i in range(1, 11):
        u = User(
            email=f"student{i}@example.com",
            full_name=f"Student {i}",
            password_hash=generate_password_hash("password"),
            role_id=student_role.role_id,
            status="active",
        )
        users.append(u)
        db.session.add(u)

    staff1 = User(
        email="tech1@example.com",
        full_name="Tech Staff 1",
        password_hash=generate_password_hash("password"),
        role_id=tech_role.role_id,
        status="active",
    )
    staff2 = User(
        email="tech2@example.com",
        full_name="Tech Staff 2",
        password_hash=generate_password_hash("password"),
        role_id=tech_role.role_id,
        status="active",
    )
    admin = User(
        email="admin@example.com",
        full_name="System Admin",
        password_hash=generate_password_hash("adminpass"),
        role_id=admin_role.role_id,
        status="active",
    )

    db.session.add_all([staff1, staff2, admin])
    db.session.commit()

    # ---- Equipment (10 items) ----
    equipment_list = []
    for i in range(1, 11):
        e = Equipment(
            name=f"Camera {i}",
            category="Camera" if i <= 5 else "Lens",
            serial_number=f"SN-{1000 + i}",
            condition="Good",
            location="Lab A",
            daily_limit=1,
        )
        equipment_list.append(e)
        db.session.add(e)

    db.session.commit()

    # ---- Reservations + ReservationItems (10 reservations) ----
    now = datetime.now()
    reservations = []
    for i in range(10):
        r = Reservation(
            user_id=users[i % len(users)].user_id,
            start_date=now + timedelta(days=i),
            end_date=now + timedelta(days=i, hours=2),
            status="Approved" if i % 2 == 0 else "Pending",
        )
        db.session.add(r)
        db.session.flush()  # so r.reservation_id is available
        reservations.append(r)

        # At least one equipment per reservation
        eq1 = equipment_list[i % len(equipment_list)]
        db.session.add(
            ReservationItem(
                reservation_id=r.reservation_id,
                equipment_id=eq1.equipment_id,
            )
        )

        # Some reservations get a second item
        if i % 3 == 0:
            eq2 = equipment_list[(i + 3) % len(equipment_list)]
            db.session.add(
                ReservationItem(
                    reservation_id=r.reservation_id,
                    equipment_id=eq2.equipment_id,
                )
            )

    db.session.commit()

    # ---- Loans for first 5 reservations ----
    for i, r in enumerate(reservations[:5]):
        checked_out_at = r.start_date
        due_at = r.start_date + timedelta(days=3)

        if i < 3:
            # Returned on time
            returned_at = due_at - timedelta(hours=1)
            overdue_fee = 0
        else:
            # Returned 2 days late
            returned_at = due_at + timedelta(days=2)
            overdue_days = 2
            overdue_fee = 5 * overdue_days

        loan = Loan(
            reservation_id=r.reservation_id,
            checked_out_at=checked_out_at,
            due_at=due_at,
            returned_at=returned_at,
            overdue_fee=overdue_fee,
        )
        db.session.add(loan)

    db.session.commit()

    # ---- Service Tickets (5 tickets) ----
    severities = ["Low", "Medium", "High", "Critical", "Medium"]
    statuses = ["Open", "In Progress", "Open", "Closed", "Open"]

    tickets = []
    for i in range(5):
        t = ServiceTicket(
            equipment_id=equipment_list[i].equipment_id,
            opened_by=staff1.user_id,
            assigned_to=staff2.user_id if i % 2 == 0 else None,
            severity=severities[i],
            status=statuses[i],
            description=f"Sample issue {i+1} on {equipment_list[i].name}",
            opened_at=now - timedelta(days=i),
            closed_at=(
                now - timedelta(days=i - 1)
                if statuses[i] == "Closed"
                else None
            ),
        )
        db.session.add(t)
        db.session.flush()
        tickets.append(t)

    db.session.commit()

    # ---- Ticket Updates (2 per ticket) ----
    for t in tickets:
        u1 = TicketUpdate(
            ticket_id=t.ticket_id,
            updated_by=staff1.user_id,
            note="Ticket created and logged.",
            added_at=t.opened_at,
        )
        u2 = TicketUpdate(
            ticket_id=t.ticket_id,
            updated_by=staff2.user_id if t.assigned_to else staff1.user_id,
            note="Initial diagnosis performed.",
            added_at=t.opened_at + timedelta(hours=2),
        )
        db.session.add_all([u1, u2])

    db.session.commit()
    print("✅ Database seeded with roles, users, equipment, reservations, loans, tickets, updates.")
