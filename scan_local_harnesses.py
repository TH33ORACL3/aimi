#!/usr/bin/env python3
"""Inventory local model harnesses and user ordering without copying secrets.

Only allow-listed, non-secret fields are read from each configuration file.
Credential inventory records environment-variable names and presence, never values.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, sqlite3, subprocess, tomllib
from datetime import datetime, timezone
from pathlib import Path

from aimi_credentials import load_aimi_credentials

load_aimi_credentials()
ROOT=Path(__file__).resolve().parent
DB=ROOT/'free_models.db'
EVIDENCE=ROOT/'evidence'/'local'
VAULT=Path('/Users/TH33_ORACL3/Library/Mobile Documents/iCloud~md~obsidian/Documents/Area 51')
NOW=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
MACHINE='aubrey-macbook'


def ensure_availability_table(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS harness_available_model_entries (
      harness_available_model_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
      installation_id INTEGER NOT NULL REFERENCES harness_installations(installation_id) ON DELETE CASCADE,
      provider_name TEXT,
      model_identifier TEXT NOT NULL,
      display_name TEXT,
      position INTEGER,
      source_path TEXT NOT NULL,
      first_observed_at TEXT NOT NULL,
      last_observed_at TEXT NOT NULL,
      metadata_json TEXT,
      UNIQUE(installation_id,provider_name,model_identifier,source_path)
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_harness_available_order ON harness_available_model_entries(installation_id,position)')


PROVIDER_FACTS={
 'openai-codex':('OpenAI Codex Subscription','https://developers.openai.com/codex/models','https://chatgpt.com/backend-api/codex','openai-responses','OPENAI_API_KEY'),
 'github-copilot':('GitHub Copilot','https://docs.github.com/en/copilot/reference/ai-models/supported-models','https://api.githubcopilot.com','openai-responses',None),
 'opencode-zen':('OpenCode Zen','https://opencode.ai/zen/v1/models','https://opencode.ai/zen/v1','openai-completions','OPENCODE_API_KEY'),
 'opencode-go':('OpenCode Go','https://opencode.ai/zen/go/v1/models','https://opencode.ai/zen/go/v1','openai-completions','OPENCODE_API_KEY'),
 'ollama':('Ollama','http://127.0.0.1:11434/api/tags','http://127.0.0.1:11434/v1','openai-completions',None),
 'ollama-cloud':('Ollama Cloud','https://ollama.com/search','https://ollama.com/v1','openai-completions',None),
 'anthropic':('Anthropic','https://api.anthropic.com/v1/models','https://api.anthropic.com','anthropic-messages','ANTHROPIC_API_KEY'),
 'xai':('xAI','https://api.x.ai/v1/models','https://api.x.ai/v1','openai-completions','XAI_API_KEY'),
 'groq':('Groq','https://api.groq.com/openai/v1/models','https://api.groq.com/openai/v1','openai-completions','GROQ_API_KEY'),
 'huggingface':('Hugging Face','https://huggingface.co/api/models','https://router.huggingface.co/v1','openai-completions','HF_TOKEN'),
 'bedrock':('Amazon Bedrock','https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html','https://bedrock-runtime.{region}.amazonaws.com','aws-bedrock',None),
 'cline':('Cline','https://docs.cline.bot/getting-started/clinepass','https://api.cline.bot/api/v1','openai-completions','CLINE_API_KEY'),
}
ALIASES={'opencode':'opencode-zen','nvidia':'nvidia-nim'}

HARNESS_KNOWN={
 'pi':('Pi CLI','CLI Agent','pi',Path.home()/'.pi/agent/settings.json',Path.home()/'.pi/agent/models.json'),
 'droid':('FactoryAI Droid','CLI Agent','droid',Path.home()/'.factory/settings.json',Path.home()/'.factory/settings.json'),
 'opencode':('OpenCode','CLI Agent','opencode',Path.home()/'.config/opencode/opencode.json',Path.home()/'.config/opencode/opencode.json'),
 'codex-cli':('Codex CLI','CLI Agent','codex',Path.home()/'.codex/config.toml',Path.home()/'.codex/config.toml'),
 'github-copilot-cli':('GitHub Copilot CLI','CLI Agent','copilot',Path.home()/'.copilot/config.json',Path.home()/'.copilot/config.json'),
 'mistral-vibe':('Mistral Vibe CLI','CLI Agent','vibe',Path.home()/'.vibe/config.toml',Path.home()/'.vibe/config.toml'),
 'antigravity-cli':('Antigravity CLI','CLI Agent','agy',Path.home()/'.gemini/antigravity-cli/settings.json',Path.home()/'.gemini/antigravity-cli/settings.json'),
 'cline':('Cline','CLI/IDE Agent','cline',Path.home()/'.cline/data/settings/providers.json',Path.home()/'.cline/data/settings/providers.json'),
 'aside':('Aside Browser Agent','Browser Agent','aside',Path.home()/'.aside/u/0/models.json',Path.home()/'.aside/u/0/models.json'),
 'zcode':('ZCode','Desktop Agent',None,Path.home()/'.zcode/v2/config.json',Path.home()/'.zcode/v2/config.json'),
 'claude-code':('Claude Code','CLI Agent','claude',Path.home()/'.claude',Path.home()/'.claude'),
 'obsidian-warp':('Warp / Oz','CLI Agent',None,Path.home()/'.warp/settings.toml',Path.home()/'.warp/settings.toml'),
 'grok-build':('Grok Build / Grok CLI','CLI Agent','grok',Path.home()/'.grok/config.toml',Path.home()/'.grok/config.toml'),
}

def version(cmd):
    p=shutil.which(cmd)
    if not p:return None,None
    try:
        r=subprocess.run([p,'--version'],capture_output=True,text=True,timeout=8)
        line=(r.stdout or r.stderr).strip().splitlines()[0]
    except Exception: line=None
    return p,line

def source(conn,path,title,harness):
    if not path or not Path(path).is_file(): return None
    raw=Path(path).read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    url='file://'+str(path)
    conn.execute("INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,content_sha256,verification_status,trust_priority,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                 (url,'local_config',harness,title,1,1,NOW,digest,'verified',5,'Local source; secret values are never copied into evidence archives.'))
    return conn.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(url,)).fetchone()[0]

def ensure_provider(conn,pid):
    pid=ALIASES.get(pid,pid)
    if conn.execute('SELECT 1 FROM providers WHERE provider_id=?',(pid,)).fetchone(): return pid
    name,endpoint,base,api,env=PROVIDER_FACTS.get(pid,(pid, f'unknown://{pid}/models',f'unknown://{pid}', 'unknown',None))
    conn.execute("INSERT INTO providers(provider_id,display_name,official_models_endpoint,base_url,api_style,auth_env_var,auth_header,model_id_format,pricing_policy,free_definition,notes,last_verified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                 (pid,name,endpoint,base,api,env,f'Authorization: Bearer ${env}' if env else None,'provider-defined','unknown','Requires official pricing evidence','Added by local harness scanner',NOW))
    return pid

def provider_model(conn,pid,mid,name=None,ctx=None,out=None,metadata=None):
    pid=ensure_provider(conn,pid)
    conn.execute("""INSERT INTO provider_models_v2(provider_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,context_window_tokens,max_output_tokens,provider_metadata_json)
      VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(provider_id,model_identifier) DO UPDATE SET display_name=COALESCE(provider_models_v2.display_name,excluded.display_name),endpoint_last_seen_at=excluded.endpoint_last_seen_at,context_window_tokens=COALESCE(provider_models_v2.context_window_tokens,excluded.context_window_tokens),max_output_tokens=COALESCE(provider_models_v2.max_output_tokens,excluded.max_output_tokens),provider_metadata_json=COALESCE(provider_models_v2.provider_metadata_json,excluded.provider_metadata_json)""",
      (pid,mid,name,'available',NOW,NOW,ctx,out,json.dumps(metadata) if metadata else None))
    return pid,conn.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()[0]

def installation(conn,hid,name,cat,cmd,cfg,source_note=None):
    conn.execute("INSERT OR IGNORE INTO harnesses(harness_id,display_name,vendor,category,config_format,custom_provider_support,source_note_path,notes) VALUES(?,?,?,?,?,?,?,?)",
                 (hid,name,None,cat,None,None,str(source_note) if source_note else None,'Local/second-brain inventory'))
    exe,ver=version(cmd) if cmd else (None,None)
    installed=int(bool(exe or (cfg and Path(cfg).exists())))
    conn.execute("""INSERT INTO harness_installations(harness_id,machine_id,installed,version,executable_path,config_path,status,last_scanned_at)
      VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(harness_id,machine_id) DO UPDATE SET installed=excluded.installed,version=excluded.version,executable_path=excluded.executable_path,config_path=excluded.config_path,status=excluded.status,last_scanned_at=excluded.last_scanned_at""",
      (hid,MACHINE,installed,ver,exe,str(cfg) if cfg else None,'active' if installed else 'historical',NOW))
    return conn.execute('SELECT installation_id FROM harness_installations WHERE harness_id=? AND machine_id=?',(hid,MACHINE)).fetchone()[0]

def add_entry(conn,inst,pid,mid,pos=None,default=False,reason=None,name=None,ctx=None,out=None,src=None,meta=None):
    pid,pmid=provider_model(conn,pid,mid,name,ctx,out,meta)
    conn.execute("""INSERT INTO harness_model_entries(installation_id,provider_id,provider_model_id,configured_provider_name,configured_model_identifier,display_name,position,enabled,is_default,reasoning_level,config_source_path,first_observed_at,last_observed_at,config_metadata_json)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(installation_id,configured_provider_name,configured_model_identifier) DO UPDATE SET provider_model_id=excluded.provider_model_id,display_name=excluded.display_name,position=excluded.position,enabled=excluded.enabled,is_default=excluded.is_default,reasoning_level=excluded.reasoning_level,last_observed_at=excluded.last_observed_at,config_metadata_json=excluded.config_metadata_json""",
      (inst,pid,pmid,pid,mid,name,pos,1,int(default),reason,str(src) if src else None,NOW,NOW,json.dumps(meta) if meta else None))

def add_available(conn,inst,pid,mid,src,pos=None,name=None,meta=None):
    conn.execute('''INSERT INTO harness_available_model_entries(installation_id,provider_name,model_identifier,display_name,position,source_path,first_observed_at,last_observed_at,metadata_json)
      VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(installation_id,provider_name,model_identifier,source_path) DO UPDATE SET display_name=excluded.display_name,position=excluded.position,last_observed_at=excluded.last_observed_at,metadata_json=excluded.metadata_json''',
      (inst,pid,mid,name,pos,str(src),NOW,NOW,json.dumps(meta) if meta else None))
    provider_model(conn,pid,mid,name,metadata=meta)


def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')

def scan_obsidian(conn):
    inv=ROOT/'obsidian-harness-inventory.json'
    if not inv.exists():return
    for row in json.loads(inv.read_text()):
        p=row['properties']; name=p.get('Name') or row['name']; hid='obsidian-'+slug(row['name'])
        rank=p.get('Rank'); stars=p.get('Star Rating')
        conn.execute("INSERT OR IGNORE INTO harnesses(harness_id,display_name,vendor,category,homepage_url,source_note_path,notes) VALUES(?,?,?,?,?,?,?)",
                     (hid,name,p.get('Platform'),p.get('Category','unknown'),p.get('Homepage'),row['path'],p.get('Notes')))
        if rank or stars:
            exists=conn.execute("SELECT 1 FROM user_rankings WHERE subject_type='harness' AND subject_key=? AND ranking_system='obsidian-import' AND source=?",(hid,row['path'])).fetchone()
            if not exists:
                conn.execute("INSERT INTO user_rankings(subject_type,subject_key,ranking_system,rank_value,stars,source,recorded_at,notes) VALUES('harness',?,?,?,?,?,?,?)",
                             (hid,'obsidian-import',float(rank) if rank and rank.replace('.','',1).isdigit() else None,float(stars) if stars and stars.replace('.','',1).isdigit() else None,row['path'],NOW,'Imported from migrated Notion/Obsidian note; ranking meaning preserved as historical preference.'))

def scan_pi(conn):
    path=Path.home()/'.pi/agent/settings.json'; inst=installation(conn,'pi','Pi CLI','CLI Agent','pi',path)
    if not path.exists():return
    source(conn,path,'Pi settings and model order','Pi')
    d=json.loads(path.read_text()); defaultp=d.get('defaultProvider'); defaultm=d.get('defaultModel')
    for pos,x in enumerate(d.get('enabledModels',[]),1):
        if '/' not in x:continue
        pid,mid=x.split('/',1); add_entry(conn,inst,pid,mid,pos,pid==defaultp and mid==defaultm,d.get('defaultThinkingLevel'),src=path)
    models_path=Path.home()/'.pi/agent/models.json'
    if models_path.exists():
        source(conn,models_path,'Pi registered provider/model definitions','Pi')
        models=json.loads(models_path.read_text())
        for pid,p in models.get('providers',{}).items():
            for pos,m in enumerate(p.get('models',[]),1):
                mid=m.get('id')
                if mid:add_available(conn,inst,pid,mid,models_path,pos,m.get('name'),{'base_url':p.get('baseUrl'),'reasoning':m.get('reasoning'),'input':m.get('input')})
    conn.execute("INSERT OR IGNORE INTO model_order_profiles(harness_id,profile_name,description,optimization_goal,max_cycle_distance,active,created_at,updated_at) VALUES('pi','current-local-order','Observed Pi enabledModels order','faithful local snapshot',NULL,1,?,?)",(NOW,NOW))
    profile=conn.execute("SELECT profile_id FROM model_order_profiles WHERE harness_id='pi' AND profile_name='current-local-order'").fetchone()[0]
    conn.execute('DELETE FROM model_order_profile_entries WHERE profile_id=?',(profile,))
    for pos,x in enumerate(d.get('enabledModels',[]),1):
        pid,mid=x.split('/',1); pid=ALIASES.get(pid,pid); provider_model(conn,pid,mid)
        conn.execute('INSERT INTO model_order_profile_entries(profile_id,provider_id,model_identifier,position,role,pinned) VALUES(?,?,?,?,?,?)',(profile,pid,mid,pos,'default' if pid==ALIASES.get(defaultp,defaultp) and mid==defaultm else None,int(pos<=5)))

def scan_droid(conn):
    path=Path.home()/'.factory/settings.json'; inst=installation(conn,'droid','FactoryAI Droid','CLI Agent','droid',path)
    if not path.exists():return
    source(conn,path,'Droid custom model configuration','Droid')
    d=json.loads(path.read_text()); default=d.get('sessionDefaultSettings',{}).get('model')
    for m in d.get('customModels',[]):
        cid=m.get('id',''); parts=cid.split(':'); pid=parts[1] if len(parts)>2 else 'unknown'
        meta={'custom_id':cid,'no_image_support':m.get('noImageSupport'),'adapter':m.get('provider'),'base_url':m.get('baseUrl')}
        add_entry(conn,inst,pid,m['model'],m.get('index'),cid==default,d.get('sessionDefaultSettings',{}).get('reasoningEffort'),m.get('displayName'),None,m.get('maxOutputTokens'),path,meta)
        add_available(conn,inst,pid,m['model'],path,m.get('index'),m.get('displayName'),meta)

def scan_opencode(conn):
    path=Path.home()/'.config/opencode/opencode.json'; inst=installation(conn,'opencode','OpenCode','CLI Agent','opencode',path)
    if not path.exists():return
    source(conn,path,'OpenCode provider configuration','OpenCode')
    d=json.loads(path.read_text())
    for pid,p in d.get('provider',{}).items():
        for pos,(mid,m) in enumerate(p.get('models',{}).items(),1):
            lim=m.get('limit',{}); meta={'base_url':p.get('options',{}).get('baseURL')}
            add_entry(conn,inst,pid,mid,pos,False,None,m.get('name'),lim.get('context'),lim.get('output'),path,meta)
            add_available(conn,inst,pid,mid,path,pos,m.get('name'),meta)

def scan_codex(conn):
    path=Path.home()/'.codex/config.toml'; inst=installation(conn,'codex-cli','Codex CLI','CLI Agent','codex',path)
    if not path.exists():return
    source(conn,path,'Codex CLI configuration','Codex CLI')
    try:d=tomllib.loads(path.read_text())
    except Exception:return
    if d.get('model'): add_entry(conn,inst,'openai-codex',d['model'],1,True,d.get('model_reasoning_effort'),src=path)
    scan_codex_available(conn,inst)

def scan_codex_available(conn,inst):
    path=Path.home()/'.codex/models_cache.json'
    if not path.exists():return
    source(conn,path,'Codex CLI cached available models','Codex CLI')
    try:d=json.loads(path.read_text())
    except Exception:return
    for pos,m in enumerate(d.get('models',[]),1):
        mid=m.get('slug') or m.get('id') or m.get('model')
        if mid:
            local_context = m.get('context_window') or m.get('max_context')
            local_output = m.get('output_token_limit') or m.get('max_output_tokens')
            add_available(conn,inst,'openai-codex',mid,path,pos,m.get('display_name') or m.get('name'),{
                'visibility':m.get('visibility'),
                'fetched_at':d.get('fetched_at'),
                'client_version':d.get('client_version'),
                'context_window_tokens':local_context,
                'max_output_tokens':local_output,
                'observation_scope':'Codex CLI local effective limit; not provider maximum',
            })


def scan_vibe(conn):
    path=Path.home()/'.vibe/config.toml'; inst=installation(conn,'mistral-vibe','Mistral Vibe CLI','CLI Agent','vibe',path)
    if not path.exists():return
    source(conn,path,'Mistral Vibe model configuration','Mistral Vibe')
    try:d=tomllib.loads(path.read_text())
    except Exception:return
    active=d.get('active_model')
    for pos,m in enumerate(d.get('models',[]),1):
        pid=m.get('provider','mistral'); mid=m.get('alias') or m.get('name')
        if mid:
            add_available(conn,inst,pid,mid,path,pos,m.get('name'),{'alias':m.get('alias'),'thinking':m.get('thinking'),'supports_images':m.get('supports_images')})
            if mid==active:add_entry(conn,inst,pid,mid,pos,True,None,m.get('name'),src=path)


def scan_antigravity(conn):
    path=Path.home()/'.gemini/antigravity-cli/settings.json'; inst=installation(conn,'antigravity-cli','Antigravity CLI','CLI Agent','agy',path)
    if not path.exists():return
    source(conn,path,'Antigravity CLI model configuration','Antigravity CLI')
    try:d=json.loads(path.read_text())
    except Exception:return
    mid=d.get('model')
    if mid:
        add_entry(conn,inst,'google-antigravity',mid,1,True,src=path)
        add_available(conn,inst,'google-antigravity',mid,path,1,mid)


def scan_cline(conn):
    path=Path.home()/'.cline/data/settings/providers.json'; inst=installation(conn,'cline','Cline','CLI/IDE Agent','cline',path)
    if not path.exists():return
    source(conn,path,'Cline provider metadata','Cline')
    d=json.loads(path.read_text())
    for pos,(pid,p) in enumerate(d.get('providers',{}).items(),1):
        s=p.get('settings',{}); mid=s.get('model')
        if mid:
            add_entry(conn,inst,pid,mid,pos,pid==d.get('lastUsedProvider'),None,src=path)
            add_available(conn,inst,pid,mid,path,pos,meta={'last_used':pid==d.get('lastUsedProvider')})

def scan_claude_code(conn):
    """Track the explicit Claude Code -> ClinePass launcher without secrets."""
    path = Path.home() / '.claude'
    inst = installation(conn, 'claude-code', 'Claude Code', 'CLI Agent', 'claude', path)
    launcher = Path.home() / 'bin/claude-cline'
    proxy = Path.home() / 'bin/claude-cline-proxy.py'
    if not launcher.exists() or not proxy.exists():
        return
    try:
        launcher_text = launcher.read_text()
        proxy_text = proxy.read_text()
    except OSError:
        return
    client_match = re.search(r'^MODEL="([^"]+)', launcher_text, re.MULTILINE)
    # Proxy is generalized via env overrides; read the default from the call.
    upstream_match = re.search(
        r'^UPSTREAM_MODEL\s*=\s*os\.environ\.get\("CC_PROXY_MODEL",\s*"([^"]+)"\)',
        proxy_text, re.MULTILINE)
    if not upstream_match:
        return
    client_model = client_match.group(1) if client_match else None
    upstream_model = upstream_match.group(1)
    port_match = re.search(
        r'^PORT\s*=\s*int\(os\.environ\.get\("CC_PROXY_PORT",\s*"(\d+)"\)',
        proxy_text, re.MULTILINE)
    metadata = {
        'launcher_path': str(launcher),
        'proxy_path': str(proxy),
        'proxy_base_url': f'http://127.0.0.1:{port_match.group(1)}' if port_match else None,
        'client_model': client_model,
        'upstream_model': upstream_model,
        'route': 'ClinePass subscription',
    }
    add_entry(conn, inst, 'cline', upstream_model, 1, True, None,
              'ClinePass DeepSeek V4 Flash', src=launcher, meta=metadata)
    add_available(conn, inst, 'cline', upstream_model, launcher, 1,
                  'ClinePass DeepSeek V4 Flash', metadata)

    # Second configured route: direct to OpenRouter's Anthropic Messages endpoint.
    or_launcher = Path.home() / 'bin/claude-openrouter'
    if not or_launcher.exists():
        return
    try:
        or_text = or_launcher.read_text()
    except OSError:
        return
    or_model = re.search(r'MODEL="\$\{CLAUDE_OPENROUTER_MODEL:-([^}]+)\}"', or_text)
    base_match = re.search(r'ANTHROPIC_BASE_URL="([^"]+)"', or_text)
    if not or_model:
        return
    model_id = or_model.group(1)
    or_metadata = {
        'launcher_path': str(or_launcher),
        'base_url': base_match.group(1) if base_match else None,
        'route': 'OpenRouter Anthropic Messages (direct, no proxy)',
    }
    add_entry(conn, inst, 'openrouter', model_id, 2, True, None,
              'OpenRouter DeepSeek V4 Flash', src=or_launcher, meta=or_metadata)
    add_available(conn, inst, 'openrouter', model_id, or_launcher, 2,
                  'OpenRouter DeepSeek V4 Flash', or_metadata)

    # Third configured route: FREE OpenCode Zen DeepSeek V4 Flash via the
    # shared translation proxy (OpenAI-style upstream, so a proxy is required).
    zen_launcher = Path.home() / 'bin/claude-opencode'
    if not zen_launcher.exists():
        return
    try:
        zen_text = zen_launcher.read_text()
    except OSError:
        return
    zen_model = re.search(r'^MODEL="([^"]+)"', zen_text, re.MULTILINE)
    zen_port = re.search(r'^PORT=(\d+)', zen_text, re.MULTILINE)
    zen_upstream = re.search(r'CC_PROXY_UPSTREAM_URL="([^"]+)"', zen_text)
    if not zen_model:
        return
    zen_metadata = {
        'launcher_path': str(zen_launcher),
        'proxy_path': str(proxy),
        'proxy_base_url': f'http://127.0.0.1:{zen_port.group(1)}' if zen_port else None,
        'upstream_url': zen_upstream.group(1) if zen_upstream else None,
        'route': 'OpenCode Zen free (via translation proxy)',
    }
    add_entry(conn, inst, 'opencode-zen', zen_model.group(1), 3, True, None,
              'OpenCode Zen DeepSeek V4 Flash Free', src=zen_launcher, meta=zen_metadata)
    add_available(conn, inst, 'opencode-zen', zen_model.group(1), zen_launcher, 3,
                  'OpenCode Zen DeepSeek V4 Flash Free', zen_metadata)


def scan_aside(conn):
    path=Path.home()/'.aside/u/0/models.json'; inst=installation(conn,'aside','Aside Browser Agent','Browser Agent','aside',path)
    if not path.exists():return
    source(conn,path,'Aside custom model configuration','Aside')
    d=json.loads(path.read_text()); pos=0
    for pid,p in d.get('providers',{}).items():
        for m in p.get('models',[]):
            pos+=1; meta={'reasoning':m.get('reasoning'),'input':m.get('input'),'base_url':p.get('baseUrl')}
            add_entry(conn,inst,pid,m['id'],pos,False,None,m.get('name'),m.get('contextWindow'),m.get('maxTokens'),path,meta)
            add_available(conn,inst,pid,m['id'],path,pos,m.get('name'),meta)

def scan_warp(conn):
    path=Path.home()/'.warp/settings.toml'
    binary=Path('/Applications/Warp.app/Contents/MacOS/stable')
    inst=installation(conn,'obsidian-warp','Warp / Oz','CLI Agent',None,path)
    if binary.exists():
        try:
            ver=subprocess.run([str(binary),'--version'],capture_output=True,text=True,timeout=8).stdout.strip()
        except Exception: ver=None
        conn.execute("UPDATE harness_installations SET installed=1,version=?,executable_path=?,config_path=?,status='active',last_scanned_at=? WHERE installation_id=?",(ver,str(binary),str(path),NOW,inst))
    if not binary.exists():return
    try:
        result=subprocess.run([str(binary),'model','list','--output-format','json'],capture_output=True,text=True,timeout=30,check=True)
        models=json.loads(result.stdout)
    except Exception:return
    src='warp://oz-model-list'
    for pos,m in enumerate(models,1):
        mid=m.get('id')
        if not mid:continue
        custom=bool(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',mid,re.I))
        conn.execute('''INSERT INTO harness_available_model_entries(installation_id,provider_name,model_identifier,display_name,position,source_path,first_observed_at,last_observed_at,metadata_json)
          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(installation_id,provider_name,model_identifier,source_path) DO UPDATE SET display_name=excluded.display_name,position=excluded.position,last_observed_at=excluded.last_observed_at,metadata_json=excluded.metadata_json''',
          (inst,'warp-custom' if custom else 'warp-hosted',mid,None if custom else mid,pos,src,NOW,NOW,json.dumps({'custom_uuid':custom,'source':'oz model list'})))


def scan_grok(conn):
    """Scan ~/.grok/config.toml for custom models and reasoning config.

    Grok's config uses [model.<name>] sections with optional api_backend and
    reasoning_effort. The Anthropic Messages API backend (api_backend = "messages")
    enables thinking/reasoning for supported providers like DeepSeek.
    """
    path = Path.home() / '.grok/config.toml'
    inst = installation(conn, 'grok-build', 'Grok Build / Grok CLI', 'CLI Agent', 'grok', path)
    if not path.exists():
        return
    source(conn, path, 'Grok CLI custom model configuration', 'Grok Build')
    try:
        data = tomllib.loads(path.read_text())
    except Exception:
        return

    default_model = data.get('models', {}).get('default')
    global_reasoning = data.get('models', {}).get('default_reasoning_effort')

    # Track what we've scanned so we can add available models for custom entries
    scanned_models = set()

    # In TOML, [model.<name>] sections are nested under the "model" key as a table.
    # Each subsection (e.g. model.deepseek-v4-flash) is a key in the model table.
    model_table = data.get('model', {})
    if not isinstance(model_table, dict):
        print('  Warning: [model] section is not a table')
        return

    for model_key, section in model_table.items():
        if not isinstance(section, dict):
            continue
        full_key = 'model.' + model_key
        mid = section.get('model')
        if not mid:
            continue

        # Determine provider from context or base_url patterns
        base_url = section.get('base_url', '')
        if 'deepseek.com' in base_url:
            pid = 'deepseek'
        elif 'openai.com' in base_url:
            pid = 'openai'
        elif 'anthropic.com' in base_url:
            pid = 'anthropic'
        elif 'openrouter' in base_url:
            pid = 'openrouter'
        elif 'nvidia.com' in base_url:
            pid = 'nvidia-nim'
        elif 'opencode.ai' in base_url:
            pid = 'opencode-zen'
        else:
            pid = 'custom'

        # Determine reasoning level from per-model or global config
        reasoning_level = section.get('reasoning_effort') or global_reasoning
        api_backend = section.get('api_backend', 'chat_completions')

        display_name = section.get('name') or mid
        ctx = section.get('context_window')
        max_tok = section.get('max_completion_tokens')

        meta = {
            'api_backend': api_backend,
            'reasoning_effort': reasoning_level,
            'base_url': base_url,
            'config_key': model_key,
            'has_extra_headers': bool(section.get('extra_headers')),
        }

        # Use the config key as the harness model identifier to distinguish
        # different configurations of the same underlying model.
        harness_mid = model_key
        is_default = (harness_mid == default_model) or (model_key == default_model)

        add_entry(
            conn, inst, pid, harness_mid,
            pos=len(scanned_models) + 1,
            default=is_default,
            reason=reasoning_level,
            name=display_name,
            ctx=ctx,
            out=max_tok,
            src=path,
            meta=meta,
        )
        scanned_models.add(model_key)

        # Also register as available model
        add_available(conn, inst, pid, harness_mid, path, len(scanned_models), display_name, meta)


def scan_zcode(conn):
    # ZCode is a desktop coding harness that persists custom OpenAI-compatible
    # providers in ~/.zcode/v2/config.json under provider.<key> with source=="custom".
    # Each custom provider embeds a literal apiKey, baseURL and a models map.
    path=Path.home()/'.zcode/v2/config.json'
    inst=installation(conn,'zcode','ZCode','Desktop Agent',None,path)
    if not path.exists():return
    source(conn,path,'ZCode custom provider configuration','ZCode')
    try:d=json.loads(path.read_text())
    except Exception:return
    prov=d.get('provider',{})
    pos=0
    for pkey,p in prov.items():
        if not isinstance(p,dict):continue
        if p.get('source')!='custom':continue
        base=(p.get('options',{}) or {}).get('baseURL','')
        # Derive the AIMI provider_id from the baseURL (substring match), since
        # ZCode labels custom providers by a free-form key, not a provider id.
        low=base.lower()
        if 'api.cline.bot' in low: pid='cline'
        elif 'opencode.ai/zen/go/v1' in low: pid='opencode-go'
        elif 'opencode.ai/zen/v1' in low: pid='opencode-zen'
        elif 'integrate.api.nvidia.com' in low: pid='nvidia-nim'
        else: pid='custom'
        for mid,m in p.get('models',{}).items():
            pos+=1
            lim=(m or {}).get('limit',{}); rz=(m or {}).get('reasoning',{}); mods=(m or {}).get('modalities',{})
            meta={'name':p.get('name'),'pkey':pkey,'base_url':base,'enabled':p.get('enabled'),'reasoning_enabled':bool(rz.get('enabled')),'reasoning_variants':rz.get('variants'),'input_modalities':mods.get('input'),'output_modalities':mods.get('output')}
            add_entry(conn,inst,pid,mid,pos,False,rz.get('defaultVariant') if rz else None,p.get('name'),lim.get('context'),lim.get('output'),path,meta)
            add_available(conn,inst,pid,mid,path,pos,p.get('name'),meta)


def scan_credentials(conn):
    mapping={'OPENAI_API_KEY':'openai','ANTHROPIC_API_KEY':'anthropic','GEMINI_API_KEY':'gemini','MISTRAL_API_KEY':'mistral','DEEPSEEK_API_KEY':'deepseek','NVIDIA_API_KEY':'nvidia-nim','AIMI_OPENROUTER_API_KEY':'openrouter','OPENCODE_API_KEY':'opencode-zen','HF_TOKEN':'huggingface','GROQ_API_KEY':'groq','XAI_API_KEY':'xai','CLOUDFLARE_API_TOKEN_AZLABS_AI_WORKERS':'cloudflare-ai','CLINE_API_KEY':'cline'}
    for env,pid in mapping.items():
        pid=ensure_provider(conn,pid)
        conn.execute("INSERT OR REPLACE INTO credential_inventory(provider_id,machine_id,env_var_name,present,source_type,last_checked_at,notes) VALUES(?,?,?,?,?,?,?)",
                     (pid,MACHINE,env,int(bool(os.getenv(env))),'environment',NOW,'Presence only; value never stored.'))

def preferred_pi_order(conn):
    path=Path.home()/'.pi/agent/AGENTS.md'
    if not path.exists():return
    text=path.read_text(); m=re.search(r'## Pi Model List Order\n\nKeep Pi.*?\n\n(.*?)\n\nWithin this list',text,re.S)
    if not m:return
    rows=[]
    for line in m.group(1).splitlines():
        z=re.match(r'\d+\. `([^`]+)`',line.strip())
        if z and '/' in z.group(1):rows.append(z.group(1))
    conn.execute("INSERT OR IGNORE INTO model_order_profiles(harness_id,profile_name,description,optimization_goal,max_cycle_distance,active,created_at,updated_at) VALUES('pi','aubrey-preferred-order','Durable user-approved Pi order','minimize cycling while preserving explicit preference',5,1,?,?)",(NOW,NOW))
    profile=conn.execute("SELECT profile_id FROM model_order_profiles WHERE harness_id='pi' AND profile_name='aubrey-preferred-order'").fetchone()[0]
    conn.execute('DELETE FROM model_order_profile_entries WHERE profile_id=?',(profile,))
    for pos,x in enumerate(rows,1):
        pid,mid=x.split('/',1); pid=ALIASES.get(pid,pid); provider_model(conn,pid,mid)
        conn.execute('INSERT INTO model_order_profile_entries(profile_id,provider_id,model_identifier,position,role,pinned,rationale) VALUES(?,?,?,?,?,?,?)',(profile,pid,mid,pos,'primary' if pos<=5 else 'fallback',int(pos<=5),'Explicit durable user order'))

def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB); conn.execute('PRAGMA foreign_keys=ON')
    ensure_availability_table(conn)
    for pid in PROVIDER_FACTS:ensure_provider(conn,pid)
    scan_obsidian(conn)
    for hid,(name,cat,cmd,cfg,_) in HARNESS_KNOWN.items(): installation(conn,hid,name,cat,cmd,cfg)
    # Preserve historical rows but mark them inactive unless observed again in this scan.
    conn.execute("UPDATE harness_model_entries SET enabled=0 WHERE installation_id IN (SELECT installation_id FROM harness_installations WHERE machine_id=?)",(MACHINE,))
    scan_pi(conn); scan_droid(conn); scan_opencode(conn); scan_codex(conn); scan_cline(conn); scan_claude_code(conn); scan_aside(conn); scan_zcode(conn); scan_vibe(conn); scan_antigravity(conn); scan_grok(conn); scan_warp(conn); scan_credentials(conn); preferred_pi_order(conn)
    conn.commit()
    print(json.dumps({'harnesses':conn.execute('SELECT COUNT(*) FROM harnesses').fetchone()[0],'installations':conn.execute('SELECT COUNT(*) FROM harness_installations').fetchone()[0],'configured_models':conn.execute('SELECT COUNT(*) FROM harness_model_entries').fetchone()[0],'rankings':conn.execute('SELECT COUNT(*) FROM user_rankings').fetchone()[0],'credential_presence_records':conn.execute('SELECT COUNT(*) FROM credential_inventory').fetchone()[0]},indent=2))
if __name__=='__main__':main()
