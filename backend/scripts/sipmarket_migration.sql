-- ABVTrends Production Migration: SipMarket Products
-- Run this SQL on your production AWS RDS database

-- Ensure SipMarket distributor exists
INSERT INTO distributors (id, name, slug, website, description, api_type, requires_auth, rate_limit, is_active, created_at, updated_at)
VALUES (2, 'SipMarket (Crest Beverage/Reyes)', 'sipmarket', 'https://www.sipmarket.com', 'SipMarket ordering platform for Crest Beverage (Reyes Holdings)', 'web_scrape', true, 2.0, true, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 20 products to migrate

-- Glen Moray Port Cask - 6 - 750ml Bottles
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('4b8335b4-5935-45da-a2b8-490dfae6bb56', 'Glen Moray Port Cask - 6 - 750ml Bottles', 'Glen Moray', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('38', '4b8335b4-5935-45da-a2b8-490dfae6bb56', 'sipmarket', '120259BW', 'Glen Moray Port Cask - 6 - 750ml Bottles', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('4b8335b4-5935-45da-a2b8-490dfae6bb56', 2, 27.53, 'unit', 'USD', NOW());

-- Glen Moray 12 Year Old - 6 - 750ml Bottl
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('22dc6f69-cc02-4d35-a33b-54845f53cb33', 'Glen Moray 12 Year Old - 6 - 750ml Bottles', 'Glen Moray', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('36', '22dc6f69-cc02-4d35-a33b-54845f53cb33', 'sipmarket', '120270BW', 'Glen Moray 12 Year Old - 6 - 750ml Bottles', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('22dc6f69-cc02-4d35-a33b-54845f53cb33', 2, 35.18, 'unit', 'USD', NOW());

-- 6666 Blended Whiskey - 750ml Bottle
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('fc16bc34-0192-4dd9-b296-a36ab1b4f42c', '6666 Blended Whiskey - 750ml Bottle', 'Four Sixes', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('22', 'fc16bc34-0192-4dd9-b296-a36ab1b4f42c', 'sipmarket', '121239BW', '6666 Blended Whiskey - 750ml Bottle', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('fc16bc34-0192-4dd9-b296-a36ab1b4f42c', 2, 27.59, 'unit', 'USD', NOW());

-- 6666 Blended Whiskey - 6 - 750ml Bottles
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('5f2ddf49-185c-4756-9967-7ec371e9db72', '6666 Blended Whiskey - 6 - 750ml Bottles Case', 'Four Sixes', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('21', '5f2ddf49-185c-4756-9967-7ec371e9db72', 'sipmarket', '121239CW', '6666 Blended Whiskey - 6 - 750ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('5f2ddf49-185c-4756-9967-7ec371e9db72', 2, 138.55, 'unit', 'USD', NOW());

-- Giffard Aperitif Syrup - 6 - 1 Liter Bot
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('9a1ca07b-23bb-4328-9d00-0100f80fe72f', 'Giffard Aperitif Syrup - 6 - 1 Liter Bottles Case', 'Giffard Non-Alcoholic Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('27', '9a1ca07b-23bb-4328-9d00-0100f80fe72f', 'sipmarket', '123108CW', 'Giffard Aperitif Syrup - 6 - 1 Liter Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('9a1ca07b-23bb-4328-9d00-0100f80fe72f', 2, 106.10, 'unit', 'USD', NOW());

-- Giffard Lichi-Li - 6 - 750ml Bottles Cas
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('65a145b9-0548-472e-9555-1ec07229c7cf', 'Giffard Lichi-Li - 6 - 750ml Bottles Case', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('23', '65a145b9-0548-472e-9555-1ec07229c7cf', 'sipmarket', '123136CW', 'Giffard Lichi-Li - 6 - 750ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('65a145b9-0548-472e-9555-1ec07229c7cf', 2, 155.40, 'unit', 'USD', NOW());

-- Giffard Mangue - 6 - 750ml Bottles
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('2838e014-6f53-4229-b3f1-5174e4d15e97', 'Giffard Mangue - 6 - 750ml Bottles', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('24', '2838e014-6f53-4229-b3f1-5174e4d15e97', 'sipmarket', '123137BW', 'Giffard Mangue - 6 - 750ml Bottles', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('2838e014-6f53-4229-b3f1-5174e4d15e97', 2, 25.90, 'unit', 'USD', NOW());

-- Giffard Menthe Pastille - 1 Liter Bottle
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('283e275b-f67f-4e93-91e1-1ef23eea5367', 'Giffard Menthe Pastille - 1 Liter Bottle', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('25', '283e275b-f67f-4e93-91e1-1ef23eea5367', 'sipmarket', '123138BW', 'Giffard Menthe Pastille - 1 Liter Bottle', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('283e275b-f67f-4e93-91e1-1ef23eea5367', 2, 31.17, 'unit', 'USD', NOW());

-- Giffard Menthe Pastille - 6 - 1 Liter Bo
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('a7228fd5-ed5d-4bd3-be80-77ec5af7f47e', 'Giffard Menthe Pastille - 6 - 1 Liter Bottles Case', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('26', 'a7228fd5-ed5d-4bd3-be80-77ec5af7f47e', 'sipmarket', '123138CW', 'Giffard Menthe Pastille - 6 - 1 Liter Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('a7228fd5-ed5d-4bd3-be80-77ec5af7f47e', 2, 187.02, 'unit', 'USD', NOW());

-- Giffard Orgeat Syrup - 6 - 350ml Bottles
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('8e30e297-8088-4e7c-8530-78aab9ae4a03', 'Giffard Orgeat Syrup - 6 - 350ml Bottles Case', 'Giffard Non-Alcoholic Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('29', '8e30e297-8088-4e7c-8530-78aab9ae4a03', 'sipmarket', '123140CW', 'Giffard Orgeat Syrup - 6 - 350ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('8e30e297-8088-4e7c-8530-78aab9ae4a03', 2, 91.50, 'unit', 'USD', NOW());

-- Giffard Piment d'Espelette - 6 - 750ml B
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('e006896b-f609-41ad-90e9-d3523e172eda', 'Giffard Piment d''Espelette - 6 - 750ml Bottles Case', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('30', 'e006896b-f609-41ad-90e9-d3523e172eda', 'sipmarket', '123141CW', 'Giffard Piment d''Espelette - 6 - 750ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('e006896b-f609-41ad-90e9-d3523e172eda', 2, 187.02, 'unit', 'USD', NOW());

-- Giffard Non-Alcoholic Pineapple Liqueur 
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('7acd31a8-a83c-4dcb-b67c-20d80b9fde8c', 'Giffard Non-Alcoholic Pineapple Liqueur - 6 - 700ml Bottles Case', 'Giffard Non-Alcoholic Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('31', '7acd31a8-a83c-4dcb-b67c-20d80b9fde8c', 'sipmarket', '123142CW', 'Giffard Non-Alcoholic Pineapple Liqueur - 6 - 700ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('7acd31a8-a83c-4dcb-b67c-20d80b9fde8c', 2, 142.50, 'unit', 'USD', NOW());

-- Giffard Rhubarbe - 750ml Bottle
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('909a86ea-c6f8-4aec-b77a-f413e34dbcf2', 'Giffard Rhubarbe - 750ml Bottle', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('32', '909a86ea-c6f8-4aec-b77a-f413e34dbcf2', 'sipmarket', '123143BW', 'Giffard Rhubarbe - 750ml Bottle', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('909a86ea-c6f8-4aec-b77a-f413e34dbcf2', 2, 25.90, 'unit', 'USD', NOW());

-- Giffard Rhubarbe - 6 - 750ml Bottles Cas
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('fcefd72c-c711-416a-b78c-4d3659d7a0a4', 'Giffard Rhubarbe - 6 - 750ml Bottles Case', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('33', 'fcefd72c-c711-416a-b78c-4d3659d7a0a4', 'sipmarket', '123143CW', 'Giffard Rhubarbe - 6 - 750ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('fcefd72c-c711-416a-b78c-4d3659d7a0a4', 2, 155.40, 'unit', 'USD', NOW());

-- Giffard Vanille de Madagascar - 750ml Bo
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('55dbccc8-f93f-4eb7-9d16-65e60ef9f95e', 'Giffard Vanille de Madagascar - 750ml Bottle', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('34', '55dbccc8-f93f-4eb7-9d16-65e60ef9f95e', 'sipmarket', '123145BW', 'Giffard Vanille de Madagascar - 750ml Bottle', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('55dbccc8-f93f-4eb7-9d16-65e60ef9f95e', 2, 31.17, 'unit', 'USD', NOW());

-- Giffard Wild Elderflower - 6 - 750ml Bot
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('90a19e1a-4585-4a08-bfa1-4efcc64c9189', 'Giffard Wild Elderflower - 6 - 750ml Bottles Case', 'Giffard Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('35', '90a19e1a-4585-4a08-bfa1-4efcc64c9189', 'sipmarket', '123146CW', 'Giffard Wild Elderflower - 6 - 750ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('90a19e1a-4585-4a08-bfa1-4efcc64c9189', 2, 187.02, 'unit', 'USD', NOW());

-- Giffard Non-Alcoholic Grapefruit - 700ml
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('6228eb89-0563-48d0-a828-8120479110c3', 'Giffard Non-Alcoholic Grapefruit - 700ml Bottle', 'Giffard Non-Alcoholic Liqueurs', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('28', '6228eb89-0563-48d0-a828-8120479110c3', 'sipmarket', '123358BW', 'Giffard Non-Alcoholic Grapefruit - 700ml Bottle', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('6228eb89-0563-48d0-a828-8120479110c3', 2, 28.25, 'unit', 'USD', NOW());

-- Grind Espresso Rum - 750ml Bottle
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('e1b0c491-235d-47d8-8f67-adf913161c94', 'Grind Espresso Rum - 750ml Bottle', 'Grind', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('40', 'e1b0c491-235d-47d8-8f67-adf913161c94', 'sipmarket', '323546BW', 'Grind Espresso Rum - 750ml Bottle', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('e1b0c491-235d-47d8-8f67-adf913161c94', 2, 15.54, 'unit', 'USD', NOW());

-- Grind Caramel Rum - 12 - 750ml Bottles C
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('5a34fd3f-50ab-4914-b39a-6b2ccfec4f84', 'Grind Caramel Rum - 12 - 750ml Bottles Case', 'Grind', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('39', '5a34fd3f-50ab-4914-b39a-6b2ccfec4f84', 'sipmarket', '325065CW', 'Grind Caramel Rum - 12 - 750ml Bottles Case', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('5a34fd3f-50ab-4914-b39a-6b2ccfec4f84', 2, 159.52, 'unit', 'USD', NOW());

-- Glen Moray 12 Year Old - B96 50ML
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('e76cec92-4dbd-473d-aaa5-651c448981ad', 'Glen Moray 12 Year Old - B96 50ML', 'Glen Moray', 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, brand = EXCLUDED.brand, updated_at = NOW();
INSERT INTO product_aliases (id, product_id, source, external_id, external_name, confidence, created_at) VALUES ('37', 'e76cec92-4dbd-473d-aaa5-651c448981ad', 'sipmarket', '60304', 'Glen Moray 12 Year Old - B96 50ML', 1.0, NOW()) ON CONFLICT (id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('e76cec92-4dbd-473d-aaa5-651c448981ad', 2, 296.91, 'unit', 'USD', NOW());

