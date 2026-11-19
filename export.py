#!/usr/bin/env python3
"""Convert individually verified monthly captures into CSV; never merge ambiguous captures."""
import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys

HEADERS=['日期','类型','分类','金额（元）','备注','备注状态','来源']

def convert(paths):
    months=set(); rows=[]
    for path in paths:
        obj=json.loads(path.read_text(encoding='utf-8'))
        month=obj['month']
        if month in months: raise ValueError(f'{month} 有多个采集批次，需先人工核对合并')
        months.add(month)
        if obj.get('complete') is not True or obj.get('totals_match') is not True or obj.get('warnings'):
            raise ValueError(f'{path}: 批次未通过完整性及金额检查')
        totals={'收入':Decimal(0),'支出':Decimal(0)}
        for r in obj['records']:
            kind=r['type']; amount=Decimal(r['amount'].replace(',',''))
            if kind not in totals or amount<0: raise ValueError('不支持的账目类型或金额')
            totals[kind]+=amount
            m=re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日',r['date'])
            if not m: raise ValueError('日期格式无法识别')
            date=f'{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}'
            if not date.startswith(month+'-'): raise ValueError('详情日期与月份不一致')
            note=next((n['text'] for n in r['nodes'] if n['id'].endswith('/remarkText')),None)
            rows.append([date,kind,r['category'],str(amount),note or '', '详情页有备注' if note is not None else '详情页未显示',path.parent.name+'/'+r['source']])
        if totals['收入']!=Decimal(obj['app_income'].replace(',','')) or totals['支出']!=Decimal(obj['app_expense'].replace(',','')):
            raise ValueError(f'{month}: 重新计算的合计与应用不一致')
    return sorted(rows,key=lambda r:r[0])

def safe(value):
    value=str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('captures',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    try:
        rows=convert(args.captures)
        with args.output.open('x',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f);writer.writerow(HEADERS);writer.writerows([[safe(v) for v in row] for row in rows])
        args.output.chmod(0o600)
        print(f'已导出 {len(rows)} 笔；请与应用总笔数和全部账本逐项核对。')
    except (OSError,ValueError,KeyError,InvalidOperation,json.JSONDecodeError) as e:
        print(f'未导出：{e}',file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
