import json, os, sys, tempfile, unittest
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPTest(unittest.IsolatedAsyncioTestCase):
 async def test_stdio_tools_and_export(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp); sample=root/'sample'/'2023-01-example'; sample.mkdir(parents=True)
   data={'month':'2023-01','complete':True,'totals_match':True,'warnings':[], 'app_income':'0','app_expense':'10','records':[{'date':'2023年01月01日','type':'支出','amount':'10','category':'餐饮','nodes':[],'source':'detail-0001.xml'}]}
   (sample/'records.json').write_text(json.dumps(data),encoding='utf-8')
   env=dict(os.environ,SHARK_DATA_DIR=temp)
   p=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('server.py'))],env=env)
   async with stdio_client(p) as (reader,writer):
    async with ClientSession(reader,writer) as session:
     await session.initialize()
     names={t.name for t in (await session.list_tools()).tools}
     self.assertEqual(names,{'diagnose','start_month_capture','capture_status','cancel_capture','export_csv'})
     r=await session.call_tool('start_month_capture',{'serial':'test','output_name':'test','quick_edit_disabled':False,'at_month_top':False})
     self.assertIn('Disable quick edit',str(r.content))
     r=await session.call_tool('export_csv',{'capture_paths':['sample/2023-01-example/records.json'],'output_name':'sample/out.csv'})
     self.assertIn('completed',str(r.content)); self.assertTrue((root/'sample/out.csv').exists())
     r=await session.call_tool('export_csv',{'capture_paths':['../outside/records.json'],'output_name':'sample/bad.csv'})
     self.assertIn('failed',str(r.content));self.assertFalse((root/'sample/bad.csv').exists())
