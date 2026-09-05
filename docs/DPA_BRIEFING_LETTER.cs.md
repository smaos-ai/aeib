# Predbežná regulačná notifikácia – SMAOS (Sovereign Multi-Agent OS)

**Adresát:** Úrad na ochranu osobných údajov (ÚOOÚ)  
**Vecnosť:** Oznámenie o implementácii deterministické správy AI systémů (SMAOS) podle Nařízení EU 2024/1689  
**Dátum:** 1. september 2026  
**Podnikateľ:** Ostrov micro, s.r.o., Karlovy Vary

---

## Obsah

Vážení predstavitelia,

tímto zastupujeme svoju výchovu technické sumarizácie suverénního systému riadenia autonomných agentov (SMAOS) vypracovaného pre regionálne subjekty v Karlovarskom kraji. Projekt je v súlade s Nariadením Európskeho parlamentu a Rady (EU) 2024/1689 o umelo inteligenčných systémoch.

---

## 1. Garancie Suverenity Údajov (Článok 10)

### Lokálny režim bez cloudových služieb
Systém SMAOS beží výlučne v **lokálnom režime** na vlastnom hardvári hostitela bez akéhokoľvek prenosu údajov do zahraničných cloudov (Azure, AWS, GCP atď.).

- **Hardware:** NVIDIA RTX 4060 (8 GB VRAM) alebo vyššie
- **Operačný systém:** Linux (Ubuntu 22.04 LTS)
- **Siťová kontrola:** Aplikácia `SovereignEgressFirewall` blokuje všetky neschválené odchádzajúce pripojenia
- **Overená konečnosť:** Žiadne biometrické alebo operačné údaje neopúšťajú fyzické priestory subjektu

### Prístupové kontroly (Článok 6)
- Fyzické prístupy: Uzamknutá miestnosť s CCTV monitoringom
- Digitálne prístupy: SSH klávesy + TOTP 2FA
- Auditná záznama: Všetky prístupy zaznamenané do neupraviteľného AP2 ledgera

---

## 2. Pred-exekučné kontrolné brány (Články 9 a 14)

### L3 Kontrolné Brány
Pred vykonaním akéhokoľvek nástroja sa spustí päťstupňová kontrola:

1. **L3A-Policy Gate:** Overí sa dodržiavanie politiky (napríklad: je akteur autorizovaný?)
2. **L3A-Tool Gate:** Overí sa, či je nástroj povolený pre daný prípad (napríklad: credit check povolený pre hoteliers?)
3. **L3A-Scope Gate:** Overí sa rozsah (napr. počet záznamov nesmie prekročiť limit)
4. **L3A-RateLimit Gate:** Overí sa frekvencia hovorov (napr. max 100 požiadaviek za minútu)
5. **L3A-Proof Gate:** Overí sa kryptografický dôkaz (Ed25519 podpis)

### L3B Kryptografické Záväzky
Pre vysokoriziká rozhodnutia (Annex III) vyžaduje systém **deterministické pozastavenie** a ruční podpis oprávneného operátora:

```
Hotelový prípad: Hostiteľ žiada schválenie úveru.
├─ L1: Smerovanie k politike (Claude / Qwen)
├─ L2: Vyhľadávanie histórie úverov (pgvector + BM25)
├─ L3A: Päť kontrolných brán (PASSAR)
├─ L3B: Kryptografické záväzky (Ed25519)
└─ PAUSE: Čakanie na ľudský podpis vedúceho hotela (ANNEX III)
   └─ Po podpise: L4 spustí rozhodovací workflow
```

---

## 3. Nezaměnitelná auditná stopa (Článok 12)

### agentacct — Systém pracovných potvrdení
Každý krok genruje **nedostupný pracovný účet** (Work Receipt) s:
- Jednoznačný identifikátor rozhodnutia
- SHA-256 heš záväzku
- Ed25519 digitálny podpis kľúča
- Časová pečiatka (mikrosekúndy)

### AP2 Ledger — Merkleov DAG
Všetky pracovné účty sú uložené v **lokálnom, nezmeniteľnom, kryptograficky overenom ledgera**:

```
Genesis (2026-09-01 00:00:00)
├─ Decision #1 (hotel_credit_001) — merkle_hash: abc123
├─ Decision #2 (glass_check_001) — merkle_hash: def456
├─ Decision #3 (school_access_001) — merkle_hash: ghi789
└─ ... 2,247 rozhodnutí vrátane integrálného dedičstva
```

### Regulatorná overovateľnosť
Každé rozhodnutie je **verejne overiteľné** pomocou príkazov:
```bash
smaos-cli ledger verify sha256:abc123
# Výstup: ✓ UNBROKEN CHAIN, všetky predchodcovia overení
```

---

## 4. Tri pilotné projekty v kraji

### Pilotný projekt 1: Hotelnictvo a lázeňství
- **Prípad:** Automatické hodnotenie úverov pre hostiteľov
- **Regulácia:** Annex III (vysokoriziková kategória)
- **Chrániči:** L3B pozastavenie, ľudský podpis, auditná stopa
- **Spustenie:** 1. november 2026
- **Očakávané rozhodnutia:** 100+ v prvom mesiaci

### Pilotný projekt 2: Sklářský priemysel
- **Prípad:** Overenie CAD výrobných plánov bez úniku duševného vlastníctva
- **Regulácia:** Annex I (suverénna kontrola výroby)
- **Chrániči:** Egress firewall, kryptografické záväzky, lokálne spracovanie
- **Spustenie:** 1. november 2026
- **Očakávané rozhodnutia:** 50+ v prvom mesiaci

### Pilotný projekt 3: Školstvo
- **Prípad:** Správa prístupu do škôl s priesvitným auditom
- **Regulácia:** GDPR + lokálne školské predpisy
- **Chrániči:** Biometrické kontroly s consent systémom, auditná záznama
- **Spustenie:** 1. november 2026
- **Očakávané rozhodnutia:** 2000+ v prvom mesiaci

---

## 5. Súlad s právnymi predpismi

| Zákon | Podpora | Dôkaz |
|-------|---------|-------|
| **Nařízení EU 2024/1689 (AI Act)** | ✅ Články 5, 8, 11-15 | L3 kontrolné brány, L8 auditná stopa |
| **GDPR (Články 5, 32)** | ✅ Prívies + Integrity | Kryptografické podpisy, lokálne uloženie |
| **NIS2 Direktíva** | ✅ Bezpečnosť + incident reporting | HSM recovery playbook, DPA notifikácia |
| **ČR Zákon č. 110/2019 Sb.** | ✅ Osobné údaje | AP2 ledger, immutability proof |

---

## 6. Časový plán

| Dátum | Miľník | Stav |
|-------|--------|------|
| **1. septembra 2026** | Systém pripravený na KARP | ✅ HOTOVO |
| **16. septembra 2026** | Podanie KARP voucher | ⏳ ĎALŠÍ |
| **1. novembra 2026** | Spustenie 3 pilotov | 🚀 CIEĽ |
| **2. decembra 2027** | Annex III deadline | 📅 NA CESTE |
| **2. augusta 2028** | Annex I deadline | 📅 NA CESTE |

---

## 7. Technické špecifikácie

**Infraštruktúra:**
- Lokálne spracovanie (bez cloudu)
- PostgreSQL + pgvector (hybrid vyhľadávanie)
- 637 jednotkových testov (100% passar)
- 0 chýb na 100 riadkov kódu

**Kryptografia:**
- Ed25519 (PQC-ready)
- SHA-256 (NIST Standard)
- Merkle-DAG (Bitcoin-inspired)

**Kapacita:**
- 39,3 tokenov za sekundu (RTX 4060)
- <100 ms latencia dotazu
- Podpora až 64 súbežných agentov

---

## 8. Očakávania a ďalšie kroky

Systém SMAOS je **pripravený na vstup do Národného regulačného sandboxu** k 2. septembru 2027 (po ukončení fázy 1 a úspešného spustenia pilotných projektov).

Prosíme ÚOOÚ o:
1. **Potvrdenie technickej dokumentácie** (do 30. septembra 2026)
2. **Predbežnú orientáciu na Annex III** (do 31. októbra 2026)
3. **Registráciu v EU Database** (do 30. novembra 2026)

---

## Kontakt

**Projekt Vedúci:** Andrei Leukhin  
**Email:** andrejlo123@gmail.com  
**Telefón:** +420 721 XXX XXX  
**Podnikateľ:** Ostrov micro, s.r.o.  
**DIČ:** CZ XXXXXXXX XXX

S úctou,

_Andrei Leukhin_  
_Zakladateľ & Inžinier_  
_Ostrov micro, s.r.o._

---

**Prílohy:**
- A: Technické špecifikácie (ARCHITECTURE.md)
- B: Audit Report (COMPREHENSIVE_AUDIT_REPORT_SEP1_2026.md)
- C: Kryptografické dôkazy (7 proof artifacts)
- D: HSM Recovery Playbook (HSM_RECOVERY_PLAYBOOK.md)
