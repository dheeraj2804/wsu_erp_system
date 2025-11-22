import os
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash


# ------------------------------------------------------------------------------
# App + DB setup
# ------------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-this"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///wsu_erp.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------

class Role(db.Model):
    __tablename__ = "roles"
    role_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.role_id"), nullable=False)
    status = db.Column(db.String(20), default="active")

    role = db.relationship("Role")

    def get_id(self):
        return str(self.user_id)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        # FIXED: was comparing password to itself earlier
        return check_password_hash(self.password_hash, password)

    @property
    def is_staff(self) -> bool:
        return self.role and self.role.name in ("Tech Staff", "System Admin")


class Equipment(db.Model):
    __tablename__ = "equipment"
    equipment_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    serial_number = db.Column(db.String(100), nullable=False)
    condition = db.Column(db.String(50), nullable=False, default="Good")
    location = db.Column(db.String(100), nullable=False)
    daily_limit = db.Column(db.Integer, nullable=False, default=1)

    reservations_items = db.relationship("ReservationItem", back_populates="equipment")


class Reservation(db.Model):
    __tablename__ = "reservations"
    reservation_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")

    user = db.relationship("User", backref="reservations")
    items = db.relationship("ReservationItem", back_populates="reservation")
    loan = db.relationship("Loan", back_populates="reservation", uselist=False)


class ReservationItem(db.Model):
    __tablename__ = "reservation_items"
    res_item_id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.reservation_id"))
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.equipment_id"))

    reservation = db.relationship("Reservation", back_populates="items")
    equipment = db.relationship("Equipment", back_populates="reservations_items")


class Loan(db.Model):
    __tablename__ = "loans"
    loan_id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(
        db.Integer, db.ForeignKey("reservations.reservation_id"), nullable=False
    )
    checked_out_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_at = db.Column(db.DateTime, nullable=False)
    returned_at = db.Column(db.DateTime, nullable=True)
    overdue_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    reservation = db.relationship("Reservation", back_populates="loan")


class ServiceTicket(db.Model):
    __tablename__ = "service_tickets"
    ticket_id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.equipment_id"), nullable=False
    )
    severity = db.Column(db.String(20), nullable=False)  # Low/Medium/High/Critical
    status = db.Column(db.String(20), nullable=False, default="Open")
    description = db.Column(db.Text, nullable=True)
    opened_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    opened_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    equipment = db.relationship("Equipment")
    opened_by_user = db.relationship(
        "User", foreign_keys=[opened_by], backref="tickets_opened"
    )
    assigned_to_user = db.relationship(
        "User", foreign_keys=[assigned_to], backref="tickets_assigned"
    )
    updates = db.relationship("TicketUpdate", back_populates="ticket")


class TicketUpdate(db.Model):
    __tablename__ = "ticket_updates"
    update_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("service_tickets.ticket_id"), nullable=False
    )
    note = db.Column(db.Text, nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)

    ticket = db.relationship("ServiceTicket", back_populates="updates")
    updated_by_user = db.relationship("User")


# ------------------------------------------------------------------------------
# Login manager
# ------------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------------------------------------------------------------------------
# Context processors
# ------------------------------------------------------------------------------

@app.context_processor
def inject_role_flags():
    return {
        "is_staff": current_user.is_authenticated and current_user.is_staff,
    }


# ------------------------------------------------------------------------------
# Helper: availability check
# ------------------------------------------------------------------------------

def equipment_is_available(equipment_id, start_dt, end_dt):
    """
    Returns True if equipment has NOT exceeded daily_limit during the requested window.
    Overlap check:
        existing.start < requested.end  AND existing.end > requested.start
    Only Pending/Approved reservations block availability.
    """
    eq = Equipment.query.get(equipment_id)
    if not eq:
        return False

    overlap_count = (
        db.session.query(func.count(ReservationItem.res_item_id))
        .join(Reservation, Reservation.reservation_id == ReservationItem.reservation_id)
        .filter(ReservationItem.equipment_id == equipment_id)
        .filter(Reservation.status.in_(["Pending", "Approved"]))
        .filter(Reservation.start_date < end_dt)
        .filter(Reservation.end_date > start_dt)
        .scalar()
    )

    return overlap_count < (eq.daily_limit or 1)


# ------------------------------------------------------------------------------
# Auth routes
# ------------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password")
        role_name = request.form.get("role", "Student")

        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)
            db.session.commit()

        user = User(email=email, full_name=full_name, role_id=role.role_id)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    roles = Role.query.all()
    return render_template("register.html", roles=roles)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ------------------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# ------------------------------------------------------------------------------
# Equipment CRUD
# ------------------------------------------------------------------------------

@app.route("/equipment")
@login_required
def equipment_list():
    equipment = Equipment.query.order_by(Equipment.equipment_id).all()
    return render_template("equipment_list.html", equipment=equipment)


@app.route("/equipment/create", methods=["GET", "POST"])
@login_required
def equipment_create():
    if not current_user.is_staff:
        flash("Only staff may add equipment.", "danger")
        return redirect(url_for("equipment_list"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        category = (request.form.get("category") or "").strip()
        serial_number = (
            request.form.get("serial_number")
            or request.form.get("serial_no")
            or ""
        ).strip()
        condition = (request.form.get("condition") or "Good").strip() or "Good"
        location = (request.form.get("location") or "").strip()

        try:
            daily_limit = int(request.form.get("daily_limit") or 1)
        except ValueError:
            daily_limit = 1

        if not name or not category or not serial_number or not location:
            flash("Name, category, serial number, and location are required.", "danger")
            return redirect(url_for("equipment_create"))

        eq = Equipment(
            name=name,
            category=category,
            serial_number=serial_number,
            condition=condition,
            location=location,
            daily_limit=daily_limit,
        )
        db.session.add(eq)
        db.session.commit()

        flash("Equipment added.", "success")
        return redirect(url_for("equipment_list"))

    return render_template("equipment_form.html", equipment=None)


@app.route("/equipment/<int:equipment_id>/edit", methods=["GET", "POST"])
@login_required
def equipment_edit(equipment_id):
    if not current_user.is_staff:
        flash("Only staff may edit equipment.", "danger")
        return redirect(url_for("equipment_list"))

    eq = Equipment.query.get_or_404(equipment_id)

    if request.method == "POST":
        eq.name = (request.form.get("name") or "").strip()
        eq.category = (request.form.get("category") or "").strip()
        eq.serial_number = (request.form.get("serial_number") or "").strip()
        eq.condition = (request.form.get("condition") or "Good").strip() or "Good"
        eq.location = (request.form.get("location") or "").strip()

        try:
            eq.daily_limit = int(request.form.get("daily_limit") or 1)
        except ValueError:
            eq.daily_limit = 1

        if not eq.name or not eq.category or not eq.serial_number or not eq.location:
            flash("Name, category, serial number, and location are required.", "danger")
            return redirect(url_for("equipment_edit", equipment_id=equipment_id))

        db.session.commit()
        flash("Equipment updated.", "success")
        return redirect(url_for("equipment_list"))

    return render_template("equipment_form.html", equipment=eq)


@app.route("/equipment/<int:equipment_id>/delete", methods=["POST"])
@login_required
def equipment_delete(equipment_id):
    if not current_user.is_staff:
        flash("Only staff may delete equipment.", "danger")
        return redirect(url_for("equipment_list"))

    eq = Equipment.query.get_or_404(equipment_id)
    db.session.delete(eq)
    db.session.commit()

    flash("Equipment deleted.", "info")
    return redirect(url_for("equipment_list"))


# ------------------------------------------------------------------------------
# Reservations
# ------------------------------------------------------------------------------

@app.route("/reservations")
@login_required
def reservations_list():
    is_staff = current_user.is_staff

    if is_staff:
        reservations = Reservation.query.order_by(Reservation.start_date).all()
    else:
        reservations = (
            Reservation.query
            .filter_by(user_id=current_user.user_id)
            .order_by(Reservation.start_date)
            .all()
        )

    reservations_summary = [
        {"reservation_id": r.reservation_id, "status": r.status or "Pending"}
        for r in reservations
    ]

    return render_template(
        "reservations_list.html",
        reservations=reservations,
        reservations_summary=reservations_summary,
        is_staff=is_staff,
    )


@app.route("/reservations/calendar")
@login_required
def reservations_calendar():
    reservations = Reservation.query.order_by(Reservation.start_date).all()

    events = []
    for r in reservations:
        events.append({
            "title": f"#{r.reservation_id} - {r.user.full_name}",
            "start": r.start_date.isoformat(),
            "end": r.end_date.isoformat(),
            "color": (
                "#28a745" if r.status == "Approved"
                else "#ffc107" if r.status == "Pending"
                else "#dc3545"
            )
        })

    return render_template(
        "reservations_calendar.html",
        events=events,
        is_staff=current_user.is_staff,
    )


@app.route("/reservations/create", methods=["GET", "POST"])
@login_required
def reservations_create():
    equipment = Equipment.query.order_by(Equipment.name).all()

    if request.method == "POST":
        equipment_ids = request.form.getlist("equipment_ids")
        if not equipment_ids:
            flash("Please select at least one piece of equipment.", "danger")
            return redirect(url_for("reservations_create"))

        start_str = request.form.get("start_date")
        end_str = request.form.get("end_date")

        if not start_str or not end_str:
            flash("Start and end date are required.", "danger")
            return redirect(url_for("reservations_create"))

        try:
            start_date = datetime.fromisoformat(start_str)
            end_date = datetime.fromisoformat(end_str)
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for("reservations_create"))

        if end_date <= start_date:
            flash("End date must be after start date.", "danger")
            return redirect(url_for("reservations_create"))

        unavailable = []
        valid_ids = []

        for eid_str in equipment_ids:
            if not eid_str.isdigit():
                continue
            eid = int(eid_str)
            valid_ids.append(eid)

            if not equipment_is_available(eid, start_date, end_date):
                eq = Equipment.query.get(eid)
                unavailable.append(eq.name if eq else f"ID {eid}")

        if unavailable:
            flash(
                "Some items are not available for that time window: " + ", ".join(unavailable),
                "danger",
            )
            return redirect(url_for("reservations_create"))

        reservation = Reservation(
            user_id=current_user.user_id,
            start_date=start_date,
            end_date=end_date,
            status="Pending",
        )

        db.session.add(reservation)
        db.session.flush()

        for eid in valid_ids:
            db.session.add(
                ReservationItem(
                    reservation_id=reservation.reservation_id,
                    equipment_id=eid,
                )
            )

        db.session.commit()
        flash("Reservation submitted for approval.", "success")
        return redirect(url_for("reservations_list"))

    return render_template("reservation_form.html", equipment=equipment)


@app.route("/reservations/<int:reservation_id>")
@login_required
def reservation_detail(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)

    if (not current_user.is_staff) and reservation.user_id != current_user.user_id:
        flash("You are not allowed to view this reservation.", "danger")
        return redirect(url_for("reservations_list"))

    return render_template("reservation_detail.html", reservation=reservation)


@app.route("/reservations/<int:reservation_id>/status", methods=["POST"])
@login_required
def reservation_set_status(reservation_id):
    if not current_user.is_staff:
        flash("Only staff may change reservation status.", "danger")
        return redirect(url_for("reservations_list"))

    reservation = Reservation.query.get_or_404(reservation_id)
    new_status = request.form.get("status")

    if new_status not in ("Pending", "Approved", "Denied"):
        flash("Invalid status.", "danger")
        return redirect(url_for("reservations_list"))

    reservation.status = new_status
    db.session.commit()

    flash(f"Reservation {reservation_id} set to {new_status}.", "success")
    return redirect(url_for("reservations_list"))


# ------------------------------------------------------------------------------
# Loans
# ------------------------------------------------------------------------------

@app.route("/loans")
@login_required
def loans_list():
    if not current_user.is_staff:
        flash("Only staff may view loans.", "danger")
        return redirect(url_for("dashboard"))

    loans = Loan.query.join(Reservation).order_by(Loan.loan_id).all()
    return render_template("loans_list.html", loans=loans)


@app.route("/loans/create/<int:reservation_id>", methods=["GET", "POST"])
@login_required
def loans_create(reservation_id):
    if not current_user.is_staff:
        flash("Only staff may create loans.", "danger")
        return redirect(url_for("loans_list"))

    reservation = Reservation.query.get_or_404(reservation_id)

    if request.method == "POST":
        checked_out_str = request.form.get("checked_out_at")
        due_str = request.form.get("due_at")

        if not checked_out_str or not due_str:
            flash("Checked-out and due dates are required.", "danger")
            return redirect(url_for("loans_create", reservation_id=reservation_id))

        try:
            checked_out_at = datetime.fromisoformat(checked_out_str)
            due_at = datetime.fromisoformat(due_str)
        except ValueError:
            flash("Invalid date/time format.", "danger")
            return redirect(url_for("loans_create", reservation_id=reservation_id))

        if due_at <= checked_out_at:
            flash("Due date must be after the checked-out time.", "danger")
            return redirect(url_for("loans_create", reservation_id=reservation_id))

        loan = Loan(
            reservation_id=reservation.reservation_id,
            checked_out_at=checked_out_at,
            due_at=due_at,
            overdue_fee=0,
        )

        reservation.status = "Approved"

        db.session.add(loan)
        db.session.commit()

        flash("Loan created successfully.", "success")
        return redirect(url_for("loans_list"))

    now = datetime.utcnow().replace(microsecond=0)
    default_checked_out = now.isoformat(timespec="minutes")
    default_due = (now + timedelta(days=3)).isoformat(timespec="minutes")

    return render_template(
        "loan_create.html",
        reservation=reservation,
        default_checked_out=default_checked_out,
        default_due=default_due,
    )


@app.route("/loans/return/<int:loan_id>", methods=["POST"])
@login_required
def loans_return(loan_id):
    if not current_user.is_staff:
        flash("Only staff may update loans.", "danger")
        return redirect(url_for("dashboard"))

    loan = Loan.query.get_or_404(loan_id)

    if loan.returned_at is not None:
        flash("This loan is already marked as returned.", "info")
        return redirect(url_for("loans_list"))

    now = datetime.utcnow()
    loan.returned_at = now

    overdue_fee = 0
    if loan.due_at and now > loan.due_at:
        days_late = (now.date() - loan.due_at.date()).days
        if days_late > 0:
            overdue_fee = 10 * days_late

    loan.overdue_fee = overdue_fee
    db.session.commit()

    flash("Loan marked as returned.", "success")
    return redirect(url_for("loans_list"))


# ------------------------------------------------------------------------------
# Tickets
# ------------------------------------------------------------------------------

@app.route("/tickets")
@login_required
def tickets_list():
    if not current_user.is_staff:
        tickets = (
            ServiceTicket.query
            .filter_by(opened_by=current_user.user_id)
            .order_by(ServiceTicket.opened_at.desc())
            .all()
        )
    else:
        tickets = (
            ServiceTicket.query
            .order_by(ServiceTicket.opened_at.desc())
            .all()
        )

    return render_template(
        "tickets_list.html",
        tickets=tickets,
        is_staff=current_user.is_staff,
    )


@app.route("/tickets/create", methods=["GET", "POST"])
@login_required
def tickets_create():
    equipment = Equipment.query.order_by(Equipment.name).all()

    users = []
    if current_user.is_staff:
        users = User.query.order_by(User.full_name).all()

    if request.method == "POST":
        equipment_id = int(request.form.get("equipment_id"))
        severity = request.form.get("severity")
        description = request.form.get("description") or ""

        assigned_to = None
        if current_user.is_staff:
            assigned_raw = request.form.get("assigned_to") or ""
            if assigned_raw.isdigit():
                assigned_to = int(assigned_raw)

        ticket = ServiceTicket(
            equipment_id=equipment_id,
            severity=severity,
            status="Open",
            description=description,
            opened_by=current_user.user_id,
            assigned_to=assigned_to,
        )
        db.session.add(ticket)
        db.session.commit()

        flash("Service ticket created.", "success")
        return redirect(url_for("tickets_list"))

    return render_template(
        "ticket_form.html",
        equipment=equipment,
        users=users,
        is_staff=current_user.is_staff,
    )


@app.route("/tickets/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def ticket_detail(ticket_id):
    ticket = ServiceTicket.query.get_or_404(ticket_id)

    if (not current_user.is_staff) and ticket.opened_by != current_user.user_id:
        flash("You are not allowed to view this ticket.", "danger")
        return redirect(url_for("tickets_list"))

    if request.method == "POST":
        note = (request.form.get("note") or "").strip()
        if note:
            update = TicketUpdate(
                ticket_id=ticket.ticket_id,
                note=note,
                updated_by=current_user.user_id,
            )
            db.session.add(update)
            db.session.commit()
            flash("Update added.", "success")
            return redirect(url_for("ticket_detail", ticket_id=ticket.ticket_id))

    updates = (
        TicketUpdate.query
        .filter_by(ticket_id=ticket.ticket_id)
        .order_by(TicketUpdate.added_at.desc())
        .all()
    )

    users = []
    if current_user.is_staff:
        users = User.query.order_by(User.full_name).all()

    return render_template(
        "ticket_detail.html",
        ticket=ticket,
        updates=updates,
        users=users,
        is_staff=current_user.is_staff,
    )


@app.route("/tickets/<int:ticket_id>/edit", methods=["POST"])
@login_required
def ticket_edit(ticket_id):
    if not current_user.is_staff:
        flash("Only staff may edit tickets.", "danger")
        return redirect(url_for("tickets_list"))

    ticket = ServiceTicket.query.get_or_404(ticket_id)

    status = request.form.get("status") or ticket.status
    assigned_to = request.form.get("assigned_to") or None

    if status in ("Open", "In Progress", "Closed"):
        ticket.status = status

    if assigned_to and str(assigned_to).isdigit():
        ticket.assigned_to = int(assigned_to)
    else:
        ticket.assigned_to = None

    if ticket.status == "Closed" and ticket.closed_at is None:
        ticket.closed_at = datetime.utcnow()

    db.session.commit()

    flash("Ticket updated.", "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket.ticket_id))


# ------------------------------------------------------------------------------
# API: stats for React dashboard
# ------------------------------------------------------------------------------

@app.route("/api/stats/reservations_by_equipment")
@login_required
def stats_reservations_by_equipment():
    rows = (
        db.session.query(Equipment.name, func.count(ReservationItem.res_item_id))
        .join(ReservationItem, ReservationItem.equipment_id == Equipment.equipment_id)
        .group_by(Equipment.equipment_id)
        .all()
    )

    labels = [r[0] for r in rows]
    values = [int(r[1]) for r in rows]

    return jsonify({"labels": labels, "values": values})


# ------------------------------------------------------------------------------
# CLI helper
# ------------------------------------------------------------------------------

@app.cli.command("init-db")
def init_db():
    """Initialize database tables."""
    db.create_all()
    print("Database tables created.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
