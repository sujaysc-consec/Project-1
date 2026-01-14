-- Create inventory table
CREATE TABLE IF NOT EXISTS inventory (
    id VARCHAR PRIMARY KEY,
    count INTEGER NOT NULL,
    CONSTRAINT check_inventory_positive CHECK (count >= 0)
);

-- Create purchases table
CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    item_id VARCHAR NOT NULL REFERENCES inventory(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster lookups on purchases by item_id
CREATE INDEX IF NOT EXISTS idx_purchases_item_id ON purchases(item_id);
