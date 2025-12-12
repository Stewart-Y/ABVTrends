-- ABVTrends Production Migration: Park Street Products
-- Run this SQL on your production AWS RDS database

-- Ensure Park Street distributor exists (id=3)
INSERT INTO distributors (id, name, slug, website, api_base_url, scraper_class, is_active, created_at, updated_at)
VALUES (3, 'Park Street Imports', 'parkstreet', 'https://app.parkstreet.com', 'https://api.parkstreet.com/v1', 'ParkStreetScraper', true, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 30 products to migrate

-- Margarita Mix
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('d31877e2-c76d-4560-933a-291e5bdf0cd5', 'Margarita Mix', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('d31877e2-c76d-4560-933a-291e5bdf0cd5', 'parkstreet', 'HRB-MARMX1L-081626', 'Margarita Mix', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('d31877e2-c76d-4560-933a-291e5bdf0cd5', 3, 48.78, 'case', 'USD', NOW());

-- Margarita Mix
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('8333d4f5-2e74-46cf-ba36-2feadbaa7d00', 'Margarita Mix', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('8333d4f5-2e74-46cf-ba36-2feadbaa7d00', 'parkstreet', 'HRB-MARMX1L-062226', 'Margarita Mix', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('8333d4f5-2e74-46cf-ba36-2feadbaa7d00', 3, 48.78, 'case', 'USD', NOW());

-- Margarita Mix
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('7f8aed9c-000a-42a0-9784-b770b9ba8fb0', 'Margarita Mix', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('7f8aed9c-000a-42a0-9784-b770b9ba8fb0', 'parkstreet', 'HRB-MARMX1L-02252025', 'Margarita Mix', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('7f8aed9c-000a-42a0-9784-b770b9ba8fb0', 3, 48.78, 'case', 'USD', NOW());

-- James Asian Parsnip Gin
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('d8e7d4f5-13c0-43da-8ced-08fee536ce19', 'James Asian Parsnip Gin', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('d8e7d4f5-13c0-43da-8ced-08fee536ce19', 'parkstreet', 'ARS-JAPGIN-700', 'James Asian Parsnip Gin', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('d8e7d4f5-13c0-43da-8ced-08fee536ce19', 3, 143.96, 'case', 'USD', NOW());

-- James London Drizzle
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('522aa28a-ccbb-43ed-bdad-d4214b116143', 'James London Drizzle', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('522aa28a-ccbb-43ed-bdad-d4214b116143', 'parkstreet', 'ARS-LDRIZGIN-700', 'James London Drizzle', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('522aa28a-ccbb-43ed-bdad-d4214b116143', 3, 143.96, 'case', 'USD', NOW());

-- James Gin American Mustard
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('bf627e11-e6f1-467f-b519-bcd2045e905d', 'James Gin American Mustard', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('bf627e11-e6f1-467f-b519-bcd2045e905d', 'parkstreet', 'ARS-MUSTGIN-700', 'James Gin American Mustard', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('bf627e11-e6f1-467f-b519-bcd2045e905d', 3, 143.96, 'case', 'USD', NOW());

-- Gil The Authentic Rural Gin
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('c8e57eeb-8c61-44e5-a13d-a73141f39f3a', 'Gil The Authentic Rural Gin', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('c8e57eeb-8c61-44e5-a13d-a73141f39f3a', 'parkstreet', 'CGI-GILAUGIN6-700', 'Gil The Authentic Rural Gin', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('c8e57eeb-8c61-44e5-a13d-a73141f39f3a', 3, 190.80, 'case', 'USD', NOW());

-- Roger Amaro Tenere Sotto Banco Liqueur
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('7c993eb1-e196-435c-9526-b0ccbccc03fa', 'Roger Amaro Tenere Sotto Banco Liqueur', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('7c993eb1-e196-435c-9526-b0ccbccc03fa', 'parkstreet', 'CGI-ROAMTSB6-700', 'Roger Amaro Tenere Sotto Banco Liqueur', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('7c993eb1-e196-435c-9526-b0ccbccc03fa', 3, 264.00, 'case', 'USD', NOW());

-- Stiletto Old Fashioned
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('90312583-0392-4c47-981f-9188890a7291', 'Stiletto Old Fashioned', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('90312583-0392-4c47-981f-9188890a7291', 'parkstreet', 'GLY-STILOF-375', 'Stiletto Old Fashioned', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('90312583-0392-4c47-981f-9188890a7291', 3, 138.00, 'case', 'USD', NOW());

-- Aldez Tequila Añejo 100% Puro de Agave Organic Teq
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('810db6bd-3be1-41b7-aba5-ac466eba4b9e', 'Aldez Tequila Añejo 100% Puro de Agave Organic Tequila', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('810db6bd-3be1-41b7-aba5-ac466eba4b9e', 'parkstreet', 'JMS-ANEJO1022-750', 'Aldez Tequila Añejo 100% Puro de Agave Organic Tequila', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('810db6bd-3be1-41b7-aba5-ac466eba4b9e', 3, 342.00, 'case', 'USD', NOW());

-- Aldez Tequila Blanco  100% Puro De Agave Organic
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('0e3bd639-351f-4902-aa06-d47c6c139608', 'Aldez Tequila Blanco  100% Puro De Agave Organic', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('0e3bd639-351f-4902-aa06-d47c6c139608', 'parkstreet', 'JMS-BLANCO1022-750', 'Aldez Tequila Blanco  100% Puro De Agave Organic', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('0e3bd639-351f-4902-aa06-d47c6c139608', 3, 240.00, 'case', 'USD', NOW());

-- Riojana Cabernet Sauvignon
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('bcfa4ed9-a6c1-4454-b0a6-8fee4d272988', 'Riojana Cabernet Sauvignon', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('bcfa4ed9-a6c1-4454-b0a6-8fee4d272988', 'parkstreet', 'LRJ-10047-113', 'Riojana Cabernet Sauvignon', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('bcfa4ed9-a6c1-4454-b0a6-8fee4d272988', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Cabernet Sauvignon
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('2edce51f-c040-4a4d-830a-42496f8d7157', 'Riojana Cabernet Sauvignon', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('2edce51f-c040-4a4d-830a-42496f8d7157', 'parkstreet', 'LRJ-10047-115', 'Riojana Cabernet Sauvignon', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('2edce51f-c040-4a4d-830a-42496f8d7157', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Cabernet Sauvignon
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('ad999df3-7b9e-4840-af04-49b369632edc', 'Riojana Cabernet Sauvignon', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('ad999df3-7b9e-4840-af04-49b369632edc', 'parkstreet', 'LRJ-10047-116', 'Riojana Cabernet Sauvignon', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('ad999df3-7b9e-4840-af04-49b369632edc', 3, 68.00, 'case', 'USD', NOW());

-- RIOJANA - ENTRY LEVEL CHARDONNAY
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('226053cc-1c52-4835-80cc-8c30290bcea3', 'RIOJANA - ENTRY LEVEL CHARDONNAY', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('226053cc-1c52-4835-80cc-8c30290bcea3', 'parkstreet', 'LRJ-10048-113', 'RIOJANA - ENTRY LEVEL CHARDONNAY', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('226053cc-1c52-4835-80cc-8c30290bcea3', 3, 68.00, 'case', 'USD', NOW());

-- Riojana White Wine
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('367796d9-abf7-43ed-b030-31326dca359b', 'Riojana White Wine', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('367796d9-abf7-43ed-b030-31326dca359b', 'parkstreet', 'LRJ-10048-115', 'Riojana White Wine', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('367796d9-abf7-43ed-b030-31326dca359b', 3, 68.00, 'case', 'USD', NOW());

-- Riojana White Wine
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('dea097cb-8573-4aa5-a129-77150483e763', 'Riojana White Wine', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('dea097cb-8573-4aa5-a129-77150483e763', 'parkstreet', 'LRJ-10048-116', 'Riojana White Wine', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('dea097cb-8573-4aa5-a129-77150483e763', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Malbec
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('ecc70ccd-df02-484f-b995-4cabebee2c91', 'Riojana Malbec', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('ecc70ccd-df02-484f-b995-4cabebee2c91', 'parkstreet', 'LRJ-10050-113', 'Riojana Malbec', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('ecc70ccd-df02-484f-b995-4cabebee2c91', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Malbec
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('dd185734-5af8-42be-8142-2d2b03d72fad', 'Riojana Malbec', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('dd185734-5af8-42be-8142-2d2b03d72fad', 'parkstreet', 'LRJ-10050-115', 'Riojana Malbec', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('dd185734-5af8-42be-8142-2d2b03d72fad', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Malbec
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('8409c509-4195-4c55-be1d-391f383a74dc', 'Riojana Malbec', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('8409c509-4195-4c55-be1d-391f383a74dc', 'parkstreet', 'LRJ-10050-116', 'Riojana Malbec', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('8409c509-4195-4c55-be1d-391f383a74dc', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Reserva Malbec
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('de207f19-eba5-46b5-acbe-8df7355fba0b', 'Riojana Reserva Malbec', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('de207f19-eba5-46b5-acbe-8df7355fba0b', 'parkstreet', 'LRJ-10051-115', 'Riojana Reserva Malbec', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('de207f19-eba5-46b5-acbe-8df7355fba0b', 3, 96.00, 'case', 'USD', NOW());

-- RIOJANA - PINOT NOIR RESERVA
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('1a9e8a78-d6a5-4a50-879f-d1c49ce0a571', 'RIOJANA - PINOT NOIR RESERVA', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('1a9e8a78-d6a5-4a50-879f-d1c49ce0a571', 'parkstreet', 'LRJ-10052-115', 'RIOJANA - PINOT NOIR RESERVA', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('1a9e8a78-d6a5-4a50-879f-d1c49ce0a571', 3, 96.00, 'case', 'USD', NOW());

-- Riojana Reserva Red Blend
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('e28d93a2-f45e-41d1-b1e5-b86b232ee50f', 'Riojana Reserva Red Blend', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('e28d93a2-f45e-41d1-b1e5-b86b232ee50f', 'parkstreet', 'LRJ-10053-115', 'Riojana Reserva Red Blend', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('e28d93a2-f45e-41d1-b1e5-b86b232ee50f', 3, 96.00, 'case', 'USD', NOW());

-- Riojana Reserva Red Blend
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('e41abc4a-a5aa-4e64-9cf4-6f1a2e60a046', 'Riojana Reserva Red Blend', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('e41abc4a-a5aa-4e64-9cf4-6f1a2e60a046', 'parkstreet', 'LRJ-10053-116', 'Riojana Reserva Red Blend', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('e41abc4a-a5aa-4e64-9cf4-6f1a2e60a046', 3, 96.00, 'case', 'USD', NOW());

-- Riojana White Wine
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('05ad164b-800e-4667-8766-73b019773a69', 'Riojana White Wine', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('05ad164b-800e-4667-8766-73b019773a69', 'parkstreet', 'LRJ-10055-113', 'Riojana White Wine', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('05ad164b-800e-4667-8766-73b019773a69', 3, 68.00, 'case', 'USD', NOW());

-- RIOJANA - ENTRY LEVEL TORRONTÉS RIOJANO
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('0f61b0e7-551e-4185-939a-dd59a7857c79', 'RIOJANA - ENTRY LEVEL TORRONTÉS RIOJANO', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('0f61b0e7-551e-4185-939a-dd59a7857c79', 'parkstreet', 'LRJ-10055-115', 'RIOJANA - ENTRY LEVEL TORRONTÉS RIOJANO', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('0f61b0e7-551e-4185-939a-dd59a7857c79', 3, 68.00, 'case', 'USD', NOW());

-- RIOJANA - ENTRY LEVEL TORRONTÉS RIOJANO
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('224bc025-16bb-4767-a409-305dc8f16596', 'RIOJANA - ENTRY LEVEL TORRONTÉS RIOJANO', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('224bc025-16bb-4767-a409-305dc8f16596', 'parkstreet', 'LRJ-10055-116', 'RIOJANA - ENTRY LEVEL TORRONTÉS RIOJANO', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('224bc025-16bb-4767-a409-305dc8f16596', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Bonarda Malbec
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('0fa768bd-3604-4cbc-8821-1576a9752de6', 'Riojana Bonarda Malbec', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('0fa768bd-3604-4cbc-8821-1576a9752de6', 'parkstreet', 'LRJ-10056-113', 'Riojana Bonarda Malbec', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('0fa768bd-3604-4cbc-8821-1576a9752de6', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Bonarda Malbec
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('92274855-68cc-40fa-a9b0-bb3dc37e0531', 'Riojana Bonarda Malbec', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('92274855-68cc-40fa-a9b0-bb3dc37e0531', 'parkstreet', 'LRJ-10056-115', 'Riojana Bonarda Malbec', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('92274855-68cc-40fa-a9b0-bb3dc37e0531', 3, 68.00, 'case', 'USD', NOW());

-- Riojana Bonarda Malbec
INSERT INTO products (id, name, brand, category, is_active, created_at, updated_at) VALUES ('03147a59-d900-419a-98a9-caf8b19fe7f6', 'Riojana Bonarda Malbec', NULL, 'SPIRITS', true, NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
INSERT INTO product_aliases (product_id, source, external_id, external_name, confidence, created_at) VALUES ('03147a59-d900-419a-98a9-caf8b19fe7f6', 'parkstreet', 'LRJ-10056-116', 'Riojana Bonarda Malbec', 1.0, NOW()) ON CONFLICT (product_id, source, external_id) DO NOTHING;
INSERT INTO price_history (product_id, distributor_id, price, price_type, currency, recorded_at) VALUES ('03147a59-d900-419a-98a9-caf8b19fe7f6', 3, 68.00, 'case', 'USD', NOW());

