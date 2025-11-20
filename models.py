# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Role(db.Model):
    __tablename__ = "roles"
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)

    users = db.relationship("User", back_populates="role")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.role_id"), nullable=False)
    status = db.Column(db.String(20), default="active")

    role = db.relationship("Role", back_populates="users")
    reservations = db.relationship("Reservation", back_populates="user")

    # service tickets & updates
    tickets_opened = db.relationship(
        "ServiceTicket",
        foreign_keys="ServiceTicket.opened_by",
        back_populates="opened_by_user",
    )
    tickets_assigned = db.relationship(
        "ServiceTicket",
        foreign_keys="ServiceTicket.assigned_to",
        back_populates="assigned_to_user",
    )
    ticket_updates = db.relationship(
        "TicketUpdate", back_populates="updated_by_user"
    )

    def get_id(self):
        return str(self.user_id)

    @property
    def role_name(self):
        return self.role.role_name if self.role else None


class Equipment(db.Model):
    __tablename__ = "equipment"
    equipment_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80))
    serial_no = db.Column(db.String(100), unique=True)
    condition = db.Column(db.String(20), default="Good")
    location = db.Column(db.String(120))
    daily_limit = db.Column(db.Integer, default=1)

    reservation_items = db.relationship(
        "ReservationItem", back_populates="equipment"
    )
    service_tickets = db.relationship(
        "ServiceTicket", back_populates="equipment"
    )


class Reservation(db.Model):
    __tablename__ = "reservations"
    reservation_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="Pending")

    user = db.relationship("User", back_populates="reservations")
    items = db.relationship("ReservationItem", back_populates="reservation")
    loan = db.relationship("Loan", uselist=False, back_populates="reservation")


class ReservationItem(db.Model):
    __tablename__ = "reservation_items"
    res_item_id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(
        db.Integer, db.ForeignKey("reservations.reservation_id"), nullable=False
    )
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.equipment_id"), nullable=False
    )
    notes = db.Column(db.Text)

    reservation = db.relationship("Reservation", back_populates="items")
    equipment = db.relationship("Equipment", back_populates="reservation_items")


class Loan(db.Model):
    __tablename__ = "loans"
    loan_id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(
        db.Integer,
        db.ForeignKey("reservations.reservation_id"),
        nullable=False,
        unique=True,
    )
    checked_out_at = db.Column(db.DateTime)
    due_at = db.Column(db.DateTime)
    returned_at = db.Column(db.DateTime)
    overdue_fee = db.Column(db.Numeric(10, 2), default=0)

    reservation = db.relationship("Reservation", back_populates="loan")


class ServiceTicket(db.Model):
    __tablename__ = "service_tickets"
    ticket_id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.equipment_id"), nullable=False
    )
    opened_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    severity = db.Column(db.String(20))
    status = db.Column(db.String(20), default="Open")
    description = db.Column(db.Text)
    opened_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    equipment = db.relationship("Equipment", back_populates="service_tickets")
    opened_by_user = db.relationship(
        "User",
        foreign_keys=[opened_by],
        back_populates="tickets_opened",
    )
    assigned_to_user = db.relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="tickets_assigned",
    )
    updates = db.relationship(
        "TicketUpdate",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )


class TicketUpdate(db.Model):
    __tablename__ = "ticket_updates"
    update_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("service_tickets.ticket_id"), nullable=False
    )
    updated_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    note = db.Column(db.Text, nullable=False)
    added_at = db.Column(db.DateTime)

    ticket = db.relationship("ServiceTicket", back_populates="updates")
    updated_by_user = db.relationship(
        "User", back_populates="ticket_updates"
    )
