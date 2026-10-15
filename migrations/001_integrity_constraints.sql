-- =====================================================================
-- Migration 001: database-level integrity rules (October 2026)
-- For a database created with an EARLIER smart_parking.sql. A database
-- created with the current smart_parking.sql already has these changes.
--
-- Adds:
--   PARKING_SESSION.active_vehicle_id + uq_active_vehicle
--       a vehicle can have only one open parking session
--   RESERVATION.active_res_slot_id + uq_active_reservation_slot
--       a slot can have only one ACTIVE reservation
--   trg_payment_bi
--       total payments for a bill cannot exceed the bill amount
--
-- It does not delete or change any existing rows. Take a backup first:
--   mysqldump -h <host> -u <user> -p --routines --triggers smart_parking > backup.sql
-- Run:
--   mysql -h <host> -u <user> -p smart_parking < migrations/001_integrity_constraints.sql
--
-- STEP 1 - pre-checks. Each query must return no rows; if one does, fix
-- those records first (the ALTERs below would otherwise fail safely).
-- =====================================================================
SELECT vehicle_id, COUNT(*) AS open_sessions FROM PARKING_SESSION
WHERE exit_time IS NULL GROUP BY vehicle_id HAVING COUNT(*) > 1;

SELECT slot_id, COUNT(*) AS active_reservations FROM RESERVATION
WHERE status = 'ACTIVE' GROUP BY slot_id HAVING COUNT(*) > 1;

SELECT b.bill_id, b.amount, SUM(p.amount_paid) AS paid FROM BILL b
JOIN PAYMENT p ON p.bill_id = b.bill_id
GROUP BY b.bill_id, b.amount HAVING SUM(p.amount_paid) > b.amount;

-- STEP 2 - schema changes
ALTER TABLE PARKING_SESSION
    ADD COLUMN active_vehicle_id INT GENERATED ALWAYS AS
        (CASE WHEN exit_time IS NULL THEN vehicle_id END) STORED,
    ADD CONSTRAINT uq_active_vehicle UNIQUE (active_vehicle_id);

ALTER TABLE RESERVATION
    ADD COLUMN active_res_slot_id INT GENERATED ALWAYS AS
        (CASE WHEN status = 'ACTIVE' THEN slot_id END) STORED,
    ADD CONSTRAINT uq_active_reservation_slot UNIQUE (active_res_slot_id);

DROP TRIGGER IF EXISTS trg_payment_bi;

DELIMITER //
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
DELIMITER ;
