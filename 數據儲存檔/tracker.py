def is_valid_count(count, current_hour):
    """
    檢查數據是否異常
    1. 營運時間 (06:00-01:00) 班次不應為 0
    2. 根據百科資料，荃灣綫巔峰班次約為 36 班，設定 40 為安全上限
    """
    is_operational_hours = (current_hour >= 6 or current_hour < 1)
    
    if is_operational_hours and count == 0:
        print(f"偵測到異常：營運時間內班次為 0，放棄紀錄。")
        return False
    
    # 設定為 40 (稍微高於 36 以容納極端調度情況)
    if count > 40:
        print(f"偵測到異常：班次數量 ({count}) 超過合理範圍 (max 36+)，放棄紀錄。")
        return False
        
    return True
