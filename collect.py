#!/usr/bin/env python3
import argparse, json, os, re, subprocess, sys, time, uuid, xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

os.umask(0o077)

BASE=None
PACKAGE='com.shark.jizhang:id/'

def adb(*args):
    p=subprocess.run(['adb','-s',SERIAL,*map(str,args)],capture_output=True,timeout=35,check=True)
    return p.stdout

def ui():
    remote='/data/local/tmp/shark-extract-'+uuid.uuid4().hex+'.xml'
    try:
        out=adb('shell','uiautomator','dump',remote)
        if b'dumped to' not in out: raise RuntimeError('界面结构读取失败: '+out.decode(errors='replace'))
        adb('shell','chmod','600',remote)
        raw=adb('exec-out','cat',remote)
    finally:
        adb('shell','rm','-f',remote)
    root=ET.fromstring(raw[raw.index(b'<?xml'):])
    return root,raw

def one(root, rid):
    nodes=[n for n in root.iter('node') if n.get('resource-id')==PACKAGE+rid]
    return nodes[0].get('text','') if nodes else None

def tap(x,y): adb('shell','input','tap',x,y); time.sleep(.4)
def back(): adb('shell','input','keyevent',4); time.sleep(.4)
def save(path, data):
    path.write_bytes(data); os.chmod(path,0o600)
def bounds(n):
    a=list(map(int,re.findall(r'\d+',n.get('bounds','')))); return a if len(a)==4 else [0,0,0,0]

def rows(root):
    parent={c:n for n in root.iter() for c in n}; out=[]
    for t in root.iter('node'):
        if t.get('resource-id')!=PACKAGE+'itemText': continue
        n=t
        while n in parent and not any(c.get('resource-id')==PACKAGE+'itemIcon' for c in n): n=parent[n]
        if not any(c.get('resource-id')==PACKAGE+'itemIcon' for c in n): raise RuntimeError('账目结构不匹配')
        a=next((x.get('text','') for x in n.iter('node') if x.get('resource-id')==PACKAGE+'account'),None)
        texts=tuple((x.get('resource-id',''),x.get('text','')) for x in n.iter('node') if x.get('text'))
        x1,y1,x2,y2=bounds(n)
        if a is not None and y1>=250 and y2<=2015 and y2-y1>30: out.append({'sig':texts,'amount':a,'category':t.get('text'), 'x':min(x1+320,700),'y':(y1+y2)//2})
    return out

def month():
    root,raw=ui(); year=one(root,'dataSelectorYear'); mo=one(root,'dataSelectorMonth')
    if not year or not mo: raise RuntimeError('请先打开主账本明细页并滚动到顶部')
    month=f'{int(year.replace("年","")):04d}-{int(mo):02d}'
    income=one(root,'incomeAmount'); expense=one(root,'expensesAmount')
    session=BASE/(month+'-'+uuid.uuid4().hex[:8]); session.mkdir(mode=0o700,parents=True)
    save(session/'month.xml',raw)
    result={'month':month,'app_income':income,'app_expense':expense,'records':[],'pages':[], 'complete':False,'warnings':[]}
    def checkpoint(): save(session/'records.json',json.dumps(result,ensure_ascii=False,indent=2).encode())
    prev=[]; page=0
    while page<100:
        if page:
            root,raw=ui()
            current_month = one(root, 'dataSelectorMonth')
            if current_month and int(current_month) != int(mo):
                result['complete']=True; break
        save(session/f'list-{page:03}.xml',raw)
        current=rows(root); sig=[x['sig'] for x in current]
        if page and sig==prev:
            result['complete']=True; break
        overlap=0
        if page:
            for k in range(min(len(prev),len(sig)),0,-1):
                if prev[-k:]==sig[:k]: overlap=k; break
            if not overlap:
                result['warnings'].append('滚动后无重叠，可能漏项，必须核对'); break
        for j,row in enumerate(current[overlap:], start=overlap):
            tap(row['x'],row['y'])
            detail,dr=ui()
            category=one(detail,'categoryName'); amount=one(detail,'accountText'); kind=one(detail,'categoryTypeText'); date=one(detail,'accountDate')
            if None in (category,amount,kind,date) or row['category'] not in (category, one(detail,'remarkText')):
                raise RuntimeError(f'详情与列表不匹配，停止：page={page} row={j}')
            if not date.startswith(f'{int(year.replace("年","")):04d}年{int(mo):02d}月'):
                raise RuntimeError('详情日期不属于当前月份')
            if Decimal(amount)!=abs(Decimal(row['amount'].replace(',',''))): raise RuntimeError('详情金额与列表不符')
            nodes=[{'id':n.get('resource-id',''),'text':n.get('text',''),'desc':n.get('content-desc','')} for n in detail.iter('node') if n.get('text') or n.get('content-desc')]
            index=len(result['records'])+1
            save(session/f'detail-{index:04}.xml',dr)
            result['records'].append({'category':category,'amount':amount,'type':kind,'date':date,'nodes':nodes,'page':page,'row':j,'source':f'detail-{index:04}.xml'})
            checkpoint(); back()
            print(month, '已采集',index, flush=True)
            if args.limit and index >= args.limit:
                result['warnings'].append('按指定数量停止，尚未核对完整性'); checkpoint(); return 2
        result['pages'].append({'page':page,'visible':len(sig),'overlap':overlap})
        checkpoint(); prev=sig; page+=1
        if not current: result['complete']=True; break
        adb('shell','input','swipe',950,1600,950,1200,600); time.sleep(.5)
    got_in=sum((Decimal(x['amount']) for x in result['records'] if x['type']=='收入'),Decimal(0))
    got_out=sum((Decimal(x['amount']) for x in result['records'] if x['type']=='支出'),Decimal(0))
    result['sum_income']=str(got_in); result['sum_expense']=str(got_out)
    result['totals_match']=bool(income and expense and got_in==Decimal(income.replace(',','')) and got_out==Decimal(expense.replace(',','')))
    if not result['totals_match']: result['warnings'].append('与应用月度汇总不一致')
    checkpoint(); print('完成页面采集',month,'笔数',len(result['records']),'金额核对',result['totals_match'],'页面结束',result['complete'],flush=True)
    return 0 if result['complete'] and result['totals_match'] else 2

p=argparse.ArgumentParser(); p.add_argument('--serial',required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--limit',type=int,default=0); args=p.parse_args(); SERIAL=args.serial; BASE=args.output.expanduser()
try:
    size=adb('shell','wm','size').decode()
    if '1916x2160' not in size or ('Override size:' in size and 'Override size: 1916x2160' not in size): raise RuntimeError('此版本仅支持已验证的 1916x2160 屏幕尺寸')
    version=adb('shell','dumpsys','package','com.shark.jizhang').decode(errors='replace')
    if not re.search(r'versionName=5\.86\.1(?:\s|$)', version): raise RuntimeError('此版本仅支持已验证的鲨鱼记账 5.86.1')
    focus=adb('shell','dumpsys','window').decode(errors='replace')
    if not any('mCurrentFocus=Window' in line and 'com.shark.jizhang/' in line for line in focus.splitlines()): raise RuntimeError('请先打开鲨鱼记账')
    sys.exit(month())
except Exception as e: print('停止：',e,file=sys.stderr); sys.exit(1)
