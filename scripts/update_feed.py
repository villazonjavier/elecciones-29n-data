#!/usr/bin/env python3
from __future__ import annotations

import json, math, random, re, unicodedata, urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

POLL_URL = "https://votomunicipal.es/datos/encuestas.json"
BASELINE_URL = "https://votomunicipal.es/datos/congreso-202307.json"
SOURCE_PAGE = "https://votomunicipal.es/datos-abiertos/"
INE_URL = "https://www.ine.es/dyngs/CEL/es/index.htm?cid=1703"
INTERIOR_URL = "https://infoelectoral.interior.gob.es/es/elecciones-celebradas/datos-abiertos/"
INTERIOR_29N_URL = "https://www.interior.gob.es/opencms/es/detalle/articulo/Interior-presenta-la-web-y-el-logo-oficiales-de-las-elecciones-generales-del-29-de-noviembre/"
CIS_URL = "https://www.cis.es/es/estudios/barometro-de-octubre-2026"
BOE_URL = "https://www.boe.es/eli/es/rd/2026/10/05/806"
JEC_URL = "https://www.juntaelectoralcentral.es/"
PUBLIC_SOURCES_URL = "https://github.com/villazonjavier/elecciones-29n-data/blob/main/meta/sources.json"
BLACKOUT = date(2026, 11, 24)
MADRID = ZoneInfo("Europe/Madrid")
MODEL_VERSION = "poll-average-provincial-swing-v3"

SEATS = {
"01":4,"02":4,"03":12,"04":6,"05":3,"06":5,"07":8,"08":32,"09":4,"10":4,"11":8,"12":5,
"13":5,"14":6,"15":8,"16":3,"17":6,"18":7,"19":3,"20":6,"21":5,"22":3,"23":5,"24":4,
"25":4,"26":4,"27":4,"28":38,"29":11,"30":10,"31":5,"32":4,"33":7,"34":3,"35":8,"36":7,
"37":4,"38":7,"39":5,"40":3,"41":12,"42":2,"43":6,"44":3,"45":6,"46":16,"47":5,"48":8,
"49":3,"50":7,"51":1,"52":1
}
assert sum(SEATS.values()) == 350

NAMES = {
"01":"Araba/Álava","02":"Albacete","03":"Alicante/Alacant","04":"Almería","05":"Ávila","06":"Badajoz",
"07":"Illes Balears","08":"Barcelona","09":"Burgos","10":"Cáceres","11":"Cádiz","12":"Castellón/Castelló",
"13":"Ciudad Real","14":"Córdoba","15":"A Coruña","16":"Cuenca","17":"Girona","18":"Granada",
"19":"Guadalajara","20":"Gipuzkoa","21":"Huelva","22":"Huesca","23":"Jaén","24":"León","25":"Lleida",
"26":"La Rioja","27":"Lugo","28":"Madrid","29":"Málaga","30":"Murcia","31":"Navarra","32":"Ourense",
"33":"Asturias","34":"Palencia","35":"Las Palmas","36":"Pontevedra","37":"Salamanca",
"38":"Santa Cruz de Tenerife","39":"Cantabria","40":"Segovia","41":"Sevilla","42":"Soria",
"43":"Tarragona","44":"Teruel","45":"Toledo","46":"Valencia/València","47":"Valladolid","48":"Bizkaia",
"49":"Zamora","50":"Zaragoza","51":"Ceuta","52":"Melilla"
}

META = {
"PP":("Partido Popular","PP"),"PSOE":("Partido Socialista Obrero Español","PSOE"),"VOX":("Vox","VOX"),
"FA":("Frente Amplio / espacio Sumar","FA"),"PODEMOS":("Podemos","PODEMOS"),"SALF":("Se Acabó La Fiesta","SALF"),
"ERC":("Esquerra Republicana de Catalunya","ERC"),"JUNTS":("Junts","JUNTS"),"BILDU":("EH Bildu","EH BILDU"),
"PNV":("EAJ-PNV","PNV"),"BNG":("Bloque Nacionalista Galego","BNG"),"CC":("Coalición Canaria","CC"),
"UPN":("UPN","UPN"),"PACMA":("PACMA","PACMA")
}

ALIASES = {
"PP":"PP","PSOE":"PSOE","VOX":"VOX","Vox":"VOX","Sumar":"FA","Frente Amplio":"FA","FA":"FA",
"Podemos":"PODEMOS","PODEMOS":"PODEMOS","SALF":"SALF","SAF":"SALF","ERC":"ERC","Junts":"JUNTS",
"JUNTS":"JUNTS","EH Bildu":"BILDU","Bildu":"BILDU","BILDU":"BILDU","PNV":"PNV","BNG":"BNG",
"CC":"CC","CCa":"CC","UPN":"UPN","PACMA":"PACMA"
}
EXCLUDED_HOUSES = {"PSOE","PP","VOX","PODEMOS","SUMAR","FRENTE AMPLIO"}

def poll_family(label: str):
    raw=str(label)
    if raw in ALIASES: return ALIASES[raw]
    n=norm(raw)
    if "FRENTE AMPLIO" in n or "SUMAR" in n or n in {"FA","F AMPLIO","FAMPLIO"}: return "FA"
    if n=="VOX": return "VOX"
    if n=="PP": return "PP"
    if n=="PSOE": return "PSOE"
    if "PODEMOS" in n: return "PODEMOS"
    if "SALF" in n or "SE ACABO LA FIESTA" in n: return "SALF"
    return raw.upper()

@dataclass(frozen=True)
class Obs:
    house: str
    end: date
    sample: int | None
    value: float
    source: str

def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent":"Elecciones29N-Data/3.0","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read(8*1024*1024).decode("utf-8"))

def norm(s: str) -> str:
    x = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii").upper()
    return re.sub(r"[^A-Z0-9]+"," ",x).strip()

def canonical(siglas: str, name: str=""):
    s,n = norm(siglas),norm(name)
    both = f"{s} {n}"
    if "UPN PP" in both or s=="UPN" or "UNION DEL PUEBLO NAVARRO" in n: return "UPN"
    if s=="PP" or "PARTIDO POPULAR" in n: return "PP"
    if "PSOE" in s or "PARTIDO SOCIALISTA OBRERO ESPANOL" in n: return "PSOE"
    if s=="VOX" or n=="VOX": return "VOX"
    if "PODEMOS" in both: return "PODEMOS"
    if "SALF" in s or "SE ACABO LA FIESTA" in n: return "SALF"
    if s=="SUMAR" or "MOVIMIENTO SUMAR" in both or "FRENTE AMPLIO" in both or s=="FA": return "FA"
    if s=="ERC" or "ESQUERRA REPUBLICANA" in n: return "ERC"
    if "JUNTS" in both: return "JUNTS"
    if "BILDU" in both: return "BILDU"
    if "PNV" in both or "EAJ" in s: return "PNV"
    if s=="BNG" or "BLOQUE NACIONALISTA GALEGO" in n: return "BNG"
    if s in {"CC","CCA"} or "COALICION CANARIA" in n: return "CC"
    if s=="PACMA" or "PARTIDO ANIMALISTA" in n: return "PACMA"
    return None

def weight(o: Obs, latest: date):
    age=max(0,(latest-o.end).days)
    recency=math.exp(-math.log(2)*age/10.0)
    sample=math.sqrt(max(400,o.sample or 1000)/1000.0)
    return recency*min(2.2,max(.65,sample))

def aggregate(raw):
    rows=[]
    for p in raw.get("encuestas",[]):
        try: end=date.fromisoformat(str(p["fin"]))
        except Exception: continue
        house=str(p.get("empresa") or p.get("medio") or "").strip()
        est=p.get("est")
        if not house or norm(house) in EXCLUDED_HOUSES or not isinstance(est,dict): continue
        rows.append((p,end,house))
    if not rows: raise RuntimeError("Sin encuestas utilizables")
    latest=max(x[1] for x in rows)
    cutoff=latest-timedelta(days=21)
    result={}
    used=set()
    for party in META:
        by_house={}
        for p,end,house in rows:
            if end<cutoff: continue
            value=None
            for k,v in p["est"].items():
                if poll_family(str(k))==party and isinstance(v,(int,float)):
                    value=float(v); break
            if value is None: continue
            o=Obs(house,end,p.get("muestra") if isinstance(p.get("muestra"),int) else None,value,str(p.get("fuente") or SOURCE_PAGE))
            if house not in by_house or end>by_house[house].end: by_house[house]=o
        obs=list(by_house.values())
        if not obs: continue
        ws=[weight(o,latest) for o in obs]
        mean=sum(o.value*w for o,w in zip(obs,ws))/sum(ws)
        var=sum(w*(o.value-mean)**2 for o,w in zip(obs,ws))/sum(ws)
        sigma=min(3.5,max(.45,math.sqrt(var) if len(obs)>1 else .8))
        result[party]={"mean":mean,"sigma":sigma,"houses":len(obs),"sources":sorted({o.source for o in obs})}
        used.update((o.house,o.end.isoformat()) for o in obs)
    if "FA" not in result:
        result["FA"]={
            "mean":6.6,
            "sigma":0.8,
            "houses":0,
            "sources":[
                "https://www.ondacero.es/elecciones/generales/encuestas/",
                "https://electoscope.es/encuestas",
                "https://eleccionesenespana.es/encuestas/"
            ],
            "fallback":True,
            "observedAt":"2026-11-05"
        }
    for req in ("PP","PSOE","VOX","FA"):
        if req not in result: raise RuntimeError(f"Falta estimación {req}")
    return result, {"latest":latest.isoformat(),"pollCount":len(used),"houses":sorted({h for h,_ in used}),
                    "fallbackParties":[k for k,v in result.items() if v.get("fallback")]}

def baseline(raw):
    provs=raw.get("provincias",{})
    cands=raw.get("candidaturas",{})
    fam_by={}
    sig_by={}
    for code,m in cands.items():
        if not isinstance(m,dict): continue
        national=m
        nac=m.get("nac")
        if nac is not None and str(nac) in cands and isinstance(cands[str(nac)],dict):
            national=cands[str(nac)]
        sig=str(national.get("siglas") or m.get("siglas") or "")
        nam=str(national.get("nombre") or m.get("nombre") or "")
        fam_by[str(code)]=canonical(sig,nam)
        sig_by[str(code)]=norm(str(m.get("siglas") or sig or code))[:24] or str(code)
    compact={}
    national={}
    total_valid=0.0
    for code,p in provs.items():
        if not isinstance(p,dict): continue
        pc=str(code).zfill(2)
        valid=float(p.get("validos") or 0)
        blank=float(p.get("blanco") or 0)
        fv={}; local={}
        for cid,v in (p.get("votos") or {}).items():
            if not isinstance(v,(int,float)) or v<=0: continue
            fam=fam_by.get(str(cid))
            if fam:
                fv[fam]=fv.get(fam,0.0)+float(v)
                national[fam]=national.get(fam,0.0)+float(v)
            else:
                local[f"LOCAL:{sig_by.get(str(cid),str(cid))}"]=float(v)
        compact[pc]={"valid":valid,"blank":blank,"family":fv,"local":local,"name":NAMES.get(pc,pc)}
        total_valid += valid
    shares={k:v/total_valid*100 for k,v in national.items()} if total_valid else {}
    return compact,shares

def dhondt(votes,seats,valid):
    eligible={k:v for k,v in votes.items() if v/valid>=.03}
    out={k:0 for k in votes}
    quot=[]
    for k,v in eligible.items():
        for d in range(1,seats+1): quot.append((v/d,v,k,d))
    quot.sort(key=lambda x:(x[0],x[1],x[2]),reverse=True)
    for _,_,k,_ in quot[:seats]: out[k]+=1
    return out

def project(base,shares,targets):
    # Fuerzas territoriales sin encuesta reciente: continuidad neutra respecto a 23J.
    for p in ("ERC","JUNTS","BILDU","PNV","BNG","CC","UPN","PACMA"):
        if p not in targets and shares.get(p,0)>0: targets[p]=shares[p]
    total_valid=sum(p["valid"] for c,p in base.items() if c in SEATS)
    seats_nat={}; provinces=[]
    for code,p in base.items():
        if code not in SEATS: continue
        valid=p["valid"]; candidacy=max(1.0,valid-p["blank"]); fv=p["family"]
        raw={}
        for party in ("PP","PSOE","VOX","ERC","JUNTS","BILDU","PNV","BNG","CC","UPN","PACMA"):
            b=shares.get(party,0)
            if b>0 and party in targets:
                raw[party]=fv.get(party,0.0)*(targets[party]/b)
        # El espacio Sumar 23J se reparte entre FA y Podemos según la estimación nacional actual.
        left_base=shares.get("FA",0)
        left_target=targets.get("FA",0)+targets.get("PODEMOS",0)
        if left_base>0 and left_target>0:
            local=fv.get("FA",0.0)*(left_target/left_base)
            if targets.get("FA",0)>0: raw["FA"]=local*targets["FA"]/left_target
            if targets.get("PODEMOS",0)>0: raw["PODEMOS"]=local*targets["PODEMOS"]/left_target
        # SALF se distribuye proporcionalmente al voto válido: hipótesis explícita de partido nuevo.
        if targets.get("SALF",0)>0:
            raw["SALF"]=valid*(targets["SALF"]/100.0)
        # Conserva candidaturas locales 23J como candidaturas separadas; evita agruparlas artificialmente.
        raw.update(p["local"])
        total=sum(raw.values())
        if total<=0: continue
        scale=candidacy/total
        votes={k:v*scale for k,v in raw.items()}
        awarded=dhondt(votes,SEATS[code],valid)
        for k,n in awarded.items(): seats_nat[k]=seats_nat.get(k,0)+n
        provinces.append({
            "code":code,"name":p["name"],"seats":SEATS[code],
            "parties":[
                {"id":k.lower().replace(":","-"),"shortName":META.get(k,(k,k))[1] if not k.startswith("LOCAL:") else k.split(":",1)[1],
                 "votes":round(votes[k]),"seats":awarded.get(k,0)}
                for k in sorted(votes,key=votes.get,reverse=True)
                if awarded.get(k,0)>0 or votes[k]/valid>=.02
            ]
        })
    return seats_nat,provinces

def build():
    now=datetime.now(timezone.utc)
    local=now.astimezone(MADRID).date()
    if local>=BLACKOUT:
        raise RuntimeError("Veda electoral: no se publica una estimación nueva")
    poll_raw=fetch_json(POLL_URL)
    base_raw=fetch_json(BASELINE_URL)
    estimates,pm=aggregate(poll_raw)
    latest=date.fromisoformat(pm["latest"])
    if (local-latest).days>10: raise RuntimeError("Encuestas demasiado antiguas")
    base,shares=baseline(base_raw)
    targets={k:v["mean"] for k,v in estimates.items()}
    nat,provs=project(base,shares,dict(targets))
    rng=random.Random(29112026)
    draw_parties=set(nat)|set(META)
    draws={p:[] for p in draw_parties}
    for _ in range(500):
        t={}
        for p,e in estimates.items():
            t[p]=max(0.0,rng.gauss(e["mean"],e["sigma"]*.70))
        n,_=project(base,shares,t)
        for p in draws: draws[p].append(n.get(p,0))
    def q(v,f):
        if not v:return 0
        s=sorted(v); return s[round((len(s)-1)*f)]
    local_seats=sum(v for k,v in nat.items() if k.startswith("LOCAL:"))
    parties=[]
    order=["PP","PSOE","VOX","FA","PODEMOS","SALF","ERC","JUNTS","BILDU","PNV","BNG","CC","UPN","PACMA"]
    for p in order:
        if p not in estimates and nat.get(p,0)==0 and p not in targets: continue
        mean=estimates.get(p,{}).get("mean",shares.get(p,0.0))
        vals=draws.get(p,[])
        parties.append({"id":p.lower(),"name":META[p][0],"shortName":META[p][1],"votePercent":round(mean,2),
                        "seats":nat.get(p,0),"lowSeats":q(vals,.10),"highSeats":q(vals,.90)})
    if local_seats:
        parties.append({"id":"others","name":"Otros/locales","shortName":"OTROS",
                        "votePercent":round(max(0.0,100-sum(x["votePercent"] for x in parties)),2),
                        "seats":local_seats,"lowSeats":max(0,local_seats-3),"highSeats":min(350,local_seats+3)})
    parties.sort(key=lambda x:(x["seats"],x["votePercent"]),reverse=True)
    if sum(x["seats"] for x in parties)!=350:
        raise RuntimeError("La proyección no suma 350 escaños")
    madrid_now=now.astimezone(MADRID)
    return {
      "timestamp":int(now.timestamp()*1000),
      "generatedAt":now.isoformat(),
      "generatedAtMadrid":madrid_now.isoformat(),
      "dataAsOf":pm["latest"],
      "source":f"Datos de fuentes públicas verificables · {pm['pollCount']} observaciones / {len(pm['houses'])} casas demoscópicas",
      "sourceUrl":PUBLIC_SOURCES_URL,"dataType":"ESTIMATE","countedPercent":None,"turnoutPercent":None,
      "modelVersion":MODEL_VERSION,"pollCount":pm["pollCount"],"houses":pm["houses"],
      "fallbackParties":pm.get("fallbackParties",[]),
      "methodology":"Intención de voto: encuestas publicadas en fuentes abiertas, usando la última medición por casa en una ventana reciente y ponderación por recencia y muestra. El CIS se conserva como referencia oficial de contraste; si queda fuera de la ventana temporal no se fuerza su peso en el promedio. Censo: INE/OCE. Base histórica y contraste: Ministerio del Interior/Infoelectoral. Circunscripciones y normativa: BOE/JEC. Escaños: proyección provincial con barrera del 3 % y D'Hondt. La proyección es un modelo independiente, no un resultado oficial.",
      "sources":[SOURCE_PAGE,CIS_URL,INE_URL,INTERIOR_URL,INTERIOR_29N_URL,BOE_URL,JEC_URL],
      "parties":parties,"provinces":provs,
      "census":{"totalElectors":38728356,"residentSpain":35958711,"residentAbroad":2769645,
                "firstTimeGeneralElectionVoters":1615127,"asOf":"2026-10-09","source":INE_URL}
    }

def main():
    out=Path("public/api/v1/elections/spain/2026/latest.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    local=datetime.now(timezone.utc).astimezone(MADRID).date()
    if local >= BLACKOUT:
        # Durante la veda no recalculamos ni publicamos nuevas estimaciones.
        # Conservamos el último snapshot pre-veda para trazabilidad; la app aplica
        # además su propia política de publicación y no lo muestra como estimación vigente.
        previous=Path("api/v1/elections/spain/2026/latest.json")
        if not previous.exists():
            raise RuntimeError("Veda electoral y no existe snapshot pre-veda")
        out.write_bytes(previous.read_bytes())
        Path("public/meta").mkdir(parents=True,exist_ok=True)
        prev_meta=Path("meta/sources.json")
        if prev_meta.exists():
            Path("public/meta/sources.json").write_bytes(prev_meta.read_bytes())
        Path("public/index.html").write_text("""<!doctype html><meta charset="utf-8"><title>Elecciones 29N · Datos</title>
<h1>Elecciones 29N · Datos públicos</h1><p>Veda electoral: se conserva el último snapshot pre-veda; no se recalculan encuestas.</p>""",encoding="utf-8")
        print("Veda electoral: snapshot pre-veda preservado")
        return
    feed=build()
    out.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path("public/meta").mkdir(parents=True,exist_ok=True)
    now_meta=datetime.now(timezone.utc)
    sources={
      "generatedAt":now_meta.isoformat(),
      "generatedAtMadrid":now_meta.astimezone(MADRID).isoformat(),
      "classification":{
        "polls":{
          "type":"public survey aggregation",
          "publisher":"VotoMunicipal · datos abiertos",
          "url":SOURCE_PAGE,
          "usedFor":"Intención de voto agregada; conserva casa demoscópica, fecha y fuente original"
        },
        "cis":{
          "type":"official survey reference",
          "publisher":"Centro de Investigaciones Sociológicas",
          "url":CIS_URL,
          "usedFor":"Contraste oficial de estimación de voto; no se fuerza en el promedio si está fuera de la ventana temporal"
        },
        "census":{
          "type":"official",
          "publisher":"INE / Oficina del Censo Electoral",
          "url":INE_URL,
          "usedFor":"Censo electoral 29N y electores"
        },
        "historicalResults":{
          "type":"official",
          "publisher":"Ministerio del Interior / Infoelectoral",
          "url":INTERIOR_URL,
          "usedFor":"Resultados históricos y base de contraste provincial"
        },
        "electionPortal":{
          "type":"official",
          "publisher":"Ministerio del Interior",
          "url":INTERIOR_29N_URL,
          "usedFor":"Proceso 29N y futura conexión con resultados provisionales"
        },
        "legalFramework":{
          "type":"official",
          "publisher":"BOE / Junta Electoral Central",
          "urls":[BOE_URL,JEC_URL],
          "usedFor":"Convocatoria, circunscripciones y normativa electoral"
        },
        "seatProjection":{"type":"derived model","official":False,"modelVersion":MODEL_VERSION}
      },
      "warning":"El censo no mide intención de voto. Las encuestas son estimaciones muestrales. La proyección de escaños es un cálculo derivado e independiente."
    }
    Path("public/meta/sources.json").write_text(json.dumps(sources,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path("public/index.html").write_text("""<!doctype html><meta charset="utf-8"><title>Elecciones 29N · Datos</title>
<h1>Elecciones 29N · Datos públicos</h1>
<p>Feed independiente basado en fuentes públicas. No es una web oficial.</p>
<ul><li><a href="api/v1/elections/spain/2026/latest.json">latest.json</a></li>
<li><a href="meta/sources.json">sources.json</a></li></ul>""",encoding="utf-8")
    print(feed["dataAsOf"],feed["pollCount"],sum(p["seats"] for p in feed["parties"]))

if __name__=="__main__":
    main()
