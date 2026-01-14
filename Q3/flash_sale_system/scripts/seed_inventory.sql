-- Seed inventory with initial stock
-- Uses upsert to handle re-seeding
INSERT INTO inventory (id, count) 
VALUES (:item_id, :count)
ON CONFLICT (id) DO UPDATE SET count = EXCLUDED.count;
