-- Atomically decrement inventory and record purchase
-- Uses CTE to ensure both operations succeed or fail together
-- Only decrements if count > 0 (prevents overselling)
WITH updated AS (
    UPDATE inventory 
    SET count = count - 1 
    WHERE id = :item_id AND count > 0
    RETURNING id, count
)
INSERT INTO purchases (item_id)
SELECT id FROM updated
RETURNING id AS purchase_id, (SELECT count FROM updated) AS remaining_count;
