-- Add bidding_strategy column to campaigns table
ALTER TABLE campaigns 
ADD COLUMN bidding_strategy VARCHAR(50);

-- Update existing campaigns with random bidding strategies
UPDATE campaigns
SET bidding_strategy = CASE 
    WHEN random() < 0.5 THEN 'Manual'
    ELSE 'Auto'
END;

-- Verify
SELECT bidding_strategy, COUNT(*) as count
FROM campaigns
GROUP BY bidding_strategy;