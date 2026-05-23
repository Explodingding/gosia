# Profil docelowy: InwestycjePomorze.pl

> Ten plik jest wczytywany przez agenta jako kontekst dla LLM przy ocenie dopasowania kazdego nowego naboru. Zmieniaj smialo, jesli profil firmy ewoluuje.

## O firmie

InwestycjePomorze.pl to firma doradcza specjalizujaca sie w pozyskiwaniu funduszy unijnych i krajowych dla przedsiebiorstw. Ponad 20 lat doswiadczenia, 100+ zrealizowanych projektow, 120+ mln zl pozyskanych srodkow.

**Glowna ekspertka**: Malgorzata Klimowska, doradczyni inwestycyjna.
**Lokalizacja**: Banino (gmina Zukowo, powiat kartuski, woj. pomorskie). Obsluga zdalnie na terenie calej Polski.

## Klientela docelowa

- **MSP** (mikro, male, srednie przedsiebiorstwa) - rdzen klienteli
- **NGO** (organizacje pozarzadowe)
- **Samorzady** (gminy, powiaty)
- **Start-upy** technologiczne i medyczne

## Programy i fundusze

### Priorytet 1 (rdzen oferty):
- **FENG** - Fundusze Europejskie dla Nowoczesnej Gospodarki 2021-2027
- **FE Pomorze** - Fundusze Europejskie dla Pomorza 2021-2027
- **KPO** - Krajowy Plan Odbudowy:
  - Transformacja cyfrowa (Industry 4.0, ERP/CRM, IoT)
  - Zielona transformacja (OZE, fotowoltaika, efektywnosc energetyczna, GOZ)
  - Innowacje i konkurencyjnosc (B+R)

### Priorytet 2:
- Programy regionalne RPO
- PARP - dotacje dla MSP
- NCBR - badania i rozwoj, innowacje
- BUR - Baza Uslug Rozwojowych (dofinansowane szkolenia)
- Programy LGD (lokalne grupy dzialania)

## Branze i tematyki, ktore szczegolnie interesuja klientow

- Produkcja przemyslowa, modernizacja linii produkcyjnych
- B+R, centra badawczo-rozwojowe
- OZE, fotowoltaika, magazyny energii
- Cyfryzacja MSP, ERP/CRM, automatyzacja
- Turystyka, infrastruktura turystyczna
- Start-upy, w tym medtech
- Logistyka, intermodal

## Region priorytetowy

- **Banino, gmina Zukowo, powiat kartuski** - lokalna baza klientow
- **Wojewodztwo pomorskie** - cala oferta regionalna
- **Cala Polska** - obsluga zdalna, programy ogolnokrajowe

## Co jest CIEKAWE dla naszego klienta (wysoki match)

- Nabor jest otwarty lub planowany w ciagu 3 miesiecy
- Beneficjent: MSP / NGO / samorzad / start-up
- Region: cala Polska, woj. pomorskie, lub program ogolnokrajowy
- Kwota dofinansowania: od 50 tys. zl wzwyz (mniejsze sa rzadko oplacalne dla naszych klientow)
- Tematyka pasuje do branz powyzej

## Co jest MNIEJ ciekawe (niski match)

- Nabor zakonczony lub konczacy sie w ciagu 7 dni (nie ma czasu na wniosek)
- Beneficjent wylacznie dla duzych korporacji (>250 osob)
- Beneficjent wylacznie z innego regionu (np. tylko Slask/Mazowsze)
- Tematyka odlegla (np. tylko rolnictwo wielkoobszarowe, jesli nie mamy klientow rolnych)
- Kwota minimalna ponizej 30 tys. zl (czesto nieoplacalna)

## Jak ocenic profile_match_score (0-100)

- **90-100**: idealny - region pomorski lub ogolnopolski, MSP/NGO/samorzad, FENG/KPO/FE Pomorze, otwarty/nadchodzacy, kwota >= 100 tys.
- **70-89**: bardzo dobry - pasuje do profilu, ale jeden czynnik osabia (np. kwota 50-100 tys., region slabiej dopasowany)
- **50-69**: warto sprawdzic - czesc pasuje, czesc nie
- **30-49**: marginalny - tylko luzny zwiazek z profilem
- **0-29**: nieinteresujacy - inne wojewodztwo wylacznie, niewlasciwy beneficjent, tematyka odlegla

W polu `profile_match_reason` zawsze podaj 1-2 zdania PO POLSKU, co konkretnie sprawia, ze ten score jest taki, jaki jest.
