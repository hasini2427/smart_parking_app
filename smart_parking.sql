-- =====================================================================
-- SMART PARKING LOT ALLOCATION AND BILLING SYSTEM
-- Complete database script
--   A.1 Tables (DDL)                       A.5 Sample data
--   A.2 Indexes                            A.6 Views
--   A.3 Business-rule function/triggers    A.7 Report queries
--   A.4 Stored procedures (transactions)
-- Syntax: MySQL 8.0.16 or later (CHECK constraints are enforced from
-- 8.0.16). Run with the mysql command-line client so that the
-- DELIMITER statements are honoured.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS smart_parking;
USE smart_parking;

-- =====================================================================
-- A.1 TABLES
-- =====================================================================

CREATE TABLE FACILITY (
    facility_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    address         VARCHAR(200) NOT NULL,
    total_floors    INT NOT NULL,
    CONSTRAINT chk_facility_floors CHECK (total_floors > 0)
);

CREATE TABLE FLOOR (
    floor_id        INT AUTO_INCREMENT PRIMARY KEY,
    facility_id     INT NOT NULL,
    floor_no        INT NOT NULL,
    CONSTRAINT fk_floor_facility FOREIGN KEY (facility_id)
        REFERENCES FACILITY (facility_id),
    CONSTRAINT uq_floor UNIQUE (facility_id, floor_no)
);

CREATE TABLE ZONE (
    zone_id         INT AUTO_INCREMENT PRIMARY KEY,
    floor_id        INT NOT NULL,
    zone_name       VARCHAR(50) NOT NULL,
    CONSTRAINT fk_zone_floor FOREIGN KEY (floor_id)
        REFERENCES FLOOR (floor_id),
    CONSTRAINT uq_zone UNIQUE (floor_id, zone_name)
);

CREATE TABLE VEHICLE_TYPE (
    vehicle_type_id INT AUTO_INCREMENT PRIMARY KEY,
    type_name       VARCHAR(30) NOT NULL,
    CONSTRAINT uq_vehicle_type UNIQUE (type_name)
);

CREATE TABLE SLOT (
    slot_id         INT AUTO_INCREMENT PRIMARY KEY,
    zone_id         INT NOT NULL,
    vehicle_type_id INT NOT NULL,
    slot_no         VARCHAR(10) NOT NULL,
    status          VARCHAR(10) NOT NULL DEFAULT 'FREE',
    CONSTRAINT fk_slot_zone FOREIGN KEY (zone_id)
        REFERENCES ZONE (zone_id),
    CONSTRAINT fk_slot_vtype FOREIGN KEY (vehicle_type_id)
        REFERENCES VEHICLE_TYPE (vehicle_type_id),
    CONSTRAINT uq_slot UNIQUE (zone_id, slot_no),
    CONSTRAINT chk_slot_status
        CHECK (status IN ('FREE', 'OCCUPIED', 'RESERVED', 'BLOCKED'))
);

CREATE TABLE CUSTOMER (
    customer_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    phone           VARCHAR(15) NOT NULL,
    email           VARCHAR(100),
    CONSTRAINT uq_customer_phone UNIQUE (phone),
    CONSTRAINT uq_customer_email UNIQUE (email)
);

CREATE TABLE VEHICLE (
    vehicle_id      INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL,
    vehicle_type_id INT NOT NULL,
    reg_no          VARCHAR(20) NOT NULL,
    CONSTRAINT fk_vehicle_customer FOREIGN KEY (customer_id)
        REFERENCES CUSTOMER (customer_id),
    CONSTRAINT fk_vehicle_vtype FOREIGN KEY (vehicle_type_id)
        REFERENCES VEHICLE_TYPE (vehicle_type_id),
    CONSTRAINT uq_vehicle_reg UNIQUE (reg_no)
);

-- customer_id records the customer who made the booking; it need not be
-- the registered owner of the vehicle. active_res_slot_id holds slot_id
-- while the reservation is ACTIVE, so its UNIQUE constraint allows only one
-- active reservation per slot, even when two bookings arrive together.
CREATE TABLE RESERVATION (
    reservation_id  INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL,
    slot_id         INT NOT NULL,
    vehicle_id      INT NOT NULL,
    start_time      DATETIME NOT NULL,
    expiry_time     DATETIME NOT NULL,
    status          VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_res_customer FOREIGN KEY (customer_id)
        REFERENCES CUSTOMER (customer_id),
    CONSTRAINT fk_res_slot FOREIGN KEY (slot_id)
        REFERENCES SLOT (slot_id),
    CONSTRAINT fk_res_vehicle FOREIGN KEY (vehicle_id)
        REFERENCES VEHICLE (vehicle_id),
    active_res_slot_id INT GENERATED ALWAYS AS
                        (CASE WHEN status = 'ACTIVE' THEN slot_id END) STORED,
    CONSTRAINT chk_res_time CHECK (expiry_time > start_time),
    CONSTRAINT chk_res_status
        CHECK (status IN ('ACTIVE', 'EXPIRED', 'CANCELLED', 'FULFILLED')),
    CONSTRAINT uq_active_reservation_slot UNIQUE (active_res_slot_id)
);

-- active_slot_id holds slot_id while the session is open (exit_time IS
-- NULL) and NULL once it is closed. The UNIQUE constraint on it allows
-- only one open session per slot: one active vehicle per slot.
-- active_vehicle_id works the same way for the vehicle, so a vehicle
-- cannot be parked in two slots at the same time.
CREATE TABLE PARKING_SESSION (
    session_id      INT AUTO_INCREMENT PRIMARY KEY,
    slot_id         INT NOT NULL,
    vehicle_id      INT NOT NULL,
    reservation_id  INT NULL,
    entry_time      DATETIME NOT NULL,
    exit_time       DATETIME NULL,
    active_slot_id  INT GENERATED ALWAYS AS
                        (CASE WHEN exit_time IS NULL THEN slot_id END) STORED,
    active_vehicle_id INT GENERATED ALWAYS AS
                        (CASE WHEN exit_time IS NULL THEN vehicle_id END) STORED,
    CONSTRAINT fk_sess_slot FOREIGN KEY (slot_id)
        REFERENCES SLOT (slot_id),
    CONSTRAINT fk_sess_vehicle FOREIGN KEY (vehicle_id)
        REFERENCES VEHICLE (vehicle_id),
    CONSTRAINT fk_sess_res FOREIGN KEY (reservation_id)
        REFERENCES RESERVATION (reservation_id),
    CONSTRAINT uq_sess_reservation UNIQUE (reservation_id),
    CONSTRAINT uq_active_slot UNIQUE (active_slot_id),
    CONSTRAINT uq_active_vehicle UNIQUE (active_vehicle_id),
    CONSTRAINT chk_sess_time
        CHECK (exit_time IS NULL OR exit_time > entry_time)
);

-- customer_id records the pass holder; it need not be the registered
-- owner of the vehicle.
CREATE TABLE PASS (
    pass_id         INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL,
    vehicle_id      INT NOT NULL,
    valid_from      DATE NOT NULL,
    valid_to        DATE NOT NULL,
    CONSTRAINT fk_pass_customer FOREIGN KEY (customer_id)
        REFERENCES CUSTOMER (customer_id),
    CONSTRAINT fk_pass_vehicle FOREIGN KEY (vehicle_id)
        REFERENCES VEHICLE (vehicle_id),
    CONSTRAINT chk_pass_dates CHECK (valid_to > valid_from)
);

-- One rate per vehicle type per effective date; the tariff in force for
-- a session is the latest one effective on or before the entry date.
CREATE TABLE TARIFF (
    tariff_id       INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_type_id INT NOT NULL,
    rate_per_hour   DECIMAL(8,2) NOT NULL,
    effective_from  DATE NOT NULL,
    CONSTRAINT fk_tariff_vtype FOREIGN KEY (vehicle_type_id)
        REFERENCES VEHICLE_TYPE (vehicle_type_id),
    CONSTRAINT uq_tariff UNIQUE (vehicle_type_id, effective_from),
    CONSTRAINT chk_tariff_rate CHECK (rate_per_hour > 0)
);

CREATE TABLE BILL (
    bill_id         INT AUTO_INCREMENT PRIMARY KEY,
    session_id      INT NOT NULL,
    tariff_id       INT NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    generated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bill_session FOREIGN KEY (session_id)
        REFERENCES PARKING_SESSION (session_id),
    CONSTRAINT fk_bill_tariff FOREIGN KEY (tariff_id)
        REFERENCES TARIFF (tariff_id),
    CONSTRAINT uq_bill_session UNIQUE (session_id),
    CONSTRAINT chk_bill_amount CHECK (amount >= 0)
);

CREATE TABLE PAYMENT (
    payment_id      INT AUTO_INCREMENT PRIMARY KEY,
    bill_id         INT NOT NULL,
    amount_paid     DECIMAL(10,2) NOT NULL,
    mode            VARCHAR(20) NOT NULL,
    paid_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payment_bill FOREIGN KEY (bill_id)
        REFERENCES BILL (bill_id),
    CONSTRAINT chk_payment_amount CHECK (amount_paid > 0),
    CONSTRAINT chk_payment_mode
        CHECK (mode IN ('CASH', 'CARD', 'UPI', 'WALLET'))
);

-- =====================================================================
-- A.2 INDEXES ON FREQUENTLY SEARCHED ATTRIBUTES
-- (PRIMARY KEY and UNIQUE constraints above are indexed automatically,
--  e.g. VEHICLE.reg_no and CUSTOMER.phone.)
-- =====================================================================
CREATE INDEX idx_slot_status_type   ON SLOT (status, vehicle_type_id);
CREATE INDEX idx_session_entry_time ON PARKING_SESSION (entry_time);
CREATE INDEX idx_res_status_expiry  ON RESERVATION (status, expiry_time);
CREATE INDEX idx_pass_vehicle_dates ON PASS (vehicle_id, valid_from, valid_to);
CREATE INDEX idx_payment_paid_at    ON PAYMENT (paid_at);

-- =====================================================================
-- A.3 BUSINESS-RULE FUNCTION AND TRIGGERS
-- =====================================================================
DELIMITER //

-- Slot/vehicle-type match: TRUE when the slot accepts the vehicle's type.
CREATE FUNCTION fn_slot_matches_vehicle(p_slot_id INT, p_vehicle_id INT)
RETURNS BOOLEAN
READS SQL DATA
BEGIN
    DECLARE v_count INT;
    SELECT COUNT(*) INTO v_count
    FROM SLOT s
    JOIN VEHICLE v ON v.vehicle_type_id = s.vehicle_type_id
    WHERE s.slot_id = p_slot_id AND v.vehicle_id = p_vehicle_id;
    RETURN v_count = 1;
END //

-- RESERVATION: type match and slot must be free when the booking is made.
CREATE TRIGGER trg_reservation_bi BEFORE INSERT ON RESERVATION
FOR EACH ROW
BEGIN
    IF NOT fn_slot_matches_vehicle(NEW.slot_id, NEW.vehicle_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slot type does not match vehicle type';
    END IF;
    IF (SELECT status FROM SLOT WHERE slot_id = NEW.slot_id) <> 'FREE' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slot is not available for reservation';
    END IF;
END //

CREATE TRIGGER trg_reservation_bu BEFORE UPDATE ON RESERVATION
FOR EACH ROW
BEGIN
    IF (NEW.slot_id <> OLD.slot_id OR NEW.vehicle_id <> OLD.vehicle_id)
       AND NOT fn_slot_matches_vehicle(NEW.slot_id, NEW.vehicle_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slot type does not match vehicle type';
    END IF;
END //

-- A new reservation holds the slot.
CREATE TRIGGER trg_reservation_ai AFTER INSERT ON RESERVATION
FOR EACH ROW
BEGIN
    UPDATE SLOT SET status = 'RESERVED' WHERE slot_id = NEW.slot_id;
END //

-- An expired or cancelled reservation releases the slot.
CREATE TRIGGER trg_reservation_au AFTER UPDATE ON RESERVATION
FOR EACH ROW
BEGIN
    IF OLD.status = 'ACTIVE' AND NEW.status IN ('EXPIRED', 'CANCELLED') THEN
        UPDATE SLOT SET status = 'FREE'
        WHERE slot_id = NEW.slot_id AND status = 'RESERVED';
    END IF;
END //

-- PARKING_SESSION: type match; a reserved entry must use an active,
-- unexpired reservation for the same slot and vehicle; a walk-in entry
-- needs a free slot.
CREATE TRIGGER trg_session_bi BEFORE INSERT ON PARKING_SESSION
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(10);
    DECLARE v_expiry DATETIME;
    DECLARE v_slot INT;
    DECLARE v_vehicle INT;

    IF NOT fn_slot_matches_vehicle(NEW.slot_id, NEW.vehicle_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slot type does not match vehicle type';
    END IF;

    IF NEW.reservation_id IS NOT NULL THEN
        SELECT status, expiry_time, slot_id, vehicle_id
          INTO v_status, v_expiry, v_slot, v_vehicle
        FROM RESERVATION WHERE reservation_id = NEW.reservation_id;
        IF v_status <> 'ACTIVE' OR NEW.entry_time > v_expiry THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Reservation is not active or has expired';
        END IF;
        IF v_slot <> NEW.slot_id OR v_vehicle <> NEW.vehicle_id THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Entry does not match the reservation';
        END IF;
    ELSEIF (SELECT status FROM SLOT WHERE slot_id = NEW.slot_id) <> 'FREE' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slot is not free';
    END IF;
END //

CREATE TRIGGER trg_session_bu BEFORE UPDATE ON PARKING_SESSION
FOR EACH ROW
BEGIN
    IF (NEW.slot_id <> OLD.slot_id OR NEW.vehicle_id <> OLD.vehicle_id)
       AND NOT fn_slot_matches_vehicle(NEW.slot_id, NEW.vehicle_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Slot type does not match vehicle type';
    END IF;
END //

-- Entry occupies the slot and fulfils the reservation, if any.
CREATE TRIGGER trg_session_ai AFTER INSERT ON PARKING_SESSION
FOR EACH ROW
BEGIN
    UPDATE SLOT SET status = 'OCCUPIED' WHERE slot_id = NEW.slot_id;
    IF NEW.reservation_id IS NOT NULL THEN
        UPDATE RESERVATION SET status = 'FULFILLED'
        WHERE reservation_id = NEW.reservation_id;
    END IF;
END //

-- Exit frees the slot.
CREATE TRIGGER trg_session_au AFTER UPDATE ON PARKING_SESSION
FOR EACH ROW
BEGIN
    IF OLD.exit_time IS NULL AND NEW.exit_time IS NOT NULL THEN
        UPDATE SLOT SET status = 'FREE' WHERE slot_id = NEW.slot_id;
    END IF;
END //

-- PAYMENT: total paid can never exceed the bill amount. The bill row is
-- locked first, so two payments for the same bill are checked one after
-- the other.
CREATE TRIGGER trg_payment_bi BEFORE INSERT ON PAYMENT
FOR EACH ROW
BEGIN
    DECLARE v_amount DECIMAL(10,2);
    DECLARE v_paid   DECIMAL(10,2);
    SELECT amount INTO v_amount FROM BILL
    WHERE bill_id = NEW.bill_id FOR UPDATE;
    SELECT COALESCE(SUM(amount_paid), 0) INTO v_paid FROM PAYMENT
    WHERE bill_id = NEW.bill_id;
    IF v_paid + NEW.amount_paid > v_amount THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Payment exceeds the outstanding balance';
    END IF;
END //

-- =====================================================================
-- A.4 STORED PROCEDURES (each runs as one transaction)
-- =====================================================================

-- Gate entry: uses the reserved slot, or allocates the first free slot
-- that matches the vehicle's type.
CREATE PROCEDURE sp_vehicle_entry(
    IN  p_vehicle_id     INT,
    IN  p_reservation_id INT,
    IN  p_entry_time     DATETIME,
    OUT p_session_id     INT)
BEGIN
    DECLARE v_slot INT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    IF p_reservation_id IS NOT NULL THEN
        SELECT slot_id INTO v_slot
        FROM RESERVATION
        WHERE reservation_id = p_reservation_id
        FOR UPDATE;
    ELSE
        SELECT s.slot_id INTO v_slot
        FROM SLOT s
        JOIN VEHICLE v ON v.vehicle_type_id = s.vehicle_type_id
        WHERE v.vehicle_id = p_vehicle_id AND s.status = 'FREE'
        ORDER BY s.slot_id
        LIMIT 1
        FOR UPDATE;
    END IF;

    IF v_slot IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'No free compatible slot available';
    END IF;

    INSERT INTO PARKING_SESSION (slot_id, vehicle_id, reservation_id, entry_time)
    VALUES (v_slot, p_vehicle_id, p_reservation_id, p_entry_time);
    SET p_session_id = LAST_INSERT_ID();
    COMMIT;
END //

-- Gate exit and tariff-based billing:
-- amount = hourly rate x parked minutes / 60, rounded to 2 decimals.
CREATE PROCEDURE sp_close_session(
    IN p_session_id INT,
    IN p_exit_time  DATETIME)
BEGIN
    DECLARE v_entry  DATETIME DEFAULT NULL;
    DECLARE v_type   INT DEFAULT NULL;
    DECLARE v_tariff INT DEFAULT NULL;
    DECLARE v_rate   DECIMAL(8,2) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    SELECT ps.entry_time, v.vehicle_type_id INTO v_entry, v_type
    FROM PARKING_SESSION ps
    JOIN VEHICLE v ON v.vehicle_id = ps.vehicle_id
    WHERE ps.session_id = p_session_id AND ps.exit_time IS NULL
    FOR UPDATE;

    IF v_entry IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Session not found or already closed';
    END IF;

    SELECT tariff_id, rate_per_hour INTO v_tariff, v_rate
    FROM TARIFF
    WHERE vehicle_type_id = v_type AND effective_from <= DATE(v_entry)
    ORDER BY effective_from DESC
    LIMIT 1;

    IF v_tariff IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'No tariff defined for this vehicle type';
    END IF;

    -- chk_sess_time rejects an exit time that is not after the entry time
    UPDATE PARKING_SESSION SET exit_time = p_exit_time
    WHERE session_id = p_session_id;

    INSERT INTO BILL (session_id, tariff_id, amount, generated_at)
    VALUES (p_session_id, v_tariff,
            ROUND(v_rate * TIMESTAMPDIFF(MINUTE, v_entry, p_exit_time) / 60, 2),
            p_exit_time);
    COMMIT;
END //

-- Reservation expiry: marks overdue active reservations as EXPIRED
-- (trg_reservation_au then releases their slots).
CREATE PROCEDURE sp_expire_reservations()
BEGIN
    UPDATE RESERVATION
    SET status = 'EXPIRED'
    WHERE status = 'ACTIVE' AND expiry_time < NOW();
END //

DELIMITER ;

-- Optional: run the expiry procedure automatically (requires the MySQL
-- Event Scheduler to be ON).
-- CREATE EVENT ev_expire_reservations
--     ON SCHEDULE EVERY 5 MINUTE
--     DO CALL sp_expire_reservations();

-- =====================================================================
-- A.5 SAMPLE DATA (demonstration data only)
-- =====================================================================
INSERT INTO FACILITY (name, address, total_floors) VALUES
('Demo Multi-Level Parking', 'Demonstration address', 3);

INSERT INTO FLOOR (facility_id, floor_no) VALUES (1, 0), (1, 1), (1, 2);

INSERT INTO ZONE (floor_id, zone_name) VALUES (1, 'A'), (2, 'B'), (3, 'C');

INSERT INTO VEHICLE_TYPE (type_name) VALUES
('TWO_WHEELER'), ('CAR'), ('SUV');

INSERT INTO SLOT (zone_id, vehicle_type_id, slot_no) VALUES
(1, 2, 'A-01'), (1, 2, 'A-02'), (1, 1, 'A-03'),
(2, 2, 'B-01'), (2, 3, 'B-02'), (3, 1, 'C-01');

INSERT INTO CUSTOMER (name, phone, email) VALUES
('Ananya Rao',   '9000000001', 'ananya.rao@example.com'),
('Rahul Mehta',  '9000000002', 'rahul.mehta@example.com'),
('Priya Sharma', '9000000003', 'priya.sharma@example.com'),
('Arjun Reddy',  '9000000004', 'arjun.reddy@example.com');

INSERT INTO VEHICLE (customer_id, vehicle_type_id, reg_no) VALUES
(1, 2, 'TS09AB1234'),
(2, 1, 'TS07CD5678'),
(3, 3, 'TS10EF9012'),
(4, 2, 'TS08GH3456');

INSERT INTO TARIFF (vehicle_type_id, rate_per_hour, effective_from) VALUES
(1, 10.00, '2026-01-01'),
(2, 20.00, '2026-01-01'),
(3, 30.00, '2026-01-01');

INSERT INTO PASS (customer_id, vehicle_id, valid_from, valid_to) VALUES
(2, 2, '2026-10-01', '2026-10-31');

-- Reserved entry: vehicle 1 reserves slot A-01, arrives within the window.
INSERT INTO RESERVATION (customer_id, slot_id, vehicle_id, start_time, expiry_time)
VALUES (1, 1, 1, '2026-10-01 09:00:00', '2026-10-01 09:30:00');
CALL sp_vehicle_entry(1, 1, '2026-10-01 09:10:00', @s1);
CALL sp_close_session(@s1, '2026-10-01 12:40:00');

-- Walk-in entries (slot allocated automatically).
CALL sp_vehicle_entry(2, NULL, '2026-10-01 10:05:00', @s2);
CALL sp_close_session(@s2, '2026-10-01 11:35:00');
CALL sp_vehicle_entry(3, NULL, '2026-10-01 18:20:00', @s3);
CALL sp_close_session(@s3, '2026-10-01 20:50:00');

-- A reservation that is never used (expires later).
INSERT INTO RESERVATION (customer_id, slot_id, vehicle_id, start_time, expiry_time)
VALUES (4, 4, 4, '2026-10-02 18:00:00', '2026-10-02 18:30:00');

CALL sp_vehicle_entry(2, NULL, '2026-10-02 09:30:00', @s4);
CALL sp_close_session(@s4, '2026-10-02 10:00:00');

-- An open session (vehicle still parked): entered 45 minutes before the
-- script is run, so the dashboard shows a live parked vehicle.
CALL sp_vehicle_entry(1, NULL, NOW() - INTERVAL 45 MINUTE, @s5);

-- Payments: bills 1 and 2 paid in full, bill 3 part-paid, bill 4 unpaid.
SELECT bill_id INTO @b1 FROM BILL WHERE session_id = @s1;
SELECT bill_id INTO @b2 FROM BILL WHERE session_id = @s2;
SELECT bill_id INTO @b3 FROM BILL WHERE session_id = @s3;
INSERT INTO PAYMENT (bill_id, amount_paid, mode, paid_at) VALUES
(@b1, 70.00, 'UPI',  '2026-10-01 12:41:00');
INSERT INTO PAYMENT (bill_id, amount_paid, mode, paid_at) VALUES
(@b2, 15.00, 'CASH', '2026-10-01 11:36:00');
INSERT INTO PAYMENT (bill_id, amount_paid, mode, paid_at) VALUES
(@b3, 50.00, 'CARD', '2026-10-01 20:52:00');

CALL sp_expire_reservations();

-- =====================================================================
-- A.6 VIEWS
-- =====================================================================
CREATE VIEW vw_free_slots AS
SELECT s.slot_id, f.name AS facility, fl.floor_no, z.zone_name,
       s.slot_no, vt.type_name
FROM SLOT s
JOIN ZONE z          ON z.zone_id = s.zone_id
JOIN FLOOR fl        ON fl.floor_id = z.floor_id
JOIN FACILITY f      ON f.facility_id = fl.facility_id
JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = s.vehicle_type_id
WHERE s.status = 'FREE';

CREATE VIEW vw_zone_occupancy AS
SELECT fl.floor_no, z.zone_name,
       COUNT(*)                                          AS total_slots,
       SUM(CASE WHEN s.status = 'OCCUPIED' THEN 1 ELSE 0 END) AS occupied_slots,
       SUM(CASE WHEN s.status = 'RESERVED' THEN 1 ELSE 0 END) AS reserved_slots,
       SUM(CASE WHEN s.status = 'FREE'     THEN 1 ELSE 0 END) AS free_slots,
       ROUND(100 * SUM(CASE WHEN s.status = 'OCCUPIED' THEN 1 ELSE 0 END)
             / COUNT(*), 1)                              AS occupancy_pct
FROM SLOT s
JOIN ZONE z   ON z.zone_id = s.zone_id
JOIN FLOOR fl ON fl.floor_id = z.floor_id
GROUP BY fl.floor_no, z.zone_name;

CREATE VIEW vw_bill_status AS
SELECT b.bill_id, b.session_id, v.reg_no, b.amount,
       COALESCE(SUM(p.amount_paid), 0)            AS amount_paid,
       b.amount - COALESCE(SUM(p.amount_paid), 0) AS balance
FROM BILL b
JOIN PARKING_SESSION ps ON ps.session_id = b.session_id
JOIN VEHICLE v          ON v.vehicle_id = ps.vehicle_id
LEFT JOIN PAYMENT p     ON p.bill_id = b.bill_id
GROUP BY b.bill_id, b.session_id, v.reg_no, b.amount;

-- =====================================================================
-- A.7 REPORT QUERIES
-- =====================================================================

-- A.7.1 Occupancy by floor and zone (view)
SELECT * FROM vw_zone_occupancy ORDER BY floor_no, zone_name;

-- A.7.2 Peak hours: number of entries in each hour of the day
SELECT HOUR(entry_time) AS entry_hour, COUNT(*) AS entries
FROM PARKING_SESSION
GROUP BY HOUR(entry_time)
ORDER BY entries DESC, entry_hour;

-- A.7.3 Parking duration (minutes) by vehicle type, closed sessions
SELECT vt.type_name,
       COUNT(*)                                                AS sessions,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, ps.entry_time, ps.exit_time)), 1)
                                                               AS avg_minutes,
       MIN(TIMESTAMPDIFF(MINUTE, ps.entry_time, ps.exit_time)) AS min_minutes,
       MAX(TIMESTAMPDIFF(MINUTE, ps.entry_time, ps.exit_time)) AS max_minutes
FROM PARKING_SESSION ps
JOIN VEHICLE v       ON v.vehicle_id = ps.vehicle_id
JOIN VEHICLE_TYPE vt ON vt.vehicle_type_id = v.vehicle_type_id
WHERE ps.exit_time IS NOT NULL
GROUP BY vt.type_name;

-- A.7.4 Pass usage: sessions made by each pass vehicle during validity
SELECT pa.pass_id, c.name AS pass_holder, v.reg_no,
       pa.valid_from, pa.valid_to, COUNT(ps.session_id) AS sessions_used
FROM PASS pa
JOIN CUSTOMER c ON c.customer_id = pa.customer_id
JOIN VEHICLE v  ON v.vehicle_id = pa.vehicle_id
LEFT JOIN PARKING_SESSION ps
       ON ps.vehicle_id = pa.vehicle_id
      AND DATE(ps.entry_time) BETWEEN pa.valid_from AND pa.valid_to
GROUP BY pa.pass_id, c.name, v.reg_no, pa.valid_from, pa.valid_to;

-- A.7.5 Violations
-- (a) Bills not fully paid (revenue leakage)
SELECT * FROM vw_bill_status WHERE balance > 0;

-- (b) Reservations that expired without being used (nested query)
SELECT r.reservation_id, c.name AS customer, v.reg_no, s.slot_no, r.expiry_time
FROM RESERVATION r
JOIN CUSTOMER c ON c.customer_id = r.customer_id
JOIN VEHICLE v  ON v.vehicle_id = r.vehicle_id
JOIN SLOT s     ON s.slot_id = r.slot_id
WHERE r.status = 'EXPIRED'
  AND NOT EXISTS (SELECT 1 FROM PARKING_SESSION ps
                  WHERE ps.reservation_id = r.reservation_id);

-- A.7.6 Free slots of a given vehicle type (view)
SELECT * FROM vw_free_slots WHERE type_name = 'CAR';

-- A.7.7 Revenue collected by date and vehicle type
SELECT DATE(p.paid_at) AS pay_date, vt.type_name,
       SUM(p.amount_paid) AS revenue
FROM PAYMENT p
JOIN BILL b             ON b.bill_id = p.bill_id
JOIN PARKING_SESSION ps ON ps.session_id = b.session_id
JOIN VEHICLE v          ON v.vehicle_id = ps.vehicle_id
JOIN VEHICLE_TYPE vt    ON vt.vehicle_type_id = v.vehicle_type_id
GROUP BY DATE(p.paid_at), vt.type_name
ORDER BY pay_date, vt.type_name;
