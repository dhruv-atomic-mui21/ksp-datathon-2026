-- KSP Crime Database Schema (SQLite & Catalyst Data Store ZCQL-compatible)

-- Core Lookup Tables
CREATE TABLE State (
    StateID INTEGER PRIMARY KEY,
    StateName VARCHAR(100) NOT NULL,
    NationalityID INTEGER DEFAULT 1,
    Active INTEGER DEFAULT 1
);

CREATE TABLE District (
    DistrictID INTEGER PRIMARY KEY,
    DistrictName VARCHAR(100) NOT NULL,
    StateID INTEGER,
    Active INTEGER DEFAULT 1,
    FOREIGN KEY(StateID) REFERENCES State(StateID)
);

CREATE TABLE UnitType (
    UnitTypeID INTEGER PRIMARY KEY,
    UnitTypeName VARCHAR(100) NOT NULL,
    CityDistState VARCHAR(50),
    Hierarchy INTEGER,
    Active INTEGER DEFAULT 1
);

CREATE TABLE Unit (
    UnitID INTEGER PRIMARY KEY,
    UnitName VARCHAR(100) NOT NULL,
    TypeID INTEGER,
    ParentUnit INTEGER,
    NationalityID INTEGER DEFAULT 1,
    StateID INTEGER,
    DistrictID INTEGER,
    Active INTEGER DEFAULT 1,
    FOREIGN KEY(TypeID) REFERENCES UnitType(UnitTypeID),
    FOREIGN KEY(StateID) REFERENCES State(StateID),
    FOREIGN KEY(DistrictID) REFERENCES District(DistrictID)
);

CREATE TABLE Rank (
    RankID INTEGER PRIMARY KEY,
    RankName VARCHAR(100) NOT NULL,
    Hierarchy INTEGER,
    Active INTEGER DEFAULT 1
);

CREATE TABLE Designation (
    DesignationID INTEGER PRIMARY KEY,
    DesignationName VARCHAR(100) NOT NULL,
    Active INTEGER DEFAULT 1,
    SortOrder INTEGER
);

CREATE TABLE Employee (
    EmployeeID INTEGER PRIMARY KEY,
    DistrictID INTEGER,
    UnitID INTEGER,
    RankID INTEGER,
    DesignationID INTEGER,
    KGID VARCHAR(50) UNIQUE,
    FirstName VARCHAR(100),
    EmployeeDOB DATE,
    GenderID INTEGER,
    BloodGroupID INTEGER,
    PhysicallyChallenged INTEGER DEFAULT 0,
    AppointmentDate DATE,
    FOREIGN KEY(DistrictID) REFERENCES District(DistrictID),
    FOREIGN KEY(UnitID) REFERENCES Unit(UnitID),
    FOREIGN KEY(RankID) REFERENCES Rank(RankID),
    FOREIGN KEY(DesignationID) REFERENCES Designation(DesignationID)
);

CREATE TABLE CaseCategory (
    CaseCategoryID INTEGER PRIMARY KEY,
    LookupValue VARCHAR(50) NOT NULL
);

CREATE TABLE GravityOffence (
    GravityOffenceID INTEGER PRIMARY KEY,
    LookupValue VARCHAR(50) NOT NULL
);

CREATE TABLE CaseStatusMaster (
    CaseStatusID INTEGER PRIMARY KEY,
    CaseStatusName VARCHAR(50) NOT NULL
);

CREATE TABLE Court (
    CourtID INTEGER PRIMARY KEY,
    CourtName VARCHAR(150) NOT NULL,
    DistrictID INTEGER,
    StateID INTEGER,
    Active INTEGER DEFAULT 1,
    FOREIGN KEY(DistrictID) REFERENCES District(DistrictID),
    FOREIGN KEY(StateID) REFERENCES State(StateID)
);

CREATE TABLE CrimeHead (
    CrimeHeadID INTEGER PRIMARY KEY,
    CrimeGroupName VARCHAR(150) NOT NULL,
    Active INTEGER DEFAULT 1
);

CREATE TABLE CrimeSubHead (
    CrimeSubHeadID INTEGER PRIMARY KEY,
    CrimeHeadID INTEGER,
    CrimeHeadName VARCHAR(150) NOT NULL,
    SeqID INTEGER,
    FOREIGN KEY(CrimeHeadID) REFERENCES CrimeHead(CrimeHeadID)
);

CREATE TABLE CasteMaster (
    caste_master_id INTEGER PRIMARY KEY,
    caste_master_name VARCHAR(100) NOT NULL
);

CREATE TABLE ReligionMaster (
    ReligionID INTEGER PRIMARY KEY,
    ReligionName VARCHAR(100) NOT NULL
);

CREATE TABLE OccupationMaster (
    OccupationID INTEGER PRIMARY KEY,
    OccupationName VARCHAR(100) NOT NULL
);

-- Law & Offence Definitions
CREATE TABLE Act (
    ActCode VARCHAR(50) PRIMARY KEY,
    ActDescription VARCHAR(255),
    ShortName VARCHAR(100),
    Active INTEGER DEFAULT 1
);

CREATE TABLE Section (
    ActCode VARCHAR(50),
    SectionCode VARCHAR(50),
    SectionDescription TEXT,
    Active INTEGER DEFAULT 1,
    PRIMARY KEY (ActCode, SectionCode),
    FOREIGN KEY(ActCode) REFERENCES Act(ActCode)
);

CREATE TABLE CrimeHeadActSection (
    CrimeHeadID INTEGER,
    ActCode VARCHAR(50),
    SectionCode VARCHAR(50),
    FOREIGN KEY(CrimeHeadID) REFERENCES CrimeHead(CrimeHeadID),
    FOREIGN KEY(ActCode, SectionCode) REFERENCES Section(ActCode, SectionCode)
);

-- Case Master & Child Entities
CREATE TABLE CaseMaster (
    CaseMasterID INTEGER PRIMARY KEY,
    CrimeNo VARCHAR(50) UNIQUE,
    CaseNo VARCHAR(50),
    CrimeRegisteredDate DATE,
    PolicePersonID INTEGER,
    PoliceStationID INTEGER,
    CaseCategoryID INTEGER,
    GravityOffenceID INTEGER,
    CrimeMajorHeadID INTEGER,
    CrimeMinorHeadID INTEGER,
    CaseStatusID INTEGER,
    CourtID INTEGER,
    IncidentFromDate DATETIME,
    IncidentToDate DATETIME,
    InfoReceivedPSDate DATETIME,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    BriefFacts TEXT,
    FOREIGN KEY(PolicePersonID) REFERENCES Employee(EmployeeID),
    FOREIGN KEY(PoliceStationID) REFERENCES Unit(UnitID),
    FOREIGN KEY(CaseCategoryID) REFERENCES CaseCategory(CaseCategoryID),
    FOREIGN KEY(GravityOffenceID) REFERENCES GravityOffence(GravityOffenceID),
    FOREIGN KEY(CrimeMajorHeadID) REFERENCES CrimeHead(CrimeHeadID),
    FOREIGN KEY(CrimeMinorHeadID) REFERENCES CrimeSubHead(CrimeSubHeadID),
    FOREIGN KEY(CaseStatusID) REFERENCES CaseStatusMaster(CaseStatusID),
    FOREIGN KEY(CourtID) REFERENCES Court(CourtID)
);

CREATE TABLE ComplainantDetails (
    ComplainantID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER,
    ComplainantName VARCHAR(100),
    AgeYear INTEGER,
    OccupationID INTEGER,
    ReligionID INTEGER,
    CasteID INTEGER,
    GenderID INTEGER,
    FOREIGN KEY(CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY(OccupationID) REFERENCES OccupationMaster(OccupationID),
    FOREIGN KEY(ReligionID) REFERENCES ReligionMaster(ReligionID),
    FOREIGN KEY(CasteID) REFERENCES CasteMaster(caste_master_id)
);

CREATE TABLE ActSectionAssociation (
    CaseMasterID INTEGER,
    ActID VARCHAR(50),
    SectionID VARCHAR(50),
    ActOrderID INTEGER,
    SectionOrderID INTEGER,
    PRIMARY KEY (CaseMasterID, ActID, SectionID),
    FOREIGN KEY(CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY(ActID, SectionID) REFERENCES Section(ActCode, SectionCode)
);

CREATE TABLE Victim (
    VictimMasterID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER,
    VictimName VARCHAR(100),
    AgeYear INTEGER,
    GenderID INTEGER,
    VictimPolice VARCHAR(10), -- '1' for police victim, '0' else
    FOREIGN KEY(CaseMasterID) REFERENCES CaseMaster(CaseMasterID)
);

CREATE TABLE Accused (
    AccusedMasterID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER,
    AccusedName VARCHAR(100),
    AgeYear INTEGER,
    GenderID INTEGER,
    PersonID VARCHAR(20), -- 'A1', 'A2', etc.
    -- Added fields for network linking
    PhoneNo VARCHAR(20),
    Address VARCHAR(255),
    BankAccountNo VARCHAR(50),
    FOREIGN KEY(CaseMasterID) REFERENCES CaseMaster(CaseMasterID)
);

CREATE TABLE ArrestSurrender (
    ArrestSurrenderID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER,
    ArrestSurrenderTypeID INTEGER,
    ArrestSurrenderDate DATE,
    ArrestSurrenderStateId INTEGER,
    ArrestSurrenderDistrictId INTEGER,
    PoliceStationID INTEGER,
    IOID INTEGER,
    CourtID INTEGER,
    AccusedMasterID INTEGER,
    IsAccused INTEGER,
    IsComplainantAccused INTEGER,
    FOREIGN KEY(CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY(ArrestSurrenderStateId) REFERENCES State(StateID),
    FOREIGN KEY(ArrestSurrenderDistrictId) REFERENCES District(DistrictID),
    FOREIGN KEY(PoliceStationID) REFERENCES Unit(UnitID),
    FOREIGN KEY(IOID) REFERENCES Employee(EmployeeID),
    FOREIGN KEY(CourtID) REFERENCES Court(CourtID),
    FOREIGN KEY(AccusedMasterID) REFERENCES Accused(AccusedMasterID)
);

CREATE TABLE inv_arrestsurrenderaccused (
    ArrestSurrenderID INTEGER,
    AccusedMasterID INTEGER,
    PRIMARY KEY (ArrestSurrenderID, AccusedMasterID),
    FOREIGN KEY(ArrestSurrenderID) REFERENCES ArrestSurrender(ArrestSurrenderID),
    FOREIGN KEY(AccusedMasterID) REFERENCES Accused(AccusedMasterID)
);

CREATE TABLE ChargesheetDetails (
    CSID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER,
    csdate DATETIME,
    cstype CHAR(1), -- 'A', 'B', 'C'
    PolicePersonID INTEGER,
    FOREIGN KEY(CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY(PolicePersonID) REFERENCES Employee(EmployeeID)
);

-- Audit and Security Table (Essential for Governance & RBAC)
CREATE TABLE AuditLog (
    AuditLogID INTEGER PRIMARY KEY AUTOINCREMENT,
    UserEmail VARCHAR(150),
    UserRole VARCHAR(50),
    Action VARCHAR(100),
    QueryExecuted TEXT,
    Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
