# line_config.py

# 定義全港 MTR 路線的物理區間 (Physical Segments)
# 格式：{"路線代碼": [ (站A, 站B), (站B, 站C), ... ]}

MTR_SEGMENTS = {
    "TWL": [ # 荃灣綫
        ("CEN", "ADM"), ("ADM", "TST"), ("TST", "JOR"), ("JOR", "YMT"),
        ("YMT", "MOK"), ("MOK", "PRE"), ("PRE", "SSP"), ("SSP", "CSW"),
        ("CSW", "LCK"), ("LCK", "MEF"), ("MEF", "LAK"), ("LAK", "KWF"),
        ("KWF", "KWH"), ("KWH", "TWH"), ("TWH", "TSW")
    ],
    "ISL": [ # 港島綫
        ("KET", "HKU"), ("HKU", "SYP"), ("SYP", "SHW"), ("SHW", "CEN"),
        ("CEN", "ADM"), ("ADM", "WAC"), ("WAC", "CWB"), ("CWB", "TIH"),
        ("TIH", "FOH"), ("FOH", "NOP"), ("NOP", "QUB"), ("QUB", "TAK"),
        ("TAK", "SWH"), ("SWH", "SKW"), ("SKW", "HFC"), ("HFC", "CHW")
    ],
    "KTL": [ # 觀塘綫
        ("WHA", "HOM"), ("HOM", "YMT"), ("YMT", "MOK"), ("MOK", "PRE"),
        ("PRE", "KOT"), ("KOT", "LOF"), ("LOF", "WTS"), ("WTS", "CHH"),
        ("CHH", "KBD"), ("KBD", "NTK"), ("NTK", "KOW"), ("KOW", "LAT"),
        ("LAT", "YAT"), ("YAT", "TIK")
    ],
    "TKL": [ # 將軍澳綫 (含分支)
        ("NOP", "QUB"), ("QUB", "YAT"), ("YAT", "TIK"), ("TIK", "TKO"),
        ("TKO", "HAH"), ("HAH", "POA"), # 往寶琳分支
        ("TKO", "LHP")                   # 往康城分支
    ],
    "TCL": [ # 東涌綫
        ("HOK", "KOW"), ("KOW", "OLY"), ("OLY", "NAC"), ("NAC", "LAK"),
        ("LAK", "TSY"), ("TSY", "SUN"), ("SUN", "TUC")
    ],
    "AEL": [ # 機場快綫
        ("HOK", "KOW"), ("KOW", "TSY"), ("TSY", "AIR"), ("AIR", "AWE")
    ],
    "EAL": [ # 東鐵綫 (含分支)
        ("ADM", "EXC"), ("EXC", "HUH"), ("HUH", "MKK"), ("MKK", "KOT"),
        ("KOT", "TAW"), ("TAW", "SHT"), ("SHT", "FOT"), ("FOT", "RAC"), # RAC 是火炭/馬場，視乎當日運行
        ("RAC", "UNI"), ("UNI", "TAP"), ("TAP", "TWO"), ("TWO", "FAN"),
        ("FAN", "SHS"),
        ("SHS", "LOW"), # 往羅湖分支
        ("SHS", "LMC")  # 往落馬洲分支
    ],
    "TML": [ # 屯馬綫
        ("WKS", "MOS"), ("MOS", "HEO"), ("HEO", "TSH"), ("TSH", "SHM"),
        ("SHM", "CIO"), ("CIO", "STW"), ("STW", "CKW"), ("CKW", "TAW"),
        ("TAW", "HIK"), ("HIK", "DIH"), ("DIH", "TKW"), ("TKW", "SUW"),
        ("SUW", "KAT"), ("KAT", "HOM"), ("HOM", "HUH"), ("HUH", "ETS"),
        ("ETS", "AUS"), ("AUS", "NAC"), ("NAC", "MEF"), ("MEF", "TWW"),
        ("TWW", "KSR"), ("KSR", "YUL"), ("YUL", "LOP"), ("LOP", "TUM")
    ]
}

def get_segments(line_code):
    """回傳指定路線的區間清單"""
    return MTR_SEGMENTS.get(line_code, [])

def get_all_line_codes():
    """回傳所有已定義的路線代碼"""
    return list(MTR_SEGMENTS.keys())
