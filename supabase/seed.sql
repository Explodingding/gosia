-- =============================================================================
-- Seed - tagi domyslne dla agenta naborow
-- =============================================================================

insert into public.tags (slug, label, category) values
    -- Programy
    ('feng',                'FENG',                                 'program'),
    ('fe-pomorze',          'FE Pomorze 2021-2027',                 'program'),
    ('kpo',                 'KPO',                                  'program'),
    ('kpo-cyfryzacja',      'KPO - transformacja cyfrowa',          'program'),
    ('kpo-zielona',         'KPO - zielona transformacja',          'program'),
    ('kpo-innowacje',       'KPO - innowacje i konkurencyjnosc',    'program'),
    ('parp',                'PARP',                                 'program'),
    ('ncbr',                'NCBR',                                 'program'),
    ('rpo',                 'Regionalny Program Operacyjny',        'program'),
    ('bur',                 'BUR (Baza Uslug Rozwojowych)',         'program'),
    ('lgd',                 'Lokalna Grupa Dzialania',              'program'),

    -- Beneficjenci
    ('msp',                 'MSP',                                  'beneficjent'),
    ('ngo',                 'NGO',                                  'beneficjent'),
    ('samorzad',            'Samorzad',                             'beneficjent'),
    ('startup',             'Start-up',                             'beneficjent'),
    ('duza-firma',          'Duza firma',                           'beneficjent'),

    -- Tematyka
    ('oze',                 'OZE / fotowoltaika',                   'tematyka'),
    ('br',                  'B+R',                                  'tematyka'),
    ('cyfryzacja',          'Cyfryzacja',                           'tematyka'),
    ('produkcja',           'Produkcja',                            'tematyka'),
    ('turystyka',           'Turystyka',                            'tematyka'),
    ('logistyka',           'Logistyka',                            'tematyka'),
    ('medtech',             'Medtech',                              'tematyka'),
    ('industry-4-0',        'Industry 4.0',                         'tematyka'),
    ('efektywnosc-energ',   'Efektywnosc energetyczna',             'tematyka'),
    ('goz',                 'Gospodarka obiegu zamknietego',        'tematyka'),
    ('eksport',             'Eksport / internacjonalizacja',        'tematyka'),
    ('szkolenia',           'Szkolenia / kompetencje',              'tematyka'),

    -- Regiony
    ('woj-pomorskie',       'Wojewodztwo pomorskie',                'region'),
    ('powiat-kartuski',     'Powiat kartuski',                      'region'),
    ('caly-kraj',           'Cala Polska',                          'region')

on conflict (slug) do update set label = excluded.label, category = excluded.category;

-- =============================================================================
-- Seed - zrodla startowe (laduje sources.yaml przez agenta, ale tu sa fallbacki)
-- =============================================================================
-- Pomijamy - sources.yaml jest jedynym zrodlem prawdy, agent przy starcie
-- synchronizuje tabele `sources` z plikiem.
