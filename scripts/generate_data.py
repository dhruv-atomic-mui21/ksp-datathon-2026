import os
import sqlite3
import random
from datetime import datetime, timedelta

def run_data_generator():
    db_path = "ksp_crime.db"
    
    # If database file exists, remove it to generate a fresh one
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Reading and executing db_schema.sql...")
    schema_path = os.path.join("scripts", "db_schema.sql")
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    cursor.executescript(schema_sql)
    
    # ----------------------------------------------------
    # 1. Populate Core Lookup Tables
    # ----------------------------------------------------
    print("Populating lookup tables...")
    
    # State
    cursor.execute("INSERT INTO State (StateID, StateName, NationalityID, Active) VALUES (1, 'Karnataka', 1, 1)")
    
    # Districts (Karnataka SCBR District weights calibration)
    districts = [
        (1, "Bengaluru City", 1, 1),
        (2, "Mysuru", 1, 1),
        (3, "Belagavi", 1, 1),
        (4, "Kalaburagi", 1, 1),
        (5, "Hubballi-Dharwad City", 1, 1),
        (6, "Mangaluru City", 1, 1),
        (7, "Davanagere", 1, 1),
        (8, "Shivamogga", 1, 1),
        (9, "Tumakuru", 1, 1),
        (10, "Vijayapura", 1, 1),
        (11, "Udupi", 1, 1),
        (12, "Dakshina Kannada", 1, 1),
        (13, "Uttara Kannada", 1, 1),
        (14, "Kodagu", 1, 1),
        (15, "Hassan", 1, 1)
    ]
    cursor.executemany("INSERT INTO District (DistrictID, DistrictName, StateID, Active) VALUES (?, ?, ?, ?)", districts)
    
    # UnitType
    unit_types = [
        (1, "Police Station", "City/District", 3, 1),
        (2, "Circle Office", "Sub-Division", 2, 1),
        (3, "District HQ", "District", 1, 1)
    ]
    cursor.executemany("INSERT INTO UnitType (UnitTypeID, UnitTypeName, CityDistState, Hierarchy, Active) VALUES (?, ?, ?, ?, ?)", unit_types)
    
    # Units (Police Stations for each district)
    # We will create 2-3 stations per district
    units = []
    unit_id = 1
    station_names = ["Town PS", "Traffic PS", "Cyber Crime PS", "Rural PS"]
    for dist_id, dist_name in [(d[0], d[1]) for d in districts]:
        # Add stations
        for i, s_name in enumerate(station_names[:3]):
            units.append((unit_id, f"{dist_name} {s_name}", 1, None, 1, 1, dist_id, 1))
            unit_id += 1
    cursor.executemany("INSERT INTO Unit (UnitID, UnitName, TypeID, ParentUnit, NationalityID, StateID, DistrictID, Active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", units)
    
    # Ranks
    ranks = [
        (1, "Constable", 5, 1),
        (2, "Head Constable", 4, 1),
        (3, "Assistant Sub-Inspector (ASI)", 3, 1),
        (4, "Sub-Inspector (PSI)", 2, 1),
        (5, "Inspector (PI)", 1, 1)
    ]
    cursor.executemany("INSERT INTO Rank (RankID, RankName, Hierarchy, Active) VALUES (?, ?, ?, ?)", ranks)
    
    # Designations
    designations = [
        (1, "Writer", 1, 1),
        (2, "Beat Officer", 1, 2),
        (3, "Investigating Officer (IO)", 1, 3),
        (4, "Station House Officer (SHO)", 1, 4)
    ]
    cursor.executemany("INSERT INTO Designation (DesignationID, DesignationName, Active, SortOrder) VALUES (?, ?, ?, ?)", designations)
    
    # Employees (Officers / Police personnel)
    # We will create about 100 employees
    employees = []
    first_names = ["Basavaraj", "Siddappa", "Mallikarjun", "Nagaraja", "Shivappa", "Girish", "Manjunath", "Ramesh", "Suresh", "Kumar", "Somashekar", "Prakash", "Satish", "Anand", "Vinay", "Mohammed", "Imran", "Prashanth", "Kiran"]
    for emp_id in range(1, 101):
        dist_id = random.randint(1, 15)
        # Filter units in this district
        dist_units = [u[0] for u in units if u[6] == dist_id]
        unit_id = random.choice(dist_units) if dist_units else 1
        rank_id = random.choices([1, 2, 3, 4, 5], weights=[0.4, 0.3, 0.15, 0.1, 0.05])[0]
        des_id = random.choices([1, 2, 3, 4], weights=[0.2, 0.4, 0.3, 0.1])[0]
        kgid = f"KSP{datetime.now().year}{10000 + emp_id}"
        fname = random.choice(first_names) + f" {chr(65 + random.randint(0, 25))}."
        dob = (datetime.now() - timedelta(days=random.randint(22*365, 58*365))).strftime("%Y-%m-%d")
        app_date = (datetime.now() - timedelta(days=random.randint(1*365, 20*365))).strftime("%Y-%m-%d")
        employees.append((emp_id, dist_id, unit_id, rank_id, des_id, kgid, fname, dob, 1 if random.random() > 0.1 else 2, random.randint(1, 4), 0, app_date))
    cursor.executemany("INSERT INTO Employee (EmployeeID, DistrictID, UnitID, RankID, DesignationID, KGID, FirstName, EmployeeDOB, GenderID, BloodGroupID, PhysicallyChallenged, AppointmentDate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", employees)
    
    # CaseCategory
    categories = [(1, "FIR"), (2, "UDR"), (3, "PAR"), (4, "Zero FIR")]
    cursor.executemany("INSERT INTO CaseCategory (CaseCategoryID, LookupValue) VALUES (?, ?)", categories)
    
    # GravityOffence
    gravity = [(1, "Heinous"), (2, "Non-Heinous")]
    cursor.executemany("INSERT INTO GravityOffence (GravityOffenceID, LookupValue) VALUES (?, ?)", gravity)
    
    # CaseStatusMaster
    statuses = [(1, "Under Investigation"), (2, "Charge Sheeted"), (3, "Closed - False Case"), (4, "Closed - Undetected"), (5, "Closed - Action Abated")]
    cursor.executemany("INSERT INTO CaseStatusMaster (CaseStatusID, CaseStatusName) VALUES (?, ?)", statuses)
    
    # Courts
    courts = []
    court_id = 1
    for dist_id, dist_name in [(d[0], d[1]) for d in districts]:
        courts.append((court_id, f"JMFC Court, {dist_name}", dist_id, 1, 1))
        court_id += 1
        courts.append((court_id, f"District & Sessions Court, {dist_name}", dist_id, 1, 1))
        court_id += 1
    cursor.executemany("INSERT INTO Court (CourtID, CourtName, DistrictID, StateID, Active) VALUES (?, ?, ?, ?, ?)", courts)
    
    # CrimeHead & CrimeSubHead
    crime_heads = [
        (1, "Crimes Against Body", 1),
        (2, "Crimes Against Property", 1),
        (3, "Economic Offences", 1),
        (4, "Crimes Against Women", 1),
        (5, "Special & Local Laws (SLL)", 1),
        (6, "UDR / Accidental Deaths", 1)
    ]
    cursor.executemany("INSERT INTO CrimeHead (CrimeHeadID, CrimeGroupName, Active) VALUES (?, ?, ?)", crime_heads)
    
    crime_sub_heads = [
        (1, 1, "Murder", 1),
        (2, 1, "Attempt to Murder", 2),
        (3, 1, "Grievous Hurt", 3),
        (4, 1, "Kidnapping & Abduction", 4),
        (5, 2, "Dacoity", 1),
        (6, 2, "Robbery", 2),
        (7, 2, "House Break-in & Theft (Burglary)", 3),
        (8, 2, "Ordinary Theft", 4),
        (9, 3, "Cheating & Corporate Fraud", 1),
        (10, 3, "Cyber Crime (IT Act)", 2),
        (11, 4, "Rape", 1),
        (12, 4, "Dowry Harassment (498A)", 2),
        (13, 4, "Outraging Modesty of Women", 3),
        (14, 5, "NDPS Act Offences", 1),
        (15, 5, "Excise Act Offences (Illegal Liquor)", 2),
        (16, 5, "Gambling / Karnataka Police Act", 3),
        (17, 6, "Suspicious / Unnatural Death", 1)
    ]
    cursor.executemany("INSERT INTO CrimeSubHead (CrimeSubHeadID, CrimeHeadID, CrimeHeadName, SeqID) VALUES (?, ?, ?, ?)", crime_sub_heads)
    
    # CasteMaster
    castes = [(1, "Lingayat"), (2, "Vokkaliga"), (3, "Kuruba"), (4, "Ediga"), (5, "Madiga"), (6, "Bovi"), (7, "Lambani"), (8, "Brahman"), (9, "General/Unspecified")]
    cursor.executemany("INSERT INTO CasteMaster (caste_master_id, caste_master_name) VALUES (?, ?)", castes)
    
    # ReligionMaster
    religions = [(1, "Hindu"), (2, "Muslim"), (3, "Christian"), (4, "Jain"), (5, "Buddhist"), (6, "Sikh")]
    cursor.executemany("INSERT INTO ReligionMaster (ReligionID, ReligionName) VALUES (?, ?)", religions)
    
    # OccupationMaster
    occupations = [(1, "Farmer"), (2, "Software Engineer"), (3, "Daily Wage Laborer"), (4, "Merchant/Shopkeeper"), (5, "Driver"), (6, "Unemployed"), (7, "Government Employee"), (8, "Student"), (9, "Housewife")]
    cursor.executemany("INSERT INTO OccupationMaster (OccupationID, OccupationName) VALUES (?, ?)", occupations)
    
    # Acts & Sections
    acts = [
        ("IPC", "Indian Penal Code, 1860", "IPC", 1),
        ("BNS", "Bharatiya Nyaya Sanhita, 2023", "BNS", 1),
        ("NDPS", "Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS", 1),
        ("Excise", "Karnataka Excise Act, 1965", "Excise", 1),
        ("KPAct", "Karnataka Police Act, 1963", "KPAct", 1),
        ("ITAct", "Information Technology Act, 2000", "ITAct", 1)
    ]
    cursor.executemany("INSERT INTO Act (ActCode, ActDescription, ShortName, Active) VALUES (?, ?, ?, ?)", acts)
    
    sections = [
        # IPC Sections
        ("IPC", "302", "Punishment for murder", 1),
        ("IPC", "307", "Attempt to murder", 1),
        ("IPC", "324", "Voluntarily causing hurt by dangerous weapons", 1),
        ("IPC", "379", "Punishment for theft", 1),
        ("IPC", "380", "Theft in dwelling house, etc.", 1),
        ("IPC", "392", "Punishment for robbery", 1),
        ("IPC", "395", "Punishment for dacoity", 1),
        ("IPC", "420", "Cheating and dishonestly inducing delivery of property", 1),
        ("IPC", "376", "Punishment for sexual assault / rape", 1),
        ("IPC", "498A", "Husband or relative of husband of a woman subjecting her to cruelty", 1),
        ("IPC", "174", "Unnatural death inquiry (UDR)", 1),
        # BNS equivalents
        ("BNS", "103", "Murder", 1),
        ("BNS", "109", "Attempt to murder", 1),
        ("BNS", "303", "Theft", 1),
        ("BNS", "309", "Robbery", 1),
        ("BNS", "318", "Cheating", 1),
        ("BNS", "64", "Rape", 1),
        # NDPS
        ("NDPS", "20", "Punishment for contravention in relation to cannabis plant and cannabis", 1),
        ("NDPS", "22", "Punishment for contravention in relation to psychotropic substances", 1),
        # Excise
        ("Excise", "32", "Penalty for illegal import, export, transport, manufacture, possession", 1),
        # KPAct
        ("KPAct", "78", "Penalty for opening, keeping or using gaming house", 1),
        ("KPAct", "92", "Punishment for certain street offences and nuisance", 1),
        # ITAct
        ("ITAct", "66D", "Punishment for cheating by personation by using computer resource", 1),
        ("ITAct", "66E", "Punishment for violating privacy", 1)
    ]
    cursor.executemany("INSERT INTO Section (ActCode, SectionCode, SectionDescription, Active) VALUES (?, ?, ?, ?)", sections)
    
    # CrimeHeadActSection
    ch_sections = [
        (1, "IPC", "302"), (1, "BNS", "103"), # Murder
        (2, "IPC", "307"), (2, "BNS", "109"), # Attempt to Murder
        (3, "IPC", "324"), # Grievous Hurt
        (5, "IPC", "395"), # Dacoity
        (6, "IPC", "392"), (6, "BNS", "309"), # Robbery
        (7, "IPC", "380"), # Burglary
        (8, "IPC", "379"), (8, "BNS", "303"), # Ordinary Theft
        (9, "IPC", "420"), (9, "BNS", "318"), # Cheating
        (10, "ITAct", "66D"), # Cyber Crime
        (11, "IPC", "376"), (11, "BNS", "64"), # Rape
        (12, "IPC", "498A"), # 498A
        (14, "NDPS", "20"), (14, "NDPS", "22"), # NDPS
        (15, "Excise", "32"), # Excise
        (16, "KPAct", "78"), (16, "KPAct", "92"), # KP/Gambling
        (17, "IPC", "174") # UDR
    ]
    cursor.executemany("INSERT INTO CrimeHeadActSection (CrimeHeadID, ActCode, SectionCode) VALUES (?, ?, ?)", ch_sections)
    
    conn.commit()
    
    # ----------------------------------------------------
    # 2. Setup Calibration Weights & Constants
    # ----------------------------------------------------
    
    # District weights: Bengaluru City has ~30%, rest distributed
    dist_weights = {
        1: 0.35,  # Bengaluru City
        2: 0.08,  # Mysuru
        3: 0.08,  # Belagavi
        4: 0.07,  # Kalaburagi
        5: 0.06,  # Hubballi-Dharwad City
        6: 0.06,  # Mangaluru City
        7: 0.05,  # Davanagere
        8: 0.04,  # Shivamogga
        9: 0.04,  # Tumakuru
        10: 0.04, # Vijayapura
        11: 0.03, # Udupi
        12: 0.03, # Dakshina Kannada
        13: 0.03, # Uttara Kannada
        14: 0.02, # Kodagu
        15: 0.02  # Hassan
    }
    
    # Sub-head weights (Crime category distribution)
    subhead_weights = {
        1: 0.04,   # Murder
        2: 0.05,   # Attempt to Murder
        3: 0.12,   # Grievous Hurt
        4: 0.04,   # Kidnapping
        5: 0.02,   # Dacoity
        6: 0.06,   # Robbery
        7: 0.15,   # Burglary
        8: 0.20,   # Ordinary Theft
        9: 0.08,   # Cheating
        10: 0.06,  # Cybercrime
        11: 0.03,  # Rape
        12: 0.06,  # Dowry Harassment
        13: 0.04,  # Outraging modesty
        14: 0.02,  # NDPS
        15: 0.02,  # Excise
        16: 0.02,  # Gambling/Nuisance
        17: 0.03   # UDR
    }
    
    # ----------------------------------------------------
    # 3. Inject Repeat Offenders & Criminal Network Seed Data
    # ----------------------------------------------------
    print("Seeding repeat offender pools & network rings...")
    
    # 30 repeat offender profiles
    repeat_offenders_pool = [
        {
            "name": "Kariya alias Ramesh", "age": 28, "gender": 1, 
            "phone": "9845012345", "address": "Slum Quarters, Majestic, Bengaluru",
            "bank_account": "1009845023", "mo": "Targeting locked independent houses during midnight, breaking locks with iron rod.",
            "sub_heads": [7, 8], # Burglary, Ordinary Theft
            "district": 1
        },
        {
            "name": "Bullet Manja", "age": 32, "gender": 1, 
            "phone": "9900112233", "address": "Subash Nagar, Mandya",
            "bank_account": "3044091211", "mo": "Stealing Royal Enfield motorcycles parked near railway stations using master keys.",
            "sub_heads": [8], # Ordinary Theft
            "district": 1
        },
        {
            "name": "Cyber Saleem", "age": 25, "gender": 1, 
            "phone": "9742098765", "address": "Bhatkal, Uttara Kannada",
            "bank_account": "9008127392", "mo": "Posing as bank manager, requesting OTP for KYC updates, withdrawing funds via e-wallets.",
            "sub_heads": [9, 10], # Cheating, Cybercrime
            "district": 1
        },
        {
            "name": "Siddaraju", "age": 41, "gender": 1, 
            "phone": "9448099887", "address": "Gokulam, Mysuru",
            "bank_account": "2201928374", "mo": "Grievous assault following drunken brawls over land boundaries.",
            "sub_heads": [3], # Grievous Hurt
            "district": 2
        },
        {
            "name": "Lady Don Shobha", "age": 35, "gender": 2, 
            "phone": "9535002233", "address": "Nehru Nagar, Belagavi",
            "bank_account": "4401827364", "mo": "Extortion of local merchants by threatening physical harm and damaging shops.",
            "sub_heads": [6], # Robbery/Extortion
            "district": 3
        }
    ]
    # Add minor repeat offenders
    for r_idx in range(len(repeat_offenders_pool) + 1, 26):
        fname = random.choice(["Gunda", "Appu", "Manja", "Suri", "Naga", "Chinna", "Shiva", "Ravi", "Jagga", "Sena"])
        lname = random.choice(["Gowda", "Patil", "Naik", "Shetty", "Rao", "Hegde", "Bhat", "Prasad"])
        repeat_offenders_pool.append({
            "name": f"{fname} alias {lname}",
            "age": random.randint(22, 45),
            "gender": 1,
            "phone": f"9{random.randint(100000000, 999999999)}",
            "address": f"{random.randint(10, 200)}, 4th Cross, Katriguppe, Bengaluru",
            "bank_account": f"300{random.randint(1000000, 9999999)}",
            "mo": "Snatching gold chains from elderly women walking alone in residential lanes during morning hours.",
            "sub_heads": [6, 8],
            "district": random.choice([1, 2, 3, 5, 6])
        })

    # Coordinated Crime Ring: 4 members operating together in different groups
    crime_ring_members = [
        {"name": "Girish B.", "age": 29, "gender": 1, "phone": "9008811223", "address": "Vyalikaval, Bengaluru", "bank_account": "1009008811"},
        {"name": "Kiran Kumar", "age": 27, "gender": 1, "phone": "9008811223", "address": "Vyalikaval, Bengaluru", "bank_account": "1009008811"}, # Shares phone & address!
        {"name": "Naveen Prasad", "age": 31, "gender": 1, "phone": "9008811224", "address": "Vyalikaval, Bengaluru", "bank_account": "1009008812"},
        {"name": "Vijay Patil", "age": 30, "gender": 1, "phone": "9008811224", "address": "Vyalikaval, Bengaluru", "bank_account": "1009008812"} # Shares phone & bank account with Naveen!
    ]
    
    # ----------------------------------------------------
    # 4. Generate Main Row-Level Dataset (500 Cases)
    # ----------------------------------------------------
    print("Generating 500 cases...")
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 6, 30)
    total_days = (end_date - start_date).days
    
    case_id = 1
    accused_id = 1
    victim_id = 1
    complainant_id = 1
    arr_surr_id = 1
    cs_id = 1
    
    # Keep track of running serials for CrimeNo formatting
    # keyed by (unit_id, case_cat_id, year)
    running_serials = {}
    
    for case_idx in range(1, 551): # Generate 550 cases
        
        # 4.1 Temporal and Seasonal modifier
        # Random date
        day_offset = random.randint(0, total_days)
        crime_date = start_date + timedelta(days=day_offset)
        
        # Crime Category and Sub-head selection
        sub_head_id = random.choices(list(subhead_weights.keys()), weights=list(subhead_weights.values()))[0]
        sub_head_info = [sh for sh in crime_sub_heads if sh[0] == sub_head_id][0]
        major_head_id = sub_head_info[1]
        
        # Seasonal calibration check
        # April (4) and May (5) have +35% body & property crimes. If random selection falls outside, adjust date
        if major_head_id in [1, 2] and crime_date.month not in [4, 5] and random.random() < 0.25:
            # Shift date to April or May of the same year
            try:
                crime_date = crime_date.replace(month=random.choice([4, 5]))
            except ValueError:
                # April only has 30 days. Scale day to 30.
                crime_date = crime_date.replace(day=30, month=random.choice([4, 5]))
        # Theft/Property crimes spike in December (12)
        if sub_head_id in [7, 8] and crime_date.month != 12 and random.random() < 0.20:
            try:
                crime_date = crime_date.replace(month=12)
            except ValueError:
                crime_date = crime_date.replace(day=30, month=12)
            
        year = crime_date.year
        
        # 4.2 District & Police Station selection
        dist_id = random.choices(list(dist_weights.keys()), weights=list(dist_weights.values()))[0]
        dist_name = [d[1] for d in districts if d[0] == dist_id][0]
        
        # Get units for this district
        dist_units = [u[0] for u in units if u[6] == dist_id]
        unit_id = random.choice(dist_units) if dist_units else 1
        
        # Injected Pattern: Geospatial & Temporal Burglary/Theft Hotspot in Majestic (Bengaluru City)
        # Cluster of 45 vehicle thefts (sub_head 8) in unit 1 or 2 (Majestic/Indiranagar) in Q4 2025
        is_hotspot_case = False
        if case_idx <= 45:
            is_hotspot_case = True
            dist_id = 1  # Bengaluru City
            dist_name = "Bengaluru City"
            unit_id = 1  # Indiranagar/Majestic Town Station
            sub_head_id = 8  # Ordinary Theft
            sub_head_info = [sh for sh in crime_sub_heads if sh[0] == sub_head_id][0]
            major_head_id = sub_head_info[1]
            # October - December 2025
            crime_date = datetime(2025, random.choice([10, 11, 12]), random.randint(1, 28))
            year = 2025
            
        # 4.3 Crime Category (FIR, UDR, etc.)
        if sub_head_id == 17:
            case_cat_id = 2  # UDR
        else:
            case_cat_id = random.choices([1, 4], weights=[0.95, 0.05])[0]  # FIR or Zero FIR
            
        # 4.4 Formatting CrimeNo and CaseNo according to official specification
        # format: 1 digit Category + 4 digit District + 4 digit Station + 4 digit Year + 5 digit Serial
        serial_key = (unit_id, case_cat_id, year)
        running_serials[serial_key] = running_serials.get(serial_key, 0) + 1
        serial_str = f"{running_serials[serial_key]:05d}"
        
        crime_no = f"{case_cat_id}{dist_id:04d}{unit_id:04d}{year}{serial_str}"
        case_no = f"{year}{serial_str}"
        
        # 4.5 Geolocation
        # Bengaluru City center lat: 12.9716, long: 77.5946
        # Other districts mapped outward
        if is_hotspot_case:
            # Highly concentrated around Majestic bus stand (12.976, 77.573)
            latitude = round(12.9763 + random.uniform(-0.005, 0.005), 6)
            longitude = round(77.5735 + random.uniform(-0.005, 0.005), 6)
        else:
            # Baseline district geolocation
            lat_base = 12.9716 + (dist_id - 1)*0.15
            lon_base = 77.5946 + (dist_id - 1)*0.05
            latitude = round(lat_base + random.uniform(-0.1, 0.1), 6)
            longitude = round(lon_base + random.uniform(-0.1, 0.1), 6)
            
        # 4.6 Case Status and Gravity
        case_status_id = random.choices([1, 2, 3, 4], weights=[0.40, 0.45, 0.08, 0.07])[0]
        
        # Heinous offece criteria
        is_heinous = 2  # default Non-Heinous
        if sub_head_id in [1, 2, 5, 6, 11]:  # Murder, Attempt, Dacoity, Robbery, Rape
            is_heinous = 1  # Heinous
            
        # Select court
        dist_courts = [c[0] for c in courts if c[2] == dist_id]
        court_id = random.choice(dist_courts) if dist_courts else 1
        
        # Select IO (Investigating Officer)
        unit_emps = [e[0] for e in employees if e[2] == unit_id]
        io_id = random.choice(unit_emps) if unit_emps else random.randint(1, 100)
        
        # Brief facts and timestamps
        inc_from = datetime.combine(crime_date, datetime.min.time()) + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
        inc_to = inc_from + timedelta(hours=random.randint(0, 4))
        info_recv = inc_to + timedelta(hours=random.randint(1, 24))
        
        facts = f"On the date {inc_from.strftime('%d-%m-%Y')}, the incident regarding {sub_head_info[2]} took place at jurisdiction of {dist_name}. "
        if sub_head_id == 8:
            facts += "A vehicle/gold chain was stolen by unknown person. Complainant registered FIR for necessary action."
        elif sub_head_id == 7:
            facts += "Unknown offenders gained entry into locked house by breaking front door lock and decamped with gold ornaments and cash."
        elif sub_head_id == 1:
            facts += "A dispute broke out between parties leading to physical altercation and murder. Deceased was stabbed with sharp weapon."
        elif sub_head_id == 10:
            facts += "Victim received a call from cyber fraudster posing as bank official and lost money via unauthorized transaction."
        else:
            facts += "Case registered. Detailed investigation conducted by the IO."
            
        # Injected Pattern: Anomalies
        # Anomaly 1: Illiterate elderly farmer (72 yo) committing high-tech cybercrime in Kodagu
        is_anomaly_case = False
        if case_idx == 499:
            is_anomaly_case = True
            dist_id = 14  # Kodagu
            unit_id = random.choice([u[0] for u in units if u[6] == 14])
            sub_head_id = 10  # Cyber Crime
            sub_head_info = [sh for sh in crime_sub_heads if sh[0] == sub_head_id][0]
            major_head_id = sub_head_info[1]
            facts = "ANOMALOUS INCIDENT: High-tech cryptocurrency phishing scam reported in rural coffee plantation area. Financial transaction traced to overseas account."
            
        # Anomaly 2: Murder in Bengaluru City with weird MO
        if case_idx == 500:
            is_anomaly_case = True
            dist_id = 1  # Bengaluru City
            sub_head_id = 1  # Murder
            sub_head_info = [sh for sh in crime_sub_heads if sh[0] == sub_head_id][0]
            major_head_id = sub_head_info[1]
            facts = "ANOMALOUS INCIDENT: Accused used a trained venomous cobra to bite the victim while they were asleep in order to make it look like an accidental snakebite."
            
        # Insert CaseMaster record
        cursor.execute("""
            INSERT INTO CaseMaster (
                CaseMasterID, CrimeNo, CaseNo, CrimeRegisteredDate, PolicePersonID, PoliceStationID,
                CaseCategoryID, GravityOffenceID, CrimeMajorHeadID, CrimeMinorHeadID, CaseStatusID,
                CourtID, IncidentFromDate, IncidentToDate, InfoReceivedPSDate, latitude, longitude, BriefFacts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_id, crime_no, case_no, crime_date.strftime("%Y-%m-%d"), io_id, unit_id,
            case_cat_id, is_heinous, major_head_id, sub_head_id, case_status_id,
            court_id, inc_from.strftime("%Y-%m-%d %H:%M:%S"), inc_to.strftime("%Y-%m-%d %H:%M:%S"),
            info_recv.strftime("%Y-%m-%d %H:%M:%S"), latitude, longitude, facts
        ))
        
        # 4.7 Complainant Details (Socio-demographic correlations calibrated)
        c_name = random.choice(["Rao", "Shetty", "Patil", "Reddy", "Murthy", "Nair", "Das", "Achar"])
        c_fname = random.choice(["Nagaraj", "Ravi", "Subramanya", "Deepak", "Sandesh", "Pramod", "Karthik"])
        complainant_name = f"{c_fname} {c_name}"
        c_age = random.randint(25, 65)
        c_occ = random.choices([1, 2, 3, 4, 7], weights=[0.3, 0.2, 0.2, 0.2, 0.1])[0]
        c_rel = random.choices([1, 2, 3], weights=[0.85, 0.1, 0.05])[0]
        c_caste = random.randint(1, 9)
        c_gender = random.choices([1, 2], weights=[0.75, 0.25])[0]
        
        # Calibrate socio-demographic correlation:
        # Software engineers (occ 2) are complainants in cybercrime (sub_head 10)
        if sub_head_id == 10 and not is_anomaly_case:
            c_occ = 2  # Software Engineer
            c_age = random.randint(22, 35)
            
        cursor.execute("""
            INSERT INTO ComplainantDetails (
                ComplainantID, CaseMasterID, ComplainantName, AgeYear, OccupationID, ReligionID, CasteID, GenderID
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (complainant_id, case_id, complainant_name, c_age, c_occ, c_rel, c_caste, c_gender))
        complainant_id += 1
        
        # 4.8 Victim Details
        # UDR cases have deceased as victim. FIR cases might have victims or complainants as victims
        v_name = random.choice(["Manjula", "Gangamma", "Shanthamma", "Suma", "Latha", "Sunil", "Harish", "Guru"])
        v_lname = random.choice(["M.", "R.", "S.", "K.", "Gowda", "Naik", "Hegde"])
        victim_name = f"{v_name} {v_lname}"
        v_age = random.randint(5, 75)
        v_gender = random.choices([1, 2], weights=[0.5, 0.5])[0]
        v_police = "0"
        
        # Crimes against women (Rape/harassment) -> Female victim
        if sub_head_id in [11, 12, 13]:
            v_gender = 2
            v_age = random.randint(18, 45)
            
        cursor.execute("""
            INSERT INTO Victim (
                VictimMasterID, CaseMasterID, VictimName, AgeYear, GenderID, VictimPolice
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (victim_id, case_id, victim_name, v_age, v_gender, v_police))
        victim_id += 1
        
        # 4.9 Accused Details & Criminal Network Injections
        # UDR (Unnatural Death) has no accused usually
        if sub_head_id != 17:
            # Determine if this is a Repeat Offender case
            # 20% chance if burglary/theft/cybercrime
            is_repeat_offender_case = False
            selected_offender = None
            if sub_head_id in [7, 8, 9, 10] and random.random() < 0.25:
                # Find matching offenders
                possible_offenders = [o for o in repeat_offenders_pool if sub_head_id in o["sub_heads"]]
                if possible_offenders:
                    is_repeat_offender_case = True
                    selected_offender = random.choice(possible_offenders)
                    
            # Determine if this is a Coordinated Crime Ring case
            # Let's link 10 property cases (dacoity/robbery) to our Crime Ring
            is_ring_case = False
            if sub_head_id in [5, 6] and case_idx % 8 == 0:
                is_ring_case = True
                
            accused_count = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
            if is_ring_case:
                accused_count = random.randint(2, 3)
                
            for acc_idx in range(1, accused_count + 1):
                # Set default accused properties
                a_name = random.choice(["Raju", "Manju", "Shiva", "Satish", "Venkatesh", "Syed", "Prakash", "Kiran"]) + " " + random.choice(["K.", "R.", "M.", "Patil", "Gowda", "Bhatt", "Ali"])
                a_age = random.choices([
                    random.randint(18, 25), # High weight for property crime
                    random.randint(26, 40),
                    random.randint(41, 65)
                ], weights=[0.45, 0.40, 0.15])[0]
                a_gender = 1 if random.random() > 0.05 else 2
                phone = f"9{random.randint(100000000, 999999999)}"
                address = f"{random.randint(1, 100)}, Bangalore Rd, district HQ"
                bank_acc = f"500{random.randint(1000000, 9999999)}"
                
                # Calibrate socio-demographic correlation:
                # Young unemployed/wage laborers (age 18-25, occupation Daily wage/unemployed) linked to property crime (ordinary theft)
                # Handled via demographic distributions above
                
                if is_repeat_offender_case and acc_idx == 1:
                    a_name = selected_offender["name"]
                    a_age = selected_offender["age"]
                    a_gender = selected_offender["gender"]
                    phone = selected_offender["phone"]
                    address = selected_offender["address"]
                    bank_acc = selected_offender["bank_account"]
                    # Update facts with MO to show consistency
                    cursor.execute("UPDATE CaseMaster SET BriefFacts = BriefFacts || ' MO Note: ' || ? WHERE CaseMasterID = ?", (selected_offender["mo"], case_id))
                    
                elif is_ring_case:
                    # Select ring members
                    ring_member = crime_ring_members[(case_id + acc_idx) % 4]
                    a_name = ring_member["name"]
                    a_age = ring_member["age"]
                    a_gender = ring_member["gender"]
                    phone = ring_member["phone"]
                    address = ring_member["address"]
                    bank_acc = ring_member["bank_account"]
                    
                elif is_anomaly_case and case_idx == 499:
                    # Elderly illiterate farmer in Kodagu commits cybercrime
                    a_name = "Thimme Gowda"
                    a_age = 72
                    a_gender = 1
                    phone = "9448011223"
                    address = "Hutli Village, Somwarpet, Kodagu"
                    bank_acc = "1002003004"
                    
                cursor.execute("""
                    INSERT INTO Accused (
                        AccusedMasterID, CaseMasterID, AccusedName, AgeYear, GenderID, PersonID, PhoneNo, Address, BankAccountNo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (accused_id, case_id, a_name, a_age, a_gender, f"A{acc_idx}", phone, address, bank_acc))
                
                # 4.10 Arrest & Surrender details
                # If case status is "Charge Sheeted", most accused are arrested
                # If "Under Investigation", some are arrested
                should_arrest = False
                if case_status_id == 2:  # Charge Sheeted
                    should_arrest = True
                elif case_status_id == 1 and random.random() < 0.3:
                    should_arrest = True
                    
                if should_arrest:
                    arr_date = crime_date + timedelta(days=random.randint(1, 30))
                    cursor.execute("""
                        INSERT INTO ArrestSurrender (
                            ArrestSurrenderID, CaseMasterID, ArrestSurrenderTypeID, ArrestSurrenderDate,
                            ArrestSurrenderStateId, ArrestSurrenderDistrictId, PoliceStationID, IOID, CourtID,
                            AccusedMasterID, IsAccused, IsComplainantAccused
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
                    """, (arr_surr_id, case_id, random.choice([1, 2]), arr_date.strftime("%Y-%m-%d"), 1, dist_id, unit_id, io_id, court_id, accused_id))
                    
                    # Junction table record
                    cursor.execute("INSERT INTO inv_arrestsurrenderaccused (ArrestSurrenderID, AccusedMasterID) VALUES (?, ?)", (arr_surr_id, accused_id))
                    arr_surr_id += 1
                    
                accused_id += 1
                
        # 4.11 ActSectionAssociation
        # Find sections mapping to this CrimeSubHead
        ch_assocs = [chs for chs in ch_sections if chs[0] == sub_head_id]
        if not ch_assocs:
            # Default IPC 324
            ch_assocs = [(sub_head_id, "IPC", "324")]
            
        for order_idx, ch_a in enumerate(ch_assocs, 1):
            cursor.execute("""
                INSERT INTO ActSectionAssociation (
                    CaseMasterID, ActID, SectionID, ActOrderID, SectionOrderID
                ) VALUES (?, ?, ?, ?, ?)
            """, (case_id, ch_a[1], ch_a[2], 1, order_idx))
            
        # 4.12 Chargesheet Details (if case is charge sheeted)
        if case_status_id == 2:
            cs_date = crime_date + timedelta(days=random.randint(30, 90))
            cursor.execute("""
                INSERT INTO ChargesheetDetails (
                    CSID, CaseMasterID, csdate, cstype, PolicePersonID
                ) VALUES (?, ?, ?, ?, ?)
            """, (cs_id, case_id, cs_date.strftime("%Y-%m-%d %H:%M:%S"), 'A', io_id))
            cs_id += 1
            
        case_id += 1
        
    conn.commit()
    conn.close()
    print(f"Successfully generated {case_id-1} cases and saved to ksp_crime.db!")

if __name__ == "__main__":
    run_data_generator()
