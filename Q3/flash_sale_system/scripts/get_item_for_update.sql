-- Acquire row-level lock on inventory item
SELECT id, count 
FROM inventory 
WHERE id = :item_id 
FOR UPDATE;
