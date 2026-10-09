"""Export ranked results to CSV and spreadsheet (artifact_tool)."""
import csv
from pathlib import Path

COLUMNS = ['departure_date','return_date','leave_days','leave_dates','price_twd','total_cost_twd','usable_hours','cost_per_hour','airline','direct','source','mode','outbound_departure','outbound_arrival','return_departure','return_arrival','checked_at','expires_at','offer_id']

def export_csv(rows, path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction='ignore');w.writeheader();w.writerows(rows)
    return path

def export_xlsx(rows, path):
    from artifact_tool import Workbook, SpreadsheetFile
    wb=Workbook.create();sh=wb.worksheets.add('航班價格排名')
    titles=['去程日','回程日','請假天數','請假日期','機票 TWD','總成本 TWD','可玩小時','每小時成本','航空公司','直飛','來源','模式','去程起飛','抵達札幌','回程起飛','抵達台灣','查詢時間','報價效期','報價ID']
    cells=[titles]+[[r.get(c,'') if r.get(c,'') is not None else '' for c in COLUMNS] for r in rows]
    sh.get_range_by_indexes(0,0,len(cells),len(COLUMNS)).values=cells
    sh.get_range('A1:S1').format={'fill':'#153B76','font':{'bold':True,'color':'#FFFFFF'},'row_height':30}
    sh.freeze_panes.freeze_rows(1)
    sh.get_range('A:A').format.column_width=17
    sh.get_range('B:B').format.column_width=17
    sh.get_range('D:D').format.column_width=29
    sh.get_range('I:I').format.column_width=24
    sh.get_range('M:P').format.column_width=24
    sh.get_range('Q:R').format.column_width=27
    sh.get_range('S:S').format.column_width=30
    sh.get_range('E:H').format.column_width=18
    sh.get_range('J:L').format.column_width=14
    sh.get_range('C:C').format.column_width=13
    if rows: sh.tables.add(f'A1:S{len(rows)+1}',True,'FlightOffers')
    SpreadsheetFile.export_xlsx(wb).save(str(path))
    return path
