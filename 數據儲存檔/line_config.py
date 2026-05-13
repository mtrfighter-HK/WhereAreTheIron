# line_config.py

# 定義各條路線的車站順序
# 格式為 { "路線代碼": ["車站1", "車站2", ...] }

MTR_LINES = {
    "TWL": ["CEN", "ADM", "TST", "JOR", "YMT", "MOK", "PRE", "SSP", "CSW", "LCK", "MEF", "LAK", "KWF", "KWH", "TWH", "TSW"],

    "ISL": ["KET", "HKU", "SYP", "SHW", "CEN", "ADM", "WAC", "CAB", "TIH", "FOH", "NOP", "QUB", "TAK", "SWH", "SKW", "HFC", "CHW"],

    "KTL": ["WHA", "HOM", "YMT", "MKK", "PRE", "SKM", "KOT", "LOF", "WTS", "DIH", "CHH", "KOB", "NTK", "KWT", "LAT", "YAT", "TIK"],

    "SIL": ["ADM", "OCP", "WCH", "LET", "SOH"],

    "DRL": ["SUN", "DIS"],

    "TCL": ["HOK", "KOW", "OLY", "NAC", "LAK", "TSY", "SUN", "TUC"],

    "AEL": ["HOK", "KOW", "TSY", "AIR", "AWE"],

    "TKL": ["NOP", "QUB", "YAT", "TIK", "TKO", "LHP"],

    "EAL": ["ADM", "EXC", "HUH", "MKK", "KOT", "TAW", "SHT", "FOT", "UNI", "TAI", "NOP", "QUB", "TAK", "SWH", "SKW", "HFC", "CHW"],

    "TML": ["KET", "HKU", "SYP", "SHW", "CEN", "ADM", "WAC", "CAB", "TIH", "FOH", "NOP", "QUB", "TAK", "SWH", "SKW", "HFC", "CHW"],

}

def get_segments(line_code):
    """
    自動根據車站列表生成『區間』(Segments)
    例如輸入 [A, B, C] 會輸出 [(A, B), (B, C)]
    """
    stations = MTR_LINES.get(line_code, [])
    segments = []
    for i in range(len(stations) - 1):
        segments.append((stations[i], stations[i+1]))
    return segments
