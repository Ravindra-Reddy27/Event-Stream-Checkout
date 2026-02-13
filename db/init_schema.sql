-- 1. Inventory Table 
CREATE TABLE IF NOT EXISTS inventory (
    product_id VARCHAR(255) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    quantity_available INT NOT NULL
);

-- 2. Populate Sample Data 
INSERT INTO inventory (product_id, product_name, quantity_available) VALUES
('prod-101', 'Wireless Headphones', 50),
('prod-102', 'Mechanical Keyboard', 20),
('prod-103', 'Gaming Mouse', 35),
('prod-104', 'USB-C Monitor', 10),
('prod-105', 'Ergonomic Chair', 5);

-- 3. Orders Table 
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    items JSON NOT NULL,
    status ENUM('PENDING', 'PROCESSED', 'FAILED') NOT NULL DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME NULL
);