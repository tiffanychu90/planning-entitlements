# PCTS Parser for notebooks folder
import dataclasses
import os
import re
import typing

#---------------------------------------------------------------------------------------#
## Zoning Parser
#---------------------------------------------------------------------------------------#
VALID_ZONE_CLASS = {
    "A1",
    "A2",
    "RA",
    "RE",
    "RE40",
    "RE20",
    "RE15",
    "RE11",
    "RE9",
    "RS",
    "R1",
    "R1F",
    "R1R",
    "R1H",
    "RU",
    "RZ2.5",
    "RZ3",
    "RZ4",
    "RW1",
    "R2",
    "RD1.5",
    "RD2",
    "RD3",
    "RD4",
    "RD5",
    "RD6",
    "RMP",
    "RW2",
    "R3",
    "RAS3",
    "R4",
    "RAS4",
    "R5",
    # Additional residential ones from master
    "R1R3",
    "R1H1",
    "R1V1",
    "R1V2",
    "R1V3",
    "CR",
    "C1",
    "C1.5",
    "C2",
    "C4",
    "C5",
    "CM",
    "MR1",
    "M1",
    "MR2",
    "M2",
    "M3",
    "P",
    "PB",
    # Additional parking ones from master
    "R1P",
    "R2P",
    "R3P",
    "R4P",
    "R5P",
    "RAP",
    "RSP",
    "OS",
    "GW",
    "PF",
    "FRWY",
    "SL",
    # Hybrid Industrial
    "HJ",
    "HR",
    "NI",
}

VALID_HEIGHT_DISTRICTS = {
    "1",
    "1L",
    "1VL",
    "1XL",
    "1SS",
    "2",
    "3",
    "4",
}

VALID_SUPPLEMENTAL_USE = {
    # Supplemental Use found in Table 2 or Zoning Code Article 3
    "O",
    "S",
    "G",
    "K",
    "CA",
    "MU",
    "FH",
    "SN",
    "HS",
    "RG",
    "RPD",
    "POD",
    "CDO",
    "NSO",
    "RFA",
    "MPR",
    "RIO",
    "HCR",
    "CPIO",
    "CUGU",
    "HPOZ",
    "SP",
    # Add more from their master table
    "NMU",
    # What is H? Comes up a lot.
    "H"
}

# Valid specific plans.
# TODO: handle Warner Center and USC zones specifically,
# since they don't match the pattern of the rest of the specific plans.
VALID_SPECIFIC_PLAN = {
    # Found in Zoning Code Article 2 and Sec 12.04 Zones-Districts-Symbols.
    "CEC",
    "CW",
    "GM",
    "OX",
    "PV",
    "WC",
    "ADP",
    "CCS",
    "CSA",
    "PKM",
    "LAX",
    "LASED",
    #"USC-1A",
    #"USC-1B",
    #"USC-2",
    #"USC-3",
    "PVSP",
    # Add more from their master table
    #"(WC)COLLEGE",
    #"(WC)COMMERCE",
    #"(WC)DOWNTOWN",
    #"(WC)NORTHVILLAGE",
    #"(WC)PARK",
    #"(WC)RIVER",
    #"(WC)TOPANGA",
    #"(WC)UPTOWN",
    "UV",
    "EC",
    "PPSP",
}

# Regex for qualified condition or tentative classifications
Q_T_RE = "(\(T\)|\[T\]|T|\(Q\)|\[Q\]|Q)?(\(T\)|\[T\]|T|\(Q\)|\[Q\]|Q)?"
# Specific plan
SPECIFIC_PLAN_RE = "(?:\(([A-Z]+)\))?"
# Zoning class
ZONING_CLASS_RE = "([A-Z0-9.]+)"
# Height district
HEIGHT_DISTRICT_RE = "([A-Z0-9]+)"
# Overlays
OVERLAY_RE = "((?:-[A-Z]+)*)"

# A regex for parsing a zoning string
FULL_ZONE_RE = re.compile(
    f"^{Q_T_RE}{SPECIFIC_PLAN_RE}{ZONING_CLASS_RE}{SPECIFIC_PLAN_RE}-{HEIGHT_DISTRICT_RE}{OVERLAY_RE}$"
)

# Zoning class only regex, for cases where height district and overlays may be missing
ZONE_ONLY_RE = re.compile(
    f"^{Q_T_RE}{SPECIFIC_PLAN_RE}{ZONING_CLASS_RE}{SPECIFIC_PLAN_RE}$"
)

# The different forms that the T/Q zoning prefixes may take.
T_OPTIONS = {"T", "(T)", "[T]"}
Q_OPTIONS = {"Q", "(Q)", "[Q]"}


@dataclasses.dataclass
class ZoningInfo:
    """
    A dataclass for parsing and storing parcel zoning info.
    The information is accessible as data attributes on the class instance.
    If the constructor is unable to parse the zoning string,
    a ValueError will be raised.

    References
    ==========

    https://planning.lacity.org/zoning/guide-current-zoning-string
    https://planning.lacity.org/odocument/eadcb225-a16b-4ce6-bc94-c915408c2b04/Zoning_Code_Summary.pdf
    """

    Q: bool = False
    T: bool = False
    zone_class: str = ""
    D: bool = False
    height_district: str = ""
    specific_plan: str = ""
    overlay: typing.List[str] = dataclasses.field(default_factory=list)

    def __init__(self, zoning_string: str):
        """
        Create a new ZoningInfo instance.
        
        Parameters
        ==========

        zoning_string: str
            The zoning string to be parsed.
        """
        try:
            self._parse_full(zoning_string)
        except ValueError:
            self._fallback(zoning_string)

    def _parse_full(self, zoning_string: str):
        matches = FULL_ZONE_RE.match(zoning_string.strip())
        if matches is None:
            raise ValueError(f"Couldn't parse zoning string {zoning_string}")
        groups = matches.groups()
        
        # Prefix
        if groups[0] in T_OPTIONS or groups[1] in T_OPTIONS:
            self.T = True
        
        if groups[0] in Q_OPTIONS or groups[1] in Q_OPTIONS:
            self.Q = True

        self.specific_plan = groups[2] or groups[4] or ""
        self.zone_class = groups[3] or ""
        height_district = groups[5] or ""
        if height_district[-1] == "D":
            self.D = True
            height_district = height_district[:-1]
        else:
            self.D = False
            self.height_district = height_district
        if groups[6]:
            self.overlay = groups[6].strip("-").split("-")
        else:
            self.overlay = []

        self._validate()

    def _validate(self):
        try:
            assert self.zone_class in VALID_ZONE_CLASS
            assert (
                self.height_district in VALID_HEIGHT_DISTRICTS or self.height_district
            )
            if self.overlay:
                assert all([o in VALID_SUPPLEMENTAL_USE for o in self.overlay])
            assert self.specific_plan in VALID_SPECIFIC_PLAN or self.specific_plan is ""
        except AssertionError:
            raise ValueError(f"Failed to validate")

    def _fallback(self, zoning_string: str):
        # Brute force the parts of the string, trying to assign them on a
        # best-effort basis.
        self.overlay = []
        parts = zoning_string.split("-")
        for part in parts:
            # Since the ZONE_ONLY_RE should also match height district or overlay
            # components, we match each part of the zoning string against that.
            # This allows us to check for Q/T and specific plan conditions.
            match = ZONE_ONLY_RE.match(part.strip())
            if not match:
                raise ValueError(f"Couldn't parse zoning string {zoning_string}")
            groups = match.groups()
            if groups[0] in T_OPTIONS or groups[1] in T_OPTIONS:
                self.T = True
            if groups[0] in Q_OPTIONS or groups[1] in Q_OPTIONS:
                self.Q = True
            for g in groups[2:]:
                if g is None:
                    continue
                if g in VALID_SPECIFIC_PLAN:
                    self.specific_plan = g
                elif g in VALID_ZONE_CLASS:
                    self.zone_class = g
                elif g in VALID_HEIGHT_DISTRICTS:
                    self.height_district = g
                    self.D = False
                elif g[:-1] in VALID_HEIGHT_DISTRICTS and g[-1] == "D":
                    self.D = True
                    self.height_district = g[:-1]
                elif g in VALID_SUPPLEMENTAL_USE:
                    self.overlay.append(g)
                else:
                    raise ValueError(
                        f"Couldn't parse zoning string {zoning_string}, component {g}"
                    )


#---------------------------------------------------------------------------------------#
## PCTS Parser
#---------------------------------------------------------------------------------------#
GENERAL_PCTS_RE = re.compile("([A-Z]+)-([0-9X]{4})-([0-9]+)((?:-[A-Z0-9]+)*)$")
MISSING_YEAR_RE = re.compile("([A-Z]+)-([0-9]+)((?:-[A-Z0-9]+)*)$")

VALID_PCTS_PREFIX = {
    'AA', 'ADM', 'APCC', 'APCE', 'APCH', 
    'APCNV', 'APCS', 'APCSV', 'APCW',
    'CHC', 'CPC', 'DIR', 'ENV', 'HPO', 
    'PAR', 'PS', 'TT', 'VTT', 'ZA'
}

@dataclasses.dataclass
class PCTSCaseNumber:
    """
    A dataclass for parsing and storing PCTS Case Number info.
    The information is accessible as data attributes on the class instance.
    If the constructor is unable to parse the pcts_case_string,
    a ValueError will be raised.

    References
    ==========

    https://planning.lacity.org/resources/prefix-suffix-report
    """
    prefix: str = ""
    suffix: typing.Optional[typing.List[str]] = None
    invalid_prefix: str = ""


    def __init__(self, pcts_case_string: str):
        try:
            self._general_pcts_parser(pcts_case_string)
        except ValueError:
            try:
                self._next_pcts_parser(pcts_case_string)
            except ValueError:
                pass


    def _general_pcts_parser(self, pcts_case_string: str):
        """
        Create a new PCTSCaseNumber instance.
        
        Parameters
        ==========

        pcts_case_string: str
            The PCTS case number string to be parsed.
        """
        matches = GENERAL_PCTS_RE.match(pcts_case_string.strip())
        if matches is None:
            raise ValueError("Couldn't parse PCTS string")
        
        groups = matches.groups()
        
        invalid_prefix = ""

        # Prefix
        if groups[0] in VALID_PCTS_PREFIX:
            prefix = groups[0]
        else:
            prefix = 'invalid'
            invalid_prefix = groups[0]
            
        self.prefix = prefix
        self.invalid_prefix = invalid_prefix

        # Suffix
        if groups[3]:
            self.suffix = groups[3].strip('-').split('-')
    

    def _next_pcts_parser(self, pcts_case_string: str):
        # Match where there is no year, but there is prefix, case ID, and suffix
        matches = MISSING_YEAR_RE.match(pcts_case_string.strip())
        
        if matches is None:
            raise ValueError(f"Coudln't parse PCTS string {pcts_case_string}")
        
        groups = matches.groups()
        
        invalid_prefix = ""

        # Prefix
        if groups[0] in VALID_PCTS_PREFIX:
            prefix = groups[0]
        else:
            prefix = 'invalid'
            invalid_prefix = groups[0]
        
        self.prefix = prefix
        self.invalid_prefix = invalid_prefix
    
        # Suffix
        if groups[2]:
            self.suffix = groups[2].strip('-').split('-')