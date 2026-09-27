#!/usr/bin/env python3
import base64, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

OUT=Path('config/lever_sites.txt')
SEED=['sambatv','firemon','emburse','extremenetworks','investorflow','wgsn','redoxengine','ppro','tracktik','cents','levelai','360learning','getsquire','revinate','enablecomp','wpromote','mendix','pointclickcare','jumpcloud','brillio-2','pattern','loopreturns']
TOKEN=os.getenv('GITHUB_TOKEN','')
HEAD={'Accept':'application/vnd.github+json','User-Agent':'StackPulse-source-discovery'}
if TOKEN: HEAD['Authorization']=f'Bearer {TOKEN}'

PAT=re.compile(r'https?://jobs\.lever\.co/([A-Za-z0-9_.-]+)',re.I)


def gh_get(url):
    r=requests.get(url,headers=HEAD,timeout=30)
    r.raise_for_status()
    return r.json()


def search_files(query, pages=3):
    for page in range(1,pages+1):
        url='https://api.github.com/search/code'
        try:
            r=requests.get(url,headers=HEAD,params={'q':query,'per_page':100,'page':page},timeout=30)
            if r.status_code in (403, 429):
                print(f'GitHub code search unavailable ({r.status_code}); continuing with known seed list',file=sys.stderr)
                return
            r.raise_for_status()
        except requests.RequestException as e:
            print(f'GitHub code search failed ({e}); continuing with known seed list',file=sys.stderr)
            return
        items=r.json().get('items',[])
        if not items: return
        for item in items:
            yield item
        if len(items)<100: return
        time.sleep(1)


def extract_from_item(item):
    try:
        data=gh_get(item['url'])
        raw=base64.b64decode(data.get('content','')).decode('utf-8','ignore')
        return set(m.group(1).lower() for m in PAT.finditer(raw))
    except Exception as e:
        print('skip',item.get('path'),e,file=sys.stderr)
        return set()


def valid_lever(slug):
    try:
        r=requests.get(f'https://api.lever.co/v0/postings/{slug}?mode=json',timeout=15,headers={'User-Agent':'StackPulse/0.2 source-validator'})
        if r.status_code!=200: return False
        data=r.json()
        return isinstance(data,list) and len(data)>0
    except Exception:
        return False


def main():
    found=set(SEED)
    queries=['"jobs.lever.co/" extension:md','"jobs.lever.co/" extension:json','"jobs.lever.co/" extension:yaml']
    for q in queries:
        for item in search_files(q,pages=2) or []:
            found.update(extract_from_item(item))
            if len(found)>=500: break
        if len(found)>=500: break
    print(f'candidate slugs: {len(found)}',file=sys.stderr)
    # Validation is I/O-bound. Parallelize it with a conservative bound so the
    # discovery phase cannot consume the entire scheduled workflow window.
    candidates=sorted(found)[:500]
    valid=[]
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures={pool.submit(valid_lever, slug): slug for slug in candidates}
        for i,future in enumerate(as_completed(futures), start=1):
            slug=futures[future]
            try:
                if future.result(): valid.append(slug)
            except Exception as e:
                print('skip',slug,e,file=sys.stderr)
            if i%50==0: print(f'validated {i}; active {len(valid)}',file=sys.stderr)
    valid=sorted(valid)[:250]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text('\n'.join(valid)+'\n')
    print(json.dumps({'candidates':len(found),'active':len(valid)},indent=2))


if __name__=='__main__': main()
