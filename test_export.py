import json, tempfile, unittest
from pathlib import Path
from export import convert, safe

class ExportTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.p=Path(self.tmp.name)/'records.json'
  self.obj={'month':'2023-01','complete':True,'totals_match':True,'warnings':[],'app_income':'0.00','app_expense':'12.30','records':[{'date':'2023年01月01日 星期日','type':'支出','amount':'12.3','category':'餐饮','nodes':[{'id':'x/remarkText','text':'测试'}],'source':'detail-0001.xml'}]}
 def tearDown(self):self.tmp.cleanup()
 def write(self):self.p.write_text(json.dumps(self.obj),encoding='utf-8')
 def test_verified(self):
  self.write();rows=convert([self.p]);self.assertEqual(rows[0][:6],['2023-01-01','支出','餐饮','12.3','测试','详情页有备注'])
 def test_mismatch_refused(self):
  self.obj['app_expense']='12.31';self.write()
  with self.assertRaises(ValueError):convert([self.p])
 def test_duplicate_month_refused(self):
  self.write()
  with self.assertRaises(ValueError):convert([self.p,self.p])
 def test_incomplete_refused(self):
  self.obj['complete']=False;self.write()
  with self.assertRaises(ValueError):convert([self.p])
 def test_csv_formula_escape(self):self.assertEqual(safe(' =cmd'),"' =cmd")
if __name__=='__main__':unittest.main()
