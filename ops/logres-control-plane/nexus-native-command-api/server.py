import hmac,json,os,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
TOKEN=os.environ.get('NEXUS_NATIVE_API_TOKEN','')
APPROVALS={}
def authorized(h):
 a=h.headers.get('Authorization',''); x=h.headers.get('X-Nexus-Token',''); got=a[7:] if a.startswith('Bearer ') else x
 return bool(TOKEN) and hmac.compare_digest(got,TOKEN)
def pending(): return [v for v in APPROVALS.values() if v['status']=='PENDING']
class H(BaseHTTPRequestHandler):
 def sendj(self,code,obj):
  b=json.dumps(obj,separators=(',',':')).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if not authorized(self): return self.sendj(401,{'ok':False,'error':'unauthorized'})
  if self.path=='/api/snapshot': return self.sendj(200,{'integration':{},'counts':{},'workers':[],'tasks':{},'approvals':pending(),'health':{'native_api':True},'ts':time.time()})
  return self.sendj(404,{'ok':False,'error':'not_found'})
 def do_POST(self):
  if not authorized(self): return self.sendj(401,{'ok':False,'error':'unauthorized'})
  try:n=int(self.headers.get('Content-Length','0')); body=json.loads(self.rfile.read(n) or b'{}')
  except Exception:return self.sendj(400,{'ok':False,'error':'invalid_json'})
  if self.path=='/api/approvals/register':
   for k in ('id','sha','reason','evidence_summary'):
    if not body.get(k): return self.sendj(400,{'ok':False,'error':'missing_'+k})
   if len(body['sha'])!=40:return self.sendj(400,{'ok':False,'error':'invalid_sha'})
   APPROVALS[body['id']]={'id':body['id'],'sha':body['sha'],'reason':body['reason'],'evidence_summary':body['evidence_summary'],'status':'PENDING','created_at':time.time()};return self.sendj(201,APPROVALS[body['id']])
  if self.path=='/api/control' and body.get('action') in ('approve-gate','reject-gate'):
   a=APPROVALS.get(body.get('approval_id'))
   if not a:return self.sendj(404,{'ok':False,'error':'approval_not_found'})
   if a['status']!='PENDING':return self.sendj(409,{'ok':False,'error':'approval_already_decided'})
   if body.get('sha')!=a['sha']:return self.sendj(409,{'ok':False,'error':'sha_mismatch'})
   a['status']='APPROVED' if body['action']=='approve-gate' else 'REJECTED';a['decided_at']=time.time();return self.sendj(200,{'ok':True,'approval':a})
  return self.sendj(400,{'ok':False,'error':'unsupported_action'})
 def log_message(self,*a):pass
if __name__=='__main__':
 ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','8790'))),H).serve_forever()
