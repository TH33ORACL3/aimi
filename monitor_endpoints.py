#!/usr/bin/env python3
"""Poll official model endpoints, preserve snapshots, and record meaningful diffs.

Designed for a future scheduler. It stores credential names, never credential values.
First run establishes a baseline. Later runs emit added/removed/metadata/pricing changes.
"""
from __future__ import annotations
import hashlib,json,os,re,sqlite3,time,urllib.request,urllib.error
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/'aimi.db'; SNAP=ROOT/'snapshots'/'monitor'; SNAP.mkdir(parents=True,exist_ok=True)
NOW=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); STAMP=NOW.replace(':','').replace('+00:00','Z')
CONFIG={
 'openrouter':('https://openrouter.ai/api/v1/models','OPENROUTER_API_KEY','data'),
 'opencode-zen':('https://opencode.ai/zen/v1/models','OPENCODE_API_KEY','data'),
 'opencode-go':('https://opencode.ai/zen/go/v1/models','OPENCODE_API_KEY','data'),
 'nvidia-nim':('https://integrate.api.nvidia.com/v1/models','NVIDIA_API_KEY','data'),
 'deepseek':('https://api.deepseek.com/v1/models','DEEPSEEK_API_KEY','data'),
 'mistral':('https://api.mistral.ai/v1/models','MISTRAL_API_KEY','data'),
 'openai':('https://api.openai.com/v1/models','OPENAI_API_KEY','data'),
 'gemini':('https://generativelanguage.googleapis.com/v1beta/models','GEMINI_API_KEY','models'),
 'cloudflare-ai':(f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('CLOUDFLARE_ACCOUNT_ID','{account_id}')}/ai/models/search?per_page=200",'CLOUDFLARE_API_TOKEN_AZLABS_AI_WORKERS','result'),
 'ollama-cloud':('https://ollama.com/v1/models',None,'data'),
}

def safe_url(pid,url):
 return 'https://generativelanguage.googleapis.com/v1beta/models' if pid=='gemini' else url.replace(os.getenv('CLOUDFLARE_ACCOUNT_ID','__NO_ACCOUNT__'),'{account_id}')

TRANSIENT_HTTP_STATUS={408,425,429,500,502,503,504}


def fetch(pid,url,env):
 key=os.getenv(env) if env else None; headers={'User-Agent':'AZ-Labs-model-monitor/1.0'}
 if env and not key: raise RuntimeError(f'missing {env}')
 if pid=='gemini': url=url+'?key='+key
 elif key: headers['Authorization']='Bearer '+key
 req=urllib.request.Request(url,headers=headers)
 last_error=None
 for attempt in range(3):
  try:
   with urllib.request.urlopen(req,timeout=45) as r:return r.status,r.read(),dict(r.headers)
  except urllib.error.HTTPError as exc:
   last_error=exc
   if exc.code not in TRANSIENT_HTTP_STATUS or attempt==2: raise
  except urllib.error.URLError as exc:
   last_error=exc
   if attempt==2: raise
  time.sleep(2 ** attempt)
 raise last_error or RuntimeError('model endpoint request failed')

SECRET_KEY = re.compile(r'(^|[_-])(api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|secret)(_|$)', re.I)


def sanitize_value(value):
 if isinstance(value,dict):
  return {str(k):sanitize_value(v) for k,v in value.items() if not SECRET_KEY.search(str(k))}
 if isinstance(value,list):return [sanitize_value(v) for v in value]
 return value


def first_present(*values):
 for value in values:
  if value is not None:return value
 return None


def numeric(value):
 if isinstance(value,bool):return int(value)
 if isinstance(value,(int,float)):return int(value)
 if isinstance(value,str):
  try:return int(float(value))
  except ValueError:return None
 return None


def as_list(value):
 if value is None:return None
 if isinstance(value,list):return value
 if isinstance(value,str):return [value]
 return value


def as_tristate(value):
 if value is None:return None
 if isinstance(value,bool):return int(value)
 if isinstance(value,(int,float)):return int(bool(value))
 if isinstance(value,str):
  lowered=value.strip().lower()
  if lowered in {'true','yes','supported','enabled'}:return 1
  if lowered in {'false','no','unsupported','disabled'}:return 0
 if isinstance(value,(list,dict)):return int(bool(value))
 return None


def capability_value(item,caps,keys):
 for key in keys:
  if key in item:return as_tristate(item.get(key))
  if key in caps:return as_tristate(caps.get(key))
 return None


def created_at(value):
 if value is None:return None
 if isinstance(value,(int,float)):
  timestamp=float(value)
  if timestamp>100000000000:timestamp/=1000
  try:return datetime.fromtimestamp(timestamp,tz=timezone.utc).replace(microsecond=0).isoformat()
  except (OverflowError,OSError,ValueError):return None
 if isinstance(value,str):return value
 return None


def rows(pid,payload,key):
 out={}
 for original in payload.get(key,[]):
  x=sanitize_value(original)
  mid=(x.get('name') or x.get('id')) if pid=='cloudflare-ai' else (x.get('id') or x.get('name'))
  if not mid:continue
  caps=x.get('capabilities') if isinstance(x.get('capabilities'),dict) else {}
  top=x.get('top_provider') if isinstance(x.get('top_provider'),dict) else {}
  architecture=x.get('architecture') if isinstance(x.get('architecture'),dict) else {}
  reasoning_details=x.get('reasoning') if isinstance(x.get('reasoning'),dict) else {}
  supported_parameters=x.get('supported_parameters') if isinstance(x.get('supported_parameters'),list) else []
  context=numeric(first_present(x.get('context_length'),top.get('context_length'),x.get('max_context_length'),x.get('inputTokenLimit'),x.get('context_window_tokens'),x.get('contextWindow'),x.get('context')))
  max_input=numeric(first_present(x.get('max_input_tokens'),x.get('max_input'),x.get('max_prompt_tokens'),top.get('max_prompt_tokens'),x.get('inputTokenLimit')))
  max_output=numeric(first_present(x.get('max_output_tokens'),x.get('max_output'),x.get('outputTokenLimit'),top.get('max_completion_tokens')))
  input_modalities=as_list(first_present(x.get('input_modalities'),architecture.get('input_modalities'),x.get('modalities')))
  output_modalities=as_list(first_present(x.get('output_modalities'),architecture.get('output_modalities'),x.get('modalities')))
  methods=first_present(x.get('supportedGenerationMethods'),x.get('supported_generation_methods'),x.get('methods'))
  aliases=first_present(x.get('aliases'),x.get('alias'),x.get('model_aliases'))
  alias_values=[] if aliases is None else (aliases if isinstance(aliases,list) else [aliases])
  if x.get('canonical_slug'):alias_values.append({'id':x.get('canonical_slug'),'type':'provider_canonical_slug'})
  if x.get('hugging_face_id'):alias_values.append({'id':x.get('hugging_face_id'),'type':'hugging_face_id'})
  reasoning=capability_value(x,caps,('reasoning','supports_reasoning','thinking'))
  if reasoning is None and reasoning_details:reasoning=1
  tools=capability_value(x,caps,('tools','supports_tools','tool_use','tool_calling'))
  if tools is None and 'tools' in supported_parameters:tools=1
  function_calling=capability_value(x,caps,('function_calling','supports_function_calling','function_call'))
  if function_calling is None and ('tools' in supported_parameters or 'tool_choice' in supported_parameters):function_calling=1
  structured_outputs=capability_value(x,caps,('structured_outputs','structured_output','supports_structured_outputs','supports_structured_output'))
  if structured_outputs is None and 'response_format' in supported_parameters:structured_outputs=1
  streaming=capability_value(x,caps,('streaming','supports_streaming'))
  if streaming is None and 'stream' in supported_parameters:streaming=1
  view={
   'id':mid,
   'name':x.get('name'),
   'displayName':first_present(x.get('displayName'),x.get('display_name')),
   'description':x.get('description'),
   'provider_created_at':created_at(first_present(x.get('created'),x.get('created_at'))),
   'context_length':context,
   'max_input':max_input,
   'max_output':max_output,
   'input_modalities':input_modalities,
   'output_modalities':output_modalities,
   'pricing':x.get('pricing'),
   'capabilities':caps,
   'methods':methods,
   'thinking':x.get('thinking'),
   'reasoning':reasoning,
   'tools':tools,
   'function_calling':function_calling,
   'structured_outputs':structured_outputs,
   'streaming':streaming,
   'reasoning_efforts':first_present(x.get('reasoning_efforts'),caps.get('reasoning_efforts'),reasoning_details.get('supported_efforts')),
   'thinking_api':first_present(x.get('thinking_api'),caps.get('thinking_api')),
   'aliases':alias_values,
   'tokenizer':first_present(x.get('tokenizer'),architecture.get('tokenizer')),
   'quantization':first_present(x.get('quantization'),x.get('quantization_config')),
   'canonical_slug':x.get('canonical_slug'),
   'hugging_face_id':x.get('hugging_face_id'),
   'deprecation':first_present(x.get('deprecation'),x.get('deprecated')),
   'replacement':first_present(x.get('deprecation_replacement_model'),x.get('replacement'),x.get('replacement_model')),
   'raw':x,
  }
  out[mid]=view
 return out

def is_free(pid,x):
 if pid=='openrouter':return x.get('pricing',{}).get('prompt')=='0' and x.get('pricing',{}).get('completion')=='0'
 if pid=='opencode-zen':return x['id'].endswith('-free')
 return False


def per_million(value):
 if value is None:return None
 try:return format((Decimal(str(value))*Decimal('1000000')).normalize(),'f')
 except (InvalidOperation,ValueError):return None


def endpoint_price(pid,x):
 pricing=x.get('pricing') if isinstance(x.get('pricing'),dict) else {}
 if pricing:
  return {
   'input':per_million(first_present(pricing.get('prompt'),pricing.get('input'),pricing.get('input_price'))),
   'output':per_million(first_present(pricing.get('completion'),pricing.get('output'),pricing.get('output_price'))),
   'cache_read':per_million(first_present(pricing.get('input_cache_read'),pricing.get('cache_read'))),
   'cache_write':per_million(first_present(pricing.get('input_cache_write'),pricing.get('cache_write'))),
   'request':None,
   'unit':'per million tokens',
  }
 raw=x.get('raw') if isinstance(x.get('raw'),dict) else {}
 properties=raw.get('properties') if isinstance(raw.get('properties'),list) else []
 for prop in properties:
  if not isinstance(prop,dict) or prop.get('property_id')!='price':continue
  values=prop.get('value') if isinstance(prop.get('value'),list) else []
  for value in values:
   if isinstance(value,dict) and value.get('price') is not None:
    return {'input':None,'output':None,'cache_read':None,'cache_write':None,'request':str(value.get('price')),'unit':value.get('unit') or 'per request'}
 return None


def upsert_endpoint_offer(c,pid,provider_model_id,x,source_id,capture_id):
 price=endpoint_price(pid,x)
 if not price:return
 if pid=='openrouter' and is_free(pid,x):return
 offer_type='paid' if price.get('input') is not None or price.get('output') is not None or price.get('request') is not None else 'unknown'
 terms=f"Official {pid} models endpoint reported pricing ({price.get('unit')})."
 existing=c.execute("SELECT access_offer_id FROM access_offers WHERE provider_model_id=? AND offer_type=? AND starts_at IS NULL ORDER BY access_offer_id DESC LIMIT 1",(provider_model_id,offer_type)).fetchone()
 values=(price.get('input'),price.get('output'),price.get('cache_read'),price.get('cache_write'),price.get('request'))
 if existing:
  c.execute("""UPDATE access_offers SET last_observed_at=?,input_price_per_million_usd=?,output_price_per_million_usd=?,cache_read_price_per_million_usd=?,cache_write_price_per_million_usd=?,request_price_usd=?,terms_summary=?,evidence_source_id=?,evidence_capture_id=?,last_verified_at=? WHERE access_offer_id=?""",(NOW,values[0],values[1],values[2],values[3],values[4],terms,source_id,capture_id,NOW,existing[0]))
 else:
  c.execute("""INSERT INTO access_offers(provider_model_id,offer_type,first_observed_at,last_observed_at,input_price_per_million_usd,output_price_per_million_usd,cache_read_price_per_million_usd,cache_write_price_per_million_usd,request_price_usd,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at)
   VALUES(?,?,?, ?,?,?,?,?,?,?,?,?,?,?)""",(provider_model_id,offer_type,NOW,NOW,values[0],values[1],values[2],values[3],values[4],terms,source_id,capture_id,'verified' if pid in ('openrouter','openai','mistral','deepseek') else 'single_source',NOW))


LIFECYCLE_FIELDS={
 'announcement_date':'announcement','announcementDate':'announcement',
 'preview_release_date':'preview_release','previewReleaseDate':'preview_release',
 'release_date':'general_release','releaseDate':'general_release','ga_date':'general_release','general_availability_date':'general_release',
 'api_availability_date':'api_availability','apiAvailabilityDate':'api_availability',
 'model_card_date':'model_card_publication','modelCardDate':'model_card_publication',
 'weights_release_date':'weights_release','weightsReleaseDate':'weights_release',
}


def event_time(value):
 if isinstance(value,(int,float)):return created_at(value)
 if isinstance(value,str):return value
 return None


def event_precision(value):
 text=str(value or '')
 if 'T' in text or (' ' in text and ':' in text):return 'second'
 if len(text)==7:return 'month'
 if len(text)==4:return 'year'
 return 'day'


def record_endpoint_events(c,provider_model_id,x,source_id,capture_id):
 raw=x.get('raw') if isinstance(x.get('raw'),dict) else {}
 for field,event_type in LIFECYCLE_FIELDS.items():
  if raw.get(field) in (None,''):continue
  when=event_time(raw.get(field))
  if not when:continue
  c.execute("""INSERT OR IGNORE INTO model_events(provider_model_id,event_type,event_time,time_precision,evidence_source_id,evidence_capture_id,supporting_quote,confidence,details_json)
   VALUES(?,?,?,?,?,?,?, 'single_source',?)""",(provider_model_id,event_type,when,event_precision(raw.get(field)),source_id,capture_id,f"Official endpoint field {field} reported {raw.get(field)}.",json.dumps({'provider_field':field,'provider_value':raw.get(field)})))


def source_capture(c,pid,url,raw,path,status):
 clean=safe_url(pid,url); sha=hashlib.sha256(raw).hexdigest()
 c.execute("INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,http_status,trust_priority,verification_status) VALUES(?,?,?, ?,1,1,?,?,1,'verified')",(clean,'api_endpoint',pid,f'{pid} official models endpoint',NOW,status))
 sid=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(clean,)).fetchone()[0]
 c.execute("INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version) VALUES(?,?,?,?,?,'endpoint_monitor','1.0')",(sid,NOW,sha,str(path),status))
 cap=c.execute('SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?',(sid,sha)).fetchone()[0]
 return sid,cap,sha

def ensure_metadata_schema(c):
 columns={row[1] for row in c.execute('PRAGMA table_info(provider_models_v2)')}
 for name in ('description','provider_created_at'):
  if name not in columns:c.execute(f'ALTER TABLE provider_models_v2 ADD COLUMN {name} TEXT')
 c.execute("""CREATE TABLE IF NOT EXISTS provider_model_aliases (
  provider_model_alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_model_id INTEGER NOT NULL REFERENCES provider_models_v2(provider_model_id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  alias_type TEXT NOT NULL DEFAULT 'provider_alias',
  first_observed_at TEXT NOT NULL,
  last_observed_at TEXT NOT NULL,
  evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id),
  UNIQUE(provider_model_id,alias)
 )""")
 c.execute('CREATE INDEX IF NOT EXISTS idx_provider_model_aliases_model ON provider_model_aliases(provider_model_id)')
 c.commit()


def ensure_target(c,pid,url):
 clean=safe_url(pid,url)
 c.execute("INSERT OR IGNORE INTO monitoring_targets(provider_id,target_type,url,schedule_class,enabled,expected_format,parser_name) VALUES(?,'models_endpoint',?,'frequent',1,'json',?)",(pid,clean,pid))
 return c.execute("SELECT monitoring_target_id FROM monitoring_targets WHERE target_type='models_endpoint' AND url=?",(clean,)).fetchone()[0]


def ensure_model_source(c,pid,url,status,raw,path,record_count):
 clean=safe_url(pid,url);sha=hashlib.sha256(raw).hexdigest()
 c.execute("INSERT INTO model_sources(provider_id,endpoint,fetched_at,http_status,response_sha256,raw_snapshot_path,record_count) VALUES(?,?,?,?,?,?,?)",(pid,clean,NOW,status,sha,str(path),record_count))
 return c.execute('SELECT last_insert_rowid()').fetchone()[0]


def ensure_pm(c,pid,mid,x,source_snapshot_id):
 context=x.get('context_length')
 max_input=x.get('max_input')
 max_output=x.get('max_output')
 display=first_present(x.get('displayName'),x.get('name'),mid)
 input_modalities=json.dumps(x.get('input_modalities'),sort_keys=True) if x.get('input_modalities') is not None else None
 output_modalities=json.dumps(x.get('output_modalities'),sort_keys=True) if x.get('output_modalities') is not None else None
 c.execute("""INSERT INTO provider_models_v2(
  provider_id,model_identifier,display_name,description,provider_created_at,
  endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,
  context_window_tokens,max_input_tokens,max_output_tokens,reasoning,tools,
  function_calling,structured_outputs,streaming,input_modalities_json,
  output_modalities_json,tokenizer,quantization,provider_metadata_json,source_snapshot_id)
 VALUES(?,?,?,?,?,'available',?,?, ?,?,?,?,?,?,?,?,?,?,?,?,?,?)
 ON CONFLICT(provider_id,model_identifier) DO UPDATE SET
  display_name=COALESCE(excluded.display_name,provider_models_v2.display_name),
  description=COALESCE(excluded.description,provider_models_v2.description),
  provider_created_at=COALESCE(excluded.provider_created_at,provider_models_v2.provider_created_at),
  endpoint_status='available',endpoint_last_seen_at=excluded.endpoint_last_seen_at,
  endpoint_removed_at=NULL,
  context_window_tokens=COALESCE(excluded.context_window_tokens,provider_models_v2.context_window_tokens),
  max_input_tokens=COALESCE(excluded.max_input_tokens,provider_models_v2.max_input_tokens),
  max_output_tokens=COALESCE(excluded.max_output_tokens,provider_models_v2.max_output_tokens),
  reasoning=COALESCE(excluded.reasoning,provider_models_v2.reasoning),
  tools=COALESCE(excluded.tools,provider_models_v2.tools),
  function_calling=COALESCE(excluded.function_calling,provider_models_v2.function_calling),
  structured_outputs=COALESCE(excluded.structured_outputs,provider_models_v2.structured_outputs),
  streaming=COALESCE(excluded.streaming,provider_models_v2.streaming),
  input_modalities_json=COALESCE(excluded.input_modalities_json,provider_models_v2.input_modalities_json),
  output_modalities_json=COALESCE(excluded.output_modalities_json,provider_models_v2.output_modalities_json),
  tokenizer=COALESCE(excluded.tokenizer,provider_models_v2.tokenizer),
  quantization=COALESCE(excluded.quantization,provider_models_v2.quantization),
  provider_metadata_json=excluded.provider_metadata_json,
  source_snapshot_id=excluded.source_snapshot_id""",
 (pid,mid,display,x.get('description'),x.get('provider_created_at'),NOW,NOW,context,max_input,max_output,x.get('reasoning'),x.get('tools'),x.get('function_calling'),x.get('structured_outputs'),x.get('streaming'),input_modalities,output_modalities,x.get('tokenizer'),x.get('quantization'),json.dumps(x,sort_keys=True),source_snapshot_id))
 return c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()[0]


def ensure_aliases(c,provider_model_id,x,capture_id):
 aliases=x.get('aliases') or []
 if isinstance(aliases,(str,int)):aliases=[aliases]
 for alias in aliases:
  alias_type='provider_alias'
  if isinstance(alias,dict):
   alias_type=str(alias.get('type') or 'provider_alias');alias=alias.get('id') or alias.get('name')
  if not alias or str(alias)==str(x.get('id')):continue
  c.execute("""INSERT INTO provider_model_aliases(provider_model_id,alias,alias_type,first_observed_at,last_observed_at,evidence_capture_id)
   VALUES(?,?,?,?,?,?) ON CONFLICT(provider_model_id,alias) DO UPDATE SET last_observed_at=excluded.last_observed_at,evidence_capture_id=excluded.evidence_capture_id""",
   (provider_model_id,str(alias),alias_type,NOW,NOW,capture_id))

VOLATILE_METADATA_KEYS={'created','updated','updated_at','last_updated','fetched_at','retrieved_at','timestamp','last_modified'}


def stable_metadata(value):
 if isinstance(value,dict):
  return {key:stable_metadata(item) for key,item in value.items() if str(key).lower() not in VOLATILE_METADATA_KEYS}
 if isinstance(value,list):return [stable_metadata(item) for item in value]
 return value


def change_types(before,after):
 types=[]
 if before.get('pricing') != after.get('pricing'): types.append('pricing_changed')
 capability_keys=('context_length','max_input','inputTokenLimit','outputTokenLimit','max_output','capabilities','methods','thinking','reasoning','tools','function_calling','structured_outputs','streaming','input_modalities','output_modalities','reasoning_efforts','thinking_api')
 if any(before.get(key) != after.get(key) for key in capability_keys): types.append('capability_changed')
 if before.get('aliases') != after.get('aliases'): types.append('alias_changed')
 excluded={'pricing','aliases','raw','provider_created_at',*capability_keys}
 top_level_changed=any(before.get(key) != after.get(key) for key in before.keys() | after.keys() if key not in excluded)
 raw_changed=stable_metadata(before.get('raw')) != stable_metadata(after.get('raw'))
 if top_level_changed or (raw_changed and not types):
  types.append('model_changed')
 return types

def stored_path(value):
 """Resolve a stored evidence path. Paths are project-relative by design."""
 p=Path(value)
 return p if p.is_absolute() else ROOT/p


def snapshot_for(c,target,pid,raw):
 """Return the snapshot path for this payload, writing a file only when new.

 Snapshots are content addressed by sha256. Every poll used to write a full
 copy even when the endpoint returned byte-identical JSON, which grew
 snapshots/ by roughly 50 MB a day and left more than half the files as exact
 duplicates. Pointing an unchanged run at the identical existing capture
 preserves the evidence chain exactly, because equal hashes mean equal bytes.
 """
 sha=hashlib.sha256(raw).hexdigest()
 existing=c.execute("SELECT snapshot_path FROM monitoring_runs WHERE monitoring_target_id=? AND response_sha256=? AND snapshot_path IS NOT NULL ORDER BY monitoring_run_id DESC LIMIT 1",(target,sha)).fetchone()
 if existing and existing[0] and stored_path(existing[0]).exists():
  return existing[0],sha,False
 path=SNAP/f'{pid}-{STAMP}.json'
 path.write_bytes(raw)
 return str(path.relative_to(ROOT)),sha,True


def poll(c,pid,url,env,key):
 target=ensure_target(c,pid,url); c.execute("INSERT INTO monitoring_runs(monitoring_target_id,started_at,status) VALUES(?,?,'running')",(target,NOW)); run=c.execute('SELECT last_insert_rowid()').fetchone()[0]
 try:status,raw,headers=fetch(pid,url,env); payload=json.loads(raw); current=rows(pid,payload,key)
 except Exception as e:
  c.execute("UPDATE monitoring_runs SET finished_at=?,status='failed',error_summary=? WHERE monitoring_run_id=?",(NOW,str(e)[:500],run)); c.execute("UPDATE monitoring_targets SET last_checked_at=?,consecutive_failures=consecutive_failures+1 WHERE monitoring_target_id=?",(NOW,target)); c.commit(); return {'provider':pid,'status':'failed','error':str(e)}
 snap,sha,is_new=snapshot_for(c,target,pid,raw); sid,cap,_=source_capture(c,pid,url,raw,snap,status)
 source_snapshot_id=ensure_model_source(c,pid,url,status,raw,snap,len(current))
 prior=c.execute("SELECT monitoring_run_id,snapshot_path,response_sha256 FROM monitoring_runs WHERE monitoring_target_id=? AND monitoring_run_id<>? AND status IN ('success','unchanged','changed') ORDER BY monitoring_run_id DESC LIMIT 1",(target,run)).fetchone()
 previous={}
 if prior and prior[1] and stored_path(prior[1]).exists():
  old=json.loads(stored_path(prior[1]).read_text()); previous=rows(pid,old,key)
 added=sorted(set(current)-set(previous)); removed=sorted(set(previous)-set(current)); changed_candidates=sorted(k for k in set(current)&set(previous) if current[k]!=previous[k]); changed=[]
 baseline=prior is None
 if baseline:added=[];removed=[];changed_candidates=[]
 for mid,x in current.items():
  pm=ensure_pm(c,pid,mid,x,source_snapshot_id)
  ensure_aliases(c,pm,x,cap)
  upsert_endpoint_offer(c,pid,pm,x,sid,cap)
  record_endpoint_events(c,pm,x,sid,cap)
  if is_free(pid,x):
   typ='genuine_zero_price' if pid=='openrouter' else 'temporary_free_window'; terms='Endpoint reports zero input/output price' if pid=='openrouter' else 'Official model ID ends in -free; duration unpublished'
   existing=c.execute("SELECT access_offer_id FROM access_offers WHERE provider_model_id=? AND offer_type=? AND ends_at IS NULL",(pm,typ)).fetchone()
   if existing:c.execute('UPDATE access_offers SET last_observed_at=?,last_verified_at=?,evidence_source_id=?,evidence_capture_id=? WHERE access_offer_id=?',(NOW,NOW,sid,cap,existing[0]))
   else:c.execute("INSERT INTO access_offers(provider_model_id,offer_type,first_observed_at,last_observed_at,input_price_per_million_usd,output_price_per_million_usd,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(pm,typ,NOW,NOW,'0' if pid=='openrouter' else None,'0' if pid=='openrouter' else None,terms,sid,cap,'verified' if pid=='openrouter' else 'single_source',NOW))
 for mid in removed:
  row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()
  if row:
   c.execute("UPDATE provider_models_v2 SET endpoint_status='removed',endpoint_removed_at=? WHERE provider_model_id=?",(NOW,row[0])); c.execute("UPDATE access_offers SET ends_at=COALESCE(ends_at,?),last_observed_at=? WHERE provider_model_id=? AND ends_at IS NULL",(NOW,NOW,row[0]))
 for typ,ids in [('model_added',added),('model_removed',removed)]:
  for mid in ids:c.execute("INSERT INTO endpoint_changes(monitoring_run_id,provider_id,change_type,model_identifier,before_json,after_json,detected_at) VALUES(?,?,?,?,?,?,?)",(run,pid,typ,mid,json.dumps(previous.get(mid),sort_keys=True) if mid in previous else None,json.dumps(current.get(mid),sort_keys=True) if mid in current else None,NOW))
 for mid in changed_candidates:
  before=previous[mid];after=current[mid];types=change_types(before,after)
  if not types:continue
  changed.append(mid)
  for typ in types:
   c.execute("INSERT INTO endpoint_changes(monitoring_run_id,provider_id,change_type,model_identifier,before_json,after_json,detected_at) VALUES(?,?,?,?,?,?,?)",(run,pid,typ,mid,json.dumps(before,sort_keys=True),json.dumps(after,sort_keys=True),NOW))
 # Raw payload hashes may change because of volatile timestamps, ordering, or provider metadata.
 # User-visible change status is based on normalized model additions/removals/field changes.
 state=('changed' if (added or removed or changed) else 'unchanged') if prior else 'success'
 c.execute("UPDATE monitoring_runs SET finished_at=?,status=?,http_status=?,response_sha256=?,snapshot_path=?,added_count=?,removed_count=?,changed_count=? WHERE monitoring_run_id=?",(NOW,state,status,sha,snap,len(added),len(removed),len(changed),run))
 c.execute("UPDATE monitoring_targets SET last_checked_at=?,last_success_at=?,last_changed_at=CASE WHEN ?='changed' THEN ? ELSE last_changed_at END,consecutive_failures=0 WHERE monitoring_target_id=?",(NOW,NOW,state,NOW,target)); c.commit()
 return {'provider':pid,'status':state,'models':len(current),'added':len(added),'removed':len(removed),'changed':len(changed)}

def main():
 c=sqlite3.connect(DB);c.execute('PRAGMA foreign_keys=ON');ensure_metadata_schema(c);results=[]
 for pid,(url,env,key) in CONFIG.items():results.append(poll(c,pid,url,env,key))
 print(json.dumps(results,indent=2)); return 1 if any(x['status']=='failed' for x in results) else 0
if __name__=='__main__':raise SystemExit(main())
