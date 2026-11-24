-- seed.sql : initial data for the `derecho` database. Run after schema.sql.
USE derecho;

-- Cities inside the d01 domain (lat 37.2-45.5 N, lon -97.6 to -80.4).
-- Coordinates and populations are approximate (city centre, 2020 census).
INSERT INTO cities (city_id, name, state, lat, lon, population) VALUES
 (1,  'Chicago',        'IL', 41.8781, -87.6298, 2746388),
 (2,  'Gary',           'IN', 41.5934, -87.3464,   69093),
 (3,  'Fort Wayne',     'IN', 41.0793, -85.1394,  263886),
 (4,  'Des Moines',     'IA', 41.5868, -93.6250,  214133),
 (5,  'Milwaukee',      'WI', 43.0389, -87.9065,  577222),
 (6,  'Indianapolis',   'IN', 39.7684, -86.1581,  887642),
 (7,  'Cedar Rapids',   'IA', 41.9779, -91.6656,  137710),
 (8,  'Dubuque',        'IA', 42.5006, -90.6648,   59667),
 (9,  'South Bend',     'IN', 41.6764, -86.2520,  103453),
 (10, 'Columbus',       'OH', 39.9612, -82.9988,  905748),
 (11, 'Detroit',        'MI', 42.3314, -83.0458,  639111),
 (12, 'Madison',        'WI', 43.0731, -89.4012,  269840),
 (13, 'Kansas City',    'MO', 39.0997, -94.5786,  508090),
 (14, 'Omaha',          'NE', 41.2565, -95.9345,  486051),
 (15, 'Springfield',    'IL', 39.7817, -89.6501,  114694),
 (16, 'Peoria',         'IL', 40.6936, -89.5890,  113150),
 (17, 'Rockford',       'IL', 42.2711, -89.0940,  148655),
 (18, 'Grand Rapids',   'MI', 42.9634, -85.6681,  198917),
 (19, 'Toledo',         'OH', 41.6528, -83.5379,  270102),
 (20, 'Davenport',      'IA', 41.5236, -90.5776,  101724);

-- ASOS stations (airport weather stations near those cities). Approximate coordinates.
INSERT INTO stations (station_id, name, state, lat, lon) VALUES
 ('KORD', 'Chicago O''Hare Intl',       'IL', 41.9786, -87.9048),
 ('KMDW', 'Chicago Midway Intl',        'IL', 41.7861, -87.7522),
 ('KGYY', 'Gary/Chicago Intl',          'IN', 41.6163, -87.4128),
 ('KFWA', 'Fort Wayne Intl',            'IN', 40.9785, -85.1951),
 ('KDSM', 'Des Moines Intl',            'IA', 41.5340, -93.6631),
 ('KMKE', 'Milwaukee Mitchell Intl',    'WI', 42.9472, -87.8966),
 ('KIND', 'Indianapolis Intl',          'IN', 39.7173, -86.2944),
 ('KCID', 'Cedar Rapids The Eastern Iowa', 'IA', 41.8847, -91.7108),
 ('KDBQ', 'Dubuque Regional',           'IA', 42.4020, -90.7095),
 ('KSBN', 'South Bend Intl',            'IN', 41.7087, -86.3173),
 ('KCMH', 'Columbus John Glenn Intl',   'OH', 39.9980, -82.8919),
 ('KDTW', 'Detroit Metro Wayne County', 'MI', 42.2124, -83.3534),
 ('KMSN', 'Madison Dane County Regional', 'WI', 43.1399, -89.3375),
 ('KMLI', 'Quad Cities Intl',           'IL', 41.4485, -90.5075),
 ('KRFD', 'Rockford Intl',              'IL', 42.1954, -89.0972),
 ('KPIA', 'Peoria Intl',                'IL', 40.6642, -89.6933),
 ('KGRR', 'Grand Rapids Gerald R. Ford Intl', 'MI', 42.8808, -85.5228),
 ('KTOL', 'Toledo Express',             'OH', 41.5868, -83.8078);

-- Runs: values taken from Derecho_Report.pdf (Table 5) and namelist.input.
-- Only case1 (Thompson) is loaded in the data lake.
INSERT INTO runs (run_id, scheme, mp_physics, ranks, wrf_walltime_s, real_walltime_s,
                  sec_per_sim_hour, d01_dx_m, d02_dx_m, start_utc, end_utc, hardware) VALUES
 (1, 'thompson', 8, 32, 16424, 52.0, 684, 3000, 1000,
  '2026-08-11 00:00:00', '2026-08-12 00:00:00',
  'NVIDIA LaunchPad, 1 node, 2x Intel Xeon Gold 6548Y+, cores 32-63, 1 TB RAM');

-- Morrison (case2) is not loaded. Uncomment if its data is added later:
-- INSERT INTO runs VALUES (2, 'morrison', 10, 32, 14897, 48.3, 621, 3000, 1000,
--   '2026-08-11 00:00:00', '2026-08-12 00:00:00',
--   'NVIDIA LaunchPad, 1 node, 2x Intel Xeon Gold 6548Y+, cores 32-63, 1 TB RAM');
