window.pofepaReady = (async () => {
  'use strict';
  const payload=JSON.parse(document.getElementById('site-data').textContent);
  const downloads=new Map();
  async function unpack(bytes){return JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());}
  // Base64 to bytes without a per-character callback (the offline archive is ~27 MB).
  function decodeBase64(text){const binary=atob(text),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);return bytes;}
  function fetchData(path){if(!downloads.has(path))downloads.set(path,(async()=>{const requestPath=payload.revision?path+(path.includes('?')?'&':'?')+'data='+payload.revision:path;const response=await fetch(requestPath,{cache:'no-cache'});if(!response.ok)throw new Error('Data download failed: '+response.status);return unpack(await response.arrayBuffer());})().catch(error=>{downloads.delete(path);throw error;}));return downloads.get(path);}
  const db=payload.bootstrap?await fetchData(payload.bootstrap):payload.compressed?await unpack(decodeBase64(payload.compressed)):payload;
  const playerHistories=new Map();
  const playerRankComparisons=new Map();

  const {escape:E,search,pairSearch,stats,h2h}=Pofepa;
  const Evidence=PofepaEvidence;
  const app=document.getElementById('app');
  const map=rows=>new Map(rows.map(r=>[r.id,r]));
  const players=map(db.players), clubs=map(db.clubs), events=map(db.events), sources=map(db.sources);
  const statsByPlayer=new Map(db.players.map(p=>[p.id,p.stats||stats([],p.id)]));
  const matchesByPlayer=new Map();
  for(const m of db.matches) for(const id of [m.p1,m.p2]) { if(!matchesByPlayer.has(id))matchesByPlayer.set(id,[]); matchesByPlayer.get(id).push(m); }
  if(!db.lazy)for(const [id,rows] of matchesByPlayer)statsByPlayer.set(id,stats(rows,id));
  const latestPeriod=db.coverage.ranking_periods.at(-1);
  const latestGeneral=db.snapshots.find(s=>s.region==='national'&&s.period===latestPeriod&&s.list==='ΓΕΝΙΚΟΣ');
  const latestRows=new Map((latestGeneral?.rows||[]).map(r=>[r[0],r]));
  const rosterSnapshot=category=>db.snapshots.find(s=>s.region==='national'&&s.period===latestPeriod&&s.list===(category?category.startsWith('ΓΥΝ')?'ΓΥΝΑΙΚΩΝ':category:'ΓΕΝΙΚΟΣ'));
  let lang='el';try{lang=localStorage.getItem('pofepa-lang')==='en'?'en':'el';}catch{}
  const L=(el,en)=>lang==='el'?el:en;
  const num=(v,digits=0)=>v==null?'—':new Intl.NumberFormat(lang==='el'?'el-GR':'en-GB',{maximumFractionDigits:digits}).format(v);
  const percent=v=>v==null?'—':num(v*100,1)+'%';
  const datefmt=value=>value?new Intl.DateTimeFormat(lang==='el'?'el-GR':'en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value+'T12:00:00Z')):'—';
  const month=value=>new Intl.DateTimeFormat(lang==='el'?'el-GR':'en-GB',{month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value+'-01T12:00:00Z'));
  const regionName=r=>({national:L('Πανελλαδικά','Nationwide'),south:L('Αττική & Νότια Ελλάδα','Attica & South Greece'),north:L('Βόρεια Ελλάδα','North Greece'),multi:L('Πολλαπλές περιφερειακές πηγές','Multiple regional sources')}[r]||'');
  const competitionRegions=[...(db.competition_regions||[]),{id:'unspecified',el:'Χωρίς καθορισμένη περιφέρεια',en:'Region not specified'}];
  const competitionRegionName=id=>{const region=competitionRegions.find(r=>r.id===id);return region?L(region.el,region.en):'';};
  // Where a competition is played, from the results-site grouping. Ranking-source
  // regions describe which workbook a row came from, so they are only a fallback.
  const eventPlace=(e,fallback)=>{const r=e?.competition_region;return r&&r!=='unspecified'?(r==='nationwide'?regionName('national'):competitionRegionName(r)):fallback;};
  const eventTitle=e=>e.competition_type==='cup'&&!search(e.name,'κυπελλ')?L('Κύπελλο · ','Cup · ')+e.name:e.name;
  const typeName=t=>t==='BET'?L('Βετεράνοι','Veterans'):t==='ANE'?L('Ανεξάρτητοι','Independent'):t==='WOMEN'?L('Γυναίκες','Women'):L('Γενικός πίνακας','Overall ranking');
  const listName=s=>/^BET |^ANE /.test(s)?typeName(s.split(' ')[0])+' · '+s.slice(4):s==='ΓΥΝΑΙΚΩΝ'?L('Γυναίκες · όλες οι ηλικίες','Women · all ages'):s==='ΓΕΝΙΚΟΣ'?L('Γενικός πίνακας','Overall ranking'):s;
  const navItems=[['home','Αρχική','Overview'],['matches','Αγώνες','Matches'],['players','Αθλητές','Players'],['rankings','Κατατάξεις','Rankings'],['events','Διοργανώσεις','Events'],['h2h','Σύγκριση','Head to head']];
  function route(){const [path,query='']=(location.hash.slice(1)||'home').split('?');const [requestedName,rawId]=path.split('/');const name=requestedName==='teams'?'events':requestedName;const params=new URLSearchParams(query),redirect=id=>db.player_redirects?.[id]||id;const id=name==='player'?redirect(rawId):rawId;for(const k of ['p1','p2'])if(params.has(k))params.set(k,redirect(params.get(k)));return {name,id,params};}
  let current=route();
  const param=(name,fallback='')=>current.params.get(name)||fallback;
  const href=(path,params={})=>'#'+path+(Object.keys(params).length?'?'+new URLSearchParams(params):'');
  const link=(path,text,params={})=>`<a href="${E(href(path,params))}">${E(text)}</a>`;
  const pLink=id=>link('player/'+id,players.get(id)?.name||id);
  const cLink=id=>clubs.has(id)?link('team/'+id,clubs.get(id).name):'—';
  function external(url,text,cls='source-link'){return /^https?:\/\//.test(url||'')?`<a class="${cls}" href="${E(url)}" target="_blank" rel="noopener noreferrer">${E(text)}</a>`:'—';}
  const sourceLink=(id,row)=>external(sources.get(id)?.url,L('Πηγή','Source')+(row?' · '+row:''));
  const empty=text=>`<div class="empty">${E(text||L('Δεν βρέθηκαν εγγραφές για αυτά τα φίλτρα.','No records match these filters.'))}</div>`;
  const table=(heads,body)=>`<div class="table-wrap"><table><thead><tr>${heads.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
  const field=(name,label,value,placeholder='')=>`<div class="field grow"><label for="filter-${name}">${E(label)}</label><input id="filter-${name}" data-filter="${name}" type="search" value="${E(value)}" placeholder="${E(placeholder)}" autocomplete="off"></div>`;
  function select(name,label,options,value){return `<div class="field"><label for="filter-${name}">${E(label)}</label><select id="filter-${name}" data-filter="${name}">${options.map(([v,t])=>`<option value="${E(v)}" ${v===value?'selected':''}>${E(t)}</option>`).join('')}</select></div>`;}
  const all=L('Όλα','All');
  function pageHead(title,description='',actions=''){return `<div class="page-head"><div><div class="eyebrow">POFEPA STATS</div><h1>${E(title)}</h1>${description?`<p>${E(description)}</p>`:''}</div>${actions}</div>`;}
  function breadcrumb(label,path){return `<div class="breadcrumb">${link(path,label)} / ${L('Στοιχεία','Details')}</div>`;}
  function paged(rows,render,pageKey="page",pageSize=40,countLabel=L('εγγραφές','records')){const page=Math.min(Math.max(0,Number(param(pageKey))||0),Math.max(0,Math.ceil(rows.length/pageSize)-1));const start=page*pageSize;
    return `<div class="count" role="status">${num(rows.length)} ${E(countLabel)}</div><div class="panel">${rows.length?render(rows.slice(start,start+pageSize)):empty()}${rows.length>pageSize?`<div class="pager"><span>${num(start+1)}–${num(Math.min(start+pageSize,rows.length))} / ${num(rows.length)}</span><div><button data-page="${page-1}" data-page-key="${pageKey}" ${page===0?'disabled':''}>${L('Προηγούμενα','Previous')}</button><button data-page="${page+1}" data-page-key="${pageKey}" ${start+pageSize>=rows.length?'disabled':''}>${L('Επόμενα','Next')}</button></div></div>`:''}</div>`;}
  function metric(value,label,cls=''){return `<div class="metric ${cls}"><strong>${value}</strong><span>${E(label)}</span></div>`;}
  function statCards(s){return `<div class="metric-grid">${metric(num(s.played),L('Αγώνες','Matches'))}${metric(num(s.wins),L('Νίκες','Wins'),'win')}${metric(num(s.losses),L('Ήττες','Losses'),'loss')}${metric(percent(s.winRate),L('Ποσοστό νικών','Win rate'))}</div>`;}
  // Each player's games sit beside the name in one row, so they stay aligned when a long name wraps.
  function matchTable(rows,player=''){return '<div class="match-table">'+table([L('Ημερομηνία','Date'),L('Αθλητές','Players')+' · '+L('Σετ','Games'),L('Διοργάνωση','Competition'),L('Τεκμηρίωση','Evidence')],rows.map(m=>{
    const ids=player&&m.p2===player?[m.p2,m.p1]:[m.p1,m.p2];const scores=ids[0]===m.p1?m.score:[...m.score].reverse();
    const event=events.get(m.event);return `<tr><td>${datefmt(m.date)}<span class="meta">${E(eventPlace(event,(m.regions||[m.region]).map(regionName).join(" · ")))}</span></td><td class="match-players">${ids.map((id,i)=>`<a class="${scores[i]>scores[1-i]?'winner':''}" href="#player/${E(id)}"><span>${E(players.get(id)?.name||id)}</span><span class="set-score">${scores[i]}</span></a>`).join('')}</td><td>${link('event/'+m.event,event.name)}<span class="meta">${event.season}</span></td><td>${[...(m.evidence||[{source:m.source,row:m.row}]),...(m.document_evidence||[])].map(e=>sourceLink(e.source,e.row)).join("<br>")}${Evidence.render(m,{lang,escape:E,playerName:id=>players.get(id)?.name||id,sourceLink,datefmt})}</td></tr>`;}).join(''))+'</div>';}
  function fixtureTable(rows,{showRound=true}={}){return table([...(showRound?[L('Αγωνιστική','Round')]:[]),L('Γηπεδούχος','Home team'),L('Σκορ','Score'),L('Φιλοξενούμενος','Away team'),L('Ημερομηνία / ορισμός','Date / deadline'),L('Πηγή','Source')],rows.map(f=>`<tr>${showRound?`<td>${E(f.round)}</td>`:''}<td class="player-cell">${cLink(f.clubs[0])}</td><td class="score">${f.score?f.score.join(' – '):'—'}</td><td class="player-cell">${cLink(f.clubs[1])}</td><td>${f.date?datefmt(f.date):E(f.deadline)||'—'}<span class="meta">${E(f.schedule_note)}</span></td><td>${f.sheet_url?external(f.sheet_url,L('Φύλλο αγώνα','Match sheet')):sourceLink(f.source)}${f.page?'<span class="meta">'+(/\.pdf$/i.test(sources.get(f.source)?.url)?'PDF · '+f.page:L('Εικόνα','Image'))+'</span>':''}${f.rubbers?rubberDetails(f.rubbers):''}</td></tr>`).join(''));}
  function fixturesByRound(rows){
    const groups=Pofepa.fixtureRounds(rows);
    return `<p class="chart-note">${num(rows.length)} ${L('ομαδικές συναντήσεις · Ομαδοποίηση ανά αγωνιστική, με τη σειρά της πηγής.','team fixtures · Grouped by round, in source order.')}</p>`+
      paged(groups,items=>items.map((group,index)=>{
        const label=!group.label?L('Δεν αναφέρεται αγωνιστική','Round not specified'):/^PDF\b/i.test(group.label)?L('Δεν αναφέρεται αγωνιστική','Round not specified')+' · '+group.label:group.label;
        return `<section class="fixture-round" aria-labelledby="fixture-round-${index}"><div class="round-heading"><h2 id="fixture-round-${index}" tabindex="-1">${E(label)}</h2><span>${num(group.rows.length)} ${L('συναντήσεις','fixtures')}</span></div>${fixtureTable(group.rows,{showRound:false})}</section>`;
      }).join(''),'page',4,L('αγωνιστικές / φάσεις','rounds / stages'));
  }
  function cupDraw(e,rows){
    const draw=db.cup_draws?.[e.id];
    if(!draw)return historicalCup(rows);
    return `<section class="cup-draw" aria-labelledby="cup-draw-title"><div class="section-title"><h2 id="cup-draw-title">${L('Ταμπλό κυπέλλου','Cup draw')}</h2></div><p class="chart-note">${L('Η αρχική κλήρωση, με τις προκρίσεις, τα BYE και τον τελικό όπως δημοσιεύθηκαν. Μετακινηθείτε οριζόντια για να ακολουθήσετε την πορεία κάθε ομάδας.','The original draw, with advancement, byes and the final as published. Scroll horizontally to follow each team’s path.')}</p>`+
      draw.pages.map((page,index)=>`<figure class="panel draw-page"><figcaption class="draw-toolbar"><strong>${L('Ταμπλό','Draw')} ${num(index+1)} / ${num(draw.pages.length)}</strong><div class="draw-controls"><label for="draw-zoom-${index}">${L('Προβολή','View')}</label><select id="draw-zoom-${index}" data-draw-zoom="${index}"><option value="fit">${L('Προσαρμογή πλάτους','Fit width')}</option><option value="1.4" selected>${L('Ανάγνωση','Reading size')}</option><option value="2">${L('Μεγέθυνση','Enlarge')}</option></select><button class="button secondary" data-draw-end="${index}">${L('Κύλιση δεξιά →','Scroll right →')}</button>${sourceLink(page.source)}</div></figcaption><div class="draw-viewport" id="draw-viewport-${index}" tabindex="0" role="region" aria-label="${L('Ταμπλό κυπέλλου, οριζόντια κύλιση','Cup draw, horizontally scrollable')} ${index+1}"><div class="draw-canvas" id="draw-canvas-${index}" data-width="${page.width}" style="width:${Math.round(page.width*1.4)}px"><img id="draw-image-${index}" class="draw-image" width="${page.width}" height="${page.height}" src="data:image/svg+xml,${E(encodeURIComponent(page.svg))}" alt="${E(eventTitle(e))} · ${E(e.season)} · ${L('πρωτότυπο ταμπλό, σελίδα','original draw, page')} ${page.page}" ${index?'loading="lazy"':''}>${(page.links||[]).map((link,li)=>`<a class="draw-link" href="${E(link.url)}" target="_blank" rel="noopener noreferrer" style="left:${link.bbox[0]/page.width*100}%;top:${link.bbox[1]/page.height*100}%;width:${(link.bbox[2]-link.bbox[0])/page.width*100}%;height:${(link.bbox[3]-link.bbox[1])/page.height*100}%" aria-label="${L('Φύλλο αγώνα','Match sheet')} ${li+1}" title="${L('Άνοιγμα φύλλου αγώνα','Open match sheet')}"></a>`).join('')}</div></div></figure>`).join('')+
      `</section><details class="panel panel-pad cup-results"><summary>${L('Αποτελέσματα συναντήσεων','Match results')} (${num(rows.length)})</summary>${rows.length?fixtureTable(rows,{showRound:false}):empty(L('Δεν έχουν δημοσιευθεί αποτελέσματα.','No results published yet.'))}</details>`;
  }
  function historicalCup(rows){
    const bracket=Pofepa.cupBracket(rows),rounds=bracket.rounds;
    const height=Math.max(1,...rounds.map(r=>r.matches.length))*116+70,positions=new Map();
    rounds.forEach((r,col)=>r.matches.forEach((m,i)=>positions.set(m.fixture.id,{x:col*292+16,y:54+(i+.5)*(height-70)/r.matches.length-46})));
    let edges=rounds.flatMap(r=>r.matches.flatMap(m=>m.feeders.map((id,slot)=>{
      const a=positions.get(id),b=positions.get(m.fixture.id);if(!a||!b)return '';
      const x=a.x+244,y=a.y+46,end=b.y+23+slot*44;
      return `<path d="M${x} ${y} H${x+16} V${end} H${b.x}"/>`;
    }))).join('');
    if(bracket.champion){const final=rounds.at(-1)?.matches.find(m=>m.winner===bracket.champion),p=final&&positions.get(final.fixture.id);if(p)edges+=`<path d="M${p.x+244} ${p.y+46} H${rounds.length*292+16}"/>`;}
    const champion=bracket.champion?`<section class="cup-champion" style="left:${rounds.length*292+16}px;top:${height/2-20}px"><h3>${L('Κυπελλούχος','Cup winner')}</h3>${cLink(bracket.champion)}</section>`:'';
    const board=rounds.length?`<section class="panel" aria-labelledby="cup-draw-title"><div class="draw-toolbar"><h2 id="cup-draw-title">${L('Ταμπλό κυπέλλου','Cup draw')}</h2><span class="chart-note">${L('Προκρίσεις από τα δημοσιευμένα αποτελέσματα. Οριζόντια κύλιση →','Advancement from published results. Scroll horizontally →')}</span></div><div class="draw-viewport" tabindex="0" role="region" aria-label="${L('Γύροι κυπέλλου','Cup rounds')}"><div class="knockout-board" style="width:${(rounds.length+(bracket.champion?1:0))*292+16}px;height:${height}px"><svg class="knockout-lines" width="100%" height="100%" aria-hidden="true">${edges}</svg>${rounds.map((round,col)=>`<section aria-label="${E(round.label)}"><h3 class="knockout-round" style="left:${col*292+16}px">${E(round.label)}</h3>${round.matches.map(m=>{const f=m.fixture,p=positions.get(f.id);return `<article class="knockout-match" style="left:${p.x}px;top:${p.y}px" aria-label="${E(f.home+' / '+f.away)}">${f.clubs.map((id,i)=>`<div class="knockout-team ${m.winner===id?'winner':''}"><span>${cLink(id)}</span><strong>${f.score?f.score[i]:'—'}</strong></div>`).join('')}<span class="knockout-source">${m.bye?'BYE · ':''}${f.sheet_url?external(f.sheet_url,L('Φύλλο αγώνα','Match sheet')):sourceLink(f.source)}</span></article>`;}).join('')}</section>`).join('')}${champion}</div></div></section>`:'';
    const stages=(items,label)=>items.length?`<section class="panel"><div class="round-heading"><h2>${label}</h2></div>${items.map(g=>`<h3 class="cup-stage">${E(g.label)}</h3>${fixtureTable(g.rows,{showRound:false})}`).join('')}</section>`:'';
    return board+stages(bracket.placement,L('Αγώνες κατάταξης','Placement matches'))+stages(bracket.groups,L('Φάση ομίλων','Group stage'));
  }
  function rubberDetails(rows){return `<details><summary>${L('Επιμέρους αγώνες','Individual results')} (${rows.length})</summary>${rows.map(r=>`<p>${r.status==='walkover'?E(r.names.join(' / '))+' ('+L('άνευ αγώνα','walkover')+')':r.kind==='singles'?r.players.map(pLink).join(' / '):E((r.home||r.names||[]).join(' / '))+' — '+E((r.away||[]).join(' / '))+' ('+L('διπλό','doubles')+')'} <b>${r.score.join('–')}</b></p>`).join('')}</details>`;}
  function matchSheetCoverage(){
    const c=db.coverage.match_sheets;if(!c)return '';
    const rows=[...c.reviews].sort((a,b)=>b.date.localeCompare(a.date));
    return `<section class="panel panel-pad"><h2>${L('Φύλλα αγώνων · πρόοδος εισαγωγής','Match sheets · import progress')}</h2>
      <p>${num(c.reviewed)} / ${num(c.linked)} ${L('συνδεδεμένα φύλλα ελέγχθηκαν, με προτεραιότητα στα νεότερα.','linked sheets reviewed, prioritising the newest.')}</p>
      <p>${num(c.imported_sheets??c.reviews.length)} ${L('φύλλα εισήχθησαν','sheets imported')} · ${num(c.held||0)} ${L('χρειάζονται διευκρίνιση','need clarification')} · ${num(c.pending)} ${L('δεν έχουν ακόμη ελεγχθεί','not yet reviewed')}</p>
      <p>${num(c.imported)} ${L('νέοι ατομικοί αγώνες','new singles matches')} · ${num(c.corroborated)} ${L('επιβεβαιωμένοι υπάρχοντες','existing results confirmed')} · ${num(c.excluded_walkovers)} ${L('άνευ αγώνα εξαιρέθηκαν','walkovers excluded')}</p>
      ${c.unavailable?`<p>${num(c.unavailable)} ${L('φύλλα δεν είναι διαθέσιμα στον διακομιστή της πηγής','sheets are unavailable on the source server')}</p>`:''}
      ${Object.entries(c.seasons||{}).slice(0,2).map(([season,s])=>`<p><strong>${E(season)}</strong>: ${num(s.reviewed)} / ${num(s.linked)} ${L('ελεγμένα','reviewed')} · ${num(s.accepted)} ${L('εισήχθησαν','imported')} · ${num(s.held)} ${L('χρειάζονται διευκρίνιση','need clarification')} · ${num(s.pending)} ${L('σε αναμονή ελέγχου','awaiting review')}${s.unavailable?` · ${num(s.unavailable)} ${L('μη διαθέσιμα','unavailable')}`:''}</p>`).join('')}
      ${c.excluded_team_walkovers?`<p>${num(c.excluded_team_walkovers)} ${L('ομαδικοί αγώνες δεν διεξήχθησαν · χωρίς προσθήκη ατομικών αποτελεσμάτων','team fixtures were not played · no individual results added')}</p>`:''}
      <p>${L('Οι χειρόγραφες ταυτότητες ελέγχονται με τον ΔΑΙ, το όνομα, την ομάδα και τις προηγούμενες πηγές. Οι κατατάξεις παραμένουν όπως δημοσιεύονται στους επίσημους πίνακες.','Handwritten identities are checked against registration numbers, names, teams and previous sources. Rankings remain as published in the official lists.')}</p>
      ${c.issues?.length?`<details><summary>${L('Φύλλα που χρειάζονται διευκρίνιση','Sheets needing clarification')} (${c.issues.length})</summary>${table([L('Φύλλο αγώνα','Match sheet'),L('Εκκρεμότητα','Outstanding issue')],c.issues.map(r=>`<tr><td>${external(r.url,decodeURIComponent(r.url.split('/').at(-1)))}</td><td>${E(L(r.details_el||r.details,r.details))}</td></tr>`).join(''))}</details>`:''}
      </section><div class="section-title"><h3 id="about-sheet-list" tabindex="-1">${L('Ελεγμένα φύλλα αγώνων','Reviewed match sheets')}</h3></div>`+
      paged(rows,rs=>table([L('Ημερομηνία','Date'),L('Φύλλο αγώνα','Match sheet'),L('Νέοι αγώνες','New matches'),L('Ήδη στο αρχείο','Already archived')],rs.map(r=>`<tr><td>${datefmt(r.date)}</td><td>${external(r.url,fileName(r.url))}</td><td>${r.imported||0}</td><td>${r.corroborated||0}</td></tr>`).join('')),'sheetpage',ABOUT_PAGE_SIZE,L('φύλλα','sheets'));
  }
  function documentReviews(){const rows=db.coverage.document_reviews||[];const labels={results_imported:L('Εισήχθησαν αποτελέσματα','Results imported'),standings_only:L('Μόνο βαθμολογίες ομάδων','Team standings only'),no_reported_results:L('Δεν δημοσιεύονται σκορ','No reported scores'),source_conflict:L('Αντιφατικές ονομασίες στην πηγή','Conflicting team labels in source')};return `<div class="section-title"><h2 id="about-documents" tabindex="-1">${L('Έλεγχος PDF και εικόνων','PDF and image review')}</h2></div><p class="muted">${num(rows.length)} ${L('αρχεία ελέγχθηκαν. Τα ομαδικά σκορ δεν προσμετρώνται ως ατομικοί αγώνες. Οι εικόνες βαθμολογίας δεν δίνουν αποτελέσματα συγκεκριμένων συναντήσεων.','documents reviewed. Team scores do not count as singles matches. Standings images do not provide individual fixture results.')}</p>`+
      paged(rows,rs=>table([L('Πηγή','Source'),L('Περίοδος','Season'),L('Αποτελέσματα','Results'),L('Έλεγχος','Review')],rs.map(r=>`<tr><td>${external(r.url,fileName(r.url))}</td><td>${E(r.season)}</td><td>${num(r.fixtures||0)}</td><td>${E(labels[r.review_status]||r.review_status)}${r.review_issues?.length?'<span class="meta">'+r.review_issues.length+' '+L('σκορ εξαιρέθηκαν','scores omitted')+'</span>':''}</td></tr>`).join('')),'docpage',ABOUT_PAGE_SIZE,L('αρχεία','documents'));}
  // compact (home card): one category is named above the table, so its column is dropped and ranks become chips.
  function rankingTable(rows,snapshot,{compact=false}={}){return table(['#',L('Αθλητής','Player'),L('Ομάδα στην πηγή','Team in source'),L('Βαθμοί','Points'),...(compact?[]:[L('Κατηγορία','Category')])],rows.map(r=>`<tr><td class="rank-num ${r[1]!==null&&r[1]<=3?'rank-top':''}">${compact?`<span class="rank-chip">${r[1]??'—'}</span>`:r[1]??'—'}</td><td class="player-cell">${pLink(r[0])}<span class="meta">${players.get(r[0]).registration?L('ΔΑΙ','ID')+' '+E(players.get(r[0]).registration):L('Χωρίς ΔΑΙ στην πηγή','No source registration')}</span></td><td class="team-cell">${cLink(r[3])}</td><td class="number"><b>${num(r[2],3)}</b></td>${compact?'':`<td><span class="badge neutral">${E(r[4])}</span></td>`}</tr>`).join(''));}
  function home(){const bracket=db.snapshots.find(s=>s.region==='national'&&s.period===latestPeriod&&s.list==='BET 40-49');
    const latestEvents=db.events.filter(e=>e.kind==='singles'&&e.region==='national').slice(0,4);
    const chevron='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 3 5 5-5 5"/></svg>';
    return `<section class="hero"><div class="wrap"><div class="hero-grid"><div><div class="eyebrow">${L('ΤΟ ΑΡΧΕΙΟ ΤΟΥ ΠΟΦΕΠΑ','THE POFΕPA ARCHIVE')}</div><h1>${L('Κάθε αγώνας.<br><span>Η δική σου διαδρομή.</span>','Every match.<br><span>Your table tennis story.</span>')}</h1><p>${L('Αγώνες, αθλητές και κατατάξεις ανά ηλικία και περιοχή. Εξερεύνησε τα αποτελέσματα πίσω από τους αριθμούς.','Matches, players and rankings by age and region. Explore the results behind the numbers.')}</p><form id="home-search" class="hero-search"><input name="q" aria-label="${L('Αναζήτηση αθλητή','Search players')}" placeholder="${L('Όνομα αθλητή ή αριθμός ΔΑΙ…','Player name or registration number…')}" required><button class="primary">${L('Αναζήτηση','Search')}</button></form></div><div class="stats-band">${[[db.coverage.matches,L('Εισαγμένοι ατομικοί αγώνες','Imported singles matches')],[db.coverage.ranked_players,L('Προφίλ σε κατατάξεις','Ranked profiles')],[db.coverage.reported_fixtures,L('Ομαδικά αποτελέσματα','Reported team results')],[db.coverage.ranking_periods.length,L('Μήνες κατάταξης','Ranking months')]].map(([n,t])=>`<div class="stat"><strong>${num(n)}</strong><span>${t}</span></div>`).join('')}</div></div></div></section><main id="main" class="wrap main"><aside class="latest-ranking"><div><small>${L('ΤΕΛΕΥΤΑΙΑ ΠΑΝΕΛΛΑΔΙΚΗ ΚΑΤΑΤΑΞΗ','LATEST NATIONAL RANKING')}</small><div class="big-date">${month(latestPeriod)}</div></div><p>${L('Βετεράνοι & ανεξάρτητοι, ανά ηλικιακή κατηγορία. Ιστορικοί πίνακες Βόρειας και Νότιας Ελλάδας.','Veterans & independent players, by age bracket. Historical North and South Greece rankings.')}</p><a class="button" href="#rankings">${L('Εξερεύνηση κατατάξεων','Explore rankings')}</a></aside><div class="grid-two"><section class="panel home-card home-ranking"><div class="card-head"><div><h2>${L('Κατάταξη ηλικιακής κατηγορίας','Age-bracket ranking')}</h2><p class="muted">${L('Πανελλαδικά · Βετεράνοι 40–49','Nationwide · Veterans 40–49')} · ${month(latestPeriod)}</p></div>${link('rankings',L('Όλοι οι πίνακες','All rankings'))}</div>${rankingTable(bracket.rows.slice(0,6),bracket,{compact:true})}</section><section class="panel home-card"><div class="card-head"><div><h2>${L('Διοργανώσεις','Competitions')}</h2><p class="muted">${L('Αγωνιστική περίοδος 2026–2027','2026–2027 season')}</p></div>${link('events',L('Όλες','View all'))}</div>${latestEvents.map(e=>`<a class="event-row" href="${E(href('event/'+e.id))}"><span><h3>${E(e.name)}</h3><small>${E(eventPlace(e,regionName(e.region)))} · ${num(e.match_count??db.matches.filter(m=>m.event===e.id).length)} ${L('αγώνες στο αρχείο','archived matches')}</small></span>${chevron}</a>`).join('')}</section></div><section class="panel home-card"><div class="card-head"><h2>${L('Πρόσφατα αποτελέσματα στο αρχείο','Latest archived results')}</h2>${link('matches',L('Όλοι οι αγώνες','All matches'))}</div>${matchTable(db.matches.slice(0,6))}</section><p class="chart-note">${L('Έλεγχος πηγών','Sources checked')}: ${datefmt(db.coverage.as_of)} · ${L('Ατομικά αποτελέσματα έως','Singles results through')}: ${datefmt(db.coverage.match_date_max)}</p></main>`;
  }
  function rankings(){
    const region=param('region','national');const periods=[...new Set(db.snapshots.filter(s=>s.region===region).map(s=>s.period))].sort().reverse();
    const period=periods.includes(param('period'))?param('period'):periods[0];
    const kind=param('class','BET');const relevant=db.snapshots.filter(s=>s.region===region&&s.period===period);
    const ages=relevant.filter(s=>s.list.startsWith(kind+' ')).map(s=>s.list.slice(4));
    const age=ages.includes(param('age'))?param('age'):ages.includes('40-49')?'40-49':ages[0];
    const list=kind==='WOMEN'?'ΓΥΝΑΙΚΩΝ':kind==='GENERAL'?'ΓΕΝΙΚΟΣ':kind+' '+age;
    const snap=relevant.find(s=>s.list===list);
    const rows=(snap?.rows||[]).filter(r=>search(players.get(r[0]).name+' '+players.get(r[0]).registration+' '+(clubs.get(r[3])?.name||''),param('q'))).sort((a,b)=>(a[1]??Infinity)-(b[1]??Infinity));
    return pageHead(L('Κατατάξεις ανά ηλικία & περιοχή','Rankings by age & region'),L('Οι θέσεις διατηρούν τη σειρά της επίσημης λίστας για τη συγκεκριμένη περιοχή και ηλικιακή κατηγορία.','Positions retain the official order within the selected region and age bracket.'))+
      `<div class="toolbar">${select('region',L('Περιοχή','Region'),['national','south','north'].map(r=>[r,regionName(r)]),region)}${select('class',L('Αγωνιστική κατηγορία','Player division'),['BET','ANE','WOMEN','GENERAL'].map(t=>[t,typeName(t)]),kind)}${ages.length?select('age',L('Ηλικιακή κατηγορία','Age bracket'),ages.map(a=>[a,a]),age):''}${select('period',L('Μήνας πηγής','Source month'),periods.map(p=>[p,month(p)]),period)}${field('q',L('Αναζήτηση','Search'),param('q'),L('Όνομα, ΔΑΙ ή ομάδα','Name, ID or team'))}</div>`+
      `<div class="notice">${L('Από τον Σεπτέμβριο 2026 οι πίνακες Βόρειας και Νότιας Ελλάδας ενοποιήθηκαν. Οι ξεχωριστοί περιφερειακοί πίνακες εδώ φτάνουν έως τον Ιούνιο 2026.','North and South rankings were unified from September 2026. Separate regional lists here run through June 2026.')} ${kind==='WOMEN'?L('Η πηγή δημοσιεύει ενιαίο πίνακα γυναικών, χωρίς ξεχωριστές ηλικιακές λίστες.','The source publishes one women’s table, without separate age-bracket lists.'):''}</div>`+
      (snap?`<div class="section-title"><h2>${E(listName(snap.list))}</h2>${sourceLink(snap.source)}</div><p class="chart-note">${E(regionName(region))} · ${month(period)} · ${L('Θέση εντός του επιλεγμένου πίνακα. Δεν υπολογίζεται ξανά μετά την αναζήτηση.','Rank within this list. Search does not renumber positions.')}</p>`+paged(rows,r=>rankingTable(r,snap)):empty());
  }
  function playerList(){const q=param('q'),category=param('category'),sort=param('sort','points'),snapshot=rosterSnapshot(category),ranks=new Map((snapshot?.rows||[]).map(r=>[r[0],r]));
    let rows=db.players.filter(p=>search([p.name,p.aliases.join(' '),p.registration,clubs.get(p.club)?.name].join(' '),q)&&(!category||p.category===category));
    const byName=(a,b)=>a.name.localeCompare(b.name,'el');
    rows.sort((a,b)=>sort==='name'?byName(a,b):sort==='wins'?statsByPlayer.get(b.id).wins-statsByPlayer.get(a.id).wins||byName(a,b):sort==='played'?statsByPlayer.get(b.id).played-statsByPlayer.get(a.id).played||byName(a,b):(ranks.get(a.id)?.[1]??Infinity)-(ranks.get(b.id)?.[1]??Infinity)||statsByPlayer.get(b.id).played-statsByPlayer.get(a.id).played||byName(a,b));
    return pageHead(L('Αθλητές','Players'),L('Βρες τον αθλητή και εξερεύνησε τη διαδρομή του.','Find a player and explore their record.'))+
      `<div class="panel panel-pad athlete-search"><div class="toolbar">${field('q',L('Αναζήτηση αθλητή','Search players'),q,L('Όνομα, ΔΑΙ ή ομάδα','Name, ID or team'))}${select('category',L('Κατηγορία','Category'),[['',L('Όλοι οι αθλητές','All players')],...[...new Set(db.players.map(p=>p.category).filter(Boolean))].sort().map(c=>[c,c])],category)}${select('sort',L('Ταξινόμηση','Sort by'),[['points',L('Θέση κατάταξης','Ranking position')],['played',L('Περισσότεροι αγώνες','Most matches')],['wins',L('Περισσότερες νίκες','Most wins')],['name',L('Αλφαβητικά','Alphabetical')]],sort)}</div></div>`+
      `<div class="section-title"><h2>${L('Λίστα αθλητών','Player list')}</h2><span class="chart-note">${snapshot?E(listName(snapshot.list))+' · '+month(snapshot.period):''}</span></div>`+
      paged(rows,rs=>`<div class="athlete-directory"><div class="athlete-list-head" aria-hidden="true"><span>#</span><span></span><span>${L('Αθλητής','Player')}</span><span>${L('Βαθμοί','Points')}</span><span>${L('Νίκες–Ήττες','Wins–Losses')}</span></div>${rs.map(p=>{const st=statsByPlayer.get(p.id),rank=ranks.get(p.id);return `<a class="athlete-row" href="#player/${E(p.id)}"><span class="athlete-rank">${rank?.[1]??'—'}</span><span class="athlete-avatar" aria-hidden="true">${E(p.name.split(' ').slice(0,2).map(n=>n[0]).join(''))}</span><span class="athlete-name"><strong>${E(p.name)}</strong><span>${E(clubs.get(p.club)?.name||'—')}${p.registration?' · ΔΑΙ '+E(p.registration):''}${p.provisional?' · '+L('Προσωρινή ταυτότητα','Provisional identity'):''}</span></span><span class="athlete-points"><strong>${num(rank?.[2],1)}</strong><small>${E(p.category)||'—'}</small></span><span class="athlete-record" aria-label="${num(st.played)} ${L('αγώνες','matches')}, ${num(st.wins)} ${L('νίκες','wins')}, ${num(st.losses)} ${L('ήττες','losses')}">${st.played?`<span><b class="won">${num(st.wins)}</b> – <b class="lost">${num(st.losses)}</b></span><span class="record-bar"><i style="width:${st.winRate*100}%"></i></span><small>${percent(st.winRate)} · ${num(st.played)} ${L('αγ.','played')}</small>`:`<small>${L('Χωρίς αγώνες','No matches')}</small>`}</span></a>`;}).join('')}</div>`,'page',50,L('αθλητές','players'));
  }
  function combinedRankingHistory(id){
    const history=playerHistories.get(id)||db.snapshots.flatMap(s=>(s.rows||[]).filter(r=>r[0]===id).map(row=>({...s,row})));
    return [...new Map(history.filter(h=>h.list==='ΓΕΝΙΚΟΣ').map(h=>[JSON.stringify([h.period,h.row[2]]),h])).values()].sort((a,b)=>a.period.localeCompare(b.period));
  }
  function historyChart(history){
    const rows=history.filter(h=>Number.isFinite(h.row[2]));
    const range=['all','1y','6m','3m'].includes(param('range'))?param('range'):'all';
    const controls=`<div class="ranking-ranges" role="group" aria-label="${L('Διάστημα γραφήματος','Chart range')}">${[['all',L('Όλα','All')],['1y',L('1Ε','1Y')],['6m',L('6Μ','6M')],['3m',L('3Μ','3M')]].map(([value,label])=>`<button type="button" id="chart-range-${value}" data-chart-range="${value}" aria-pressed="${range===value}" class="${range===value?'active':''}">${label}</button>`).join('')}</div>`;
    const heading=`<div class="ranking-chart-head"><h2 id="athlete-rankings" tabindex="-1">${L('Βαθμοί κατάταξης στο χρόνο','Ranking points over time')}</h2>${controls}</div>`;
    if(!rows.length)return heading+empty(L('Δεν υπάρχει ιστορικό βαθμών.','No ranking points history.'));
    const time=h=>Date.parse(h.period+'-01T00:00:00Z'),last=time(rows.at(-1)),cutoff=new Date(last);
    if(range!=='all')cutoff.setUTCMonth(cutoff.getUTCMonth()-({ '1y':12,'6m':6,'3m':3 }[range]));
    const shown=rows.filter(h=>range==='all'||time(h)>=cutoff.getTime());
    let t0=range==='all'?time(shown[0]):cutoff.getTime(),t1=last;
    if(t0===t1){t0-=15*86400000;t1+=15*86400000;}
    let low=Math.min(...shown.map(h=>h.row[2])),high=Math.max(...shown.map(h=>h.row[2]));
    if(low===high){const pad=Math.max(1,Math.abs(low)*.02);low-=pad;high+=pad;}
    const raw=(high-low)/5,mag=10**Math.floor(Math.log10(raw)),step=[1,2,2.5,5,10].map(v=>v*mag).find(v=>v>=raw);
    low=Math.floor(low/step)*step;high=Math.ceil(high/step)*step;
    const width=Math.max(240,Math.min(1060,(window.innerWidth||1200)-88)),left=58,right=width-22;
    const x=t=>left+(t-t0)/(t1-t0)*(right-left),y=v=>22+(high-v)/(high-low)*260;
    const ticks=[];for(let v=low;v<=high+step/2;v+=step)ticks.push(v);
    const points=shown.map(h=>[x(time(h)),y(h.row[2])]);
    const xticks=[];const start=new Date(t0),end=new Date(t1),total=(end.getUTCFullYear()-start.getUTCFullYear())*12+end.getUTCMonth()-start.getUTCMonth(),monthStep=[1,2,3,6,12,24,36].find(n=>total/n<=Math.max(1,Math.min(6,Math.floor((right-left)/100))))||48;
    for(let i=0;i<=total;i+=monthStep){const t=Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+i,1);if(t>=t0&&t<=t1)xticks.push(t);}
    const label=h=>month(h.period)+': '+num(h.row[2],3)+' '+L('βαθμοί','points');
    return heading+`<div class="ranking-chart-scroll"><svg class="chart athlete-ranking-chart" viewBox="0 0 ${width} 330" tabindex="0" role="group" aria-label="${L('Ιστορικό βαθμών κατάταξης · τα βέλη μετακινούν ανάμεσα στα σημεία','Ranking points history · arrow keys move between points')}" aria-describedby="ranking-readout">${ticks.map(v=>`<path d="M${left} ${y(v)}H${right}" class="rank-grid"/><text x="${left-12}" y="${y(v)+4}" text-anchor="end">${num(v,1)}</text>`).join('')}${xticks.map(t=>`<path d="M${x(t)} 22V282" class="rank-grid"/><text x="${x(t)}" y="312" text-anchor="${x(t)>right-30?'end':'middle'}">${E(month(new Date(t).toISOString().slice(0,7)))}</text>`).join('')}<polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#2b4052" stroke-width="2"/>${points.map(([cx,cy],i)=>`<circle cx="${cx}" cy="${cy}" r="3.5" fill="#2b4052" data-rank-point="${E(label(shown[i]))}"><title>${E(label(shown[i]))}</title></circle>`).join('')}</svg></div><p class="ranking-readout" id="ranking-readout" aria-live="polite">${E(label(shown.at(-1)))}</p><p class="chart-note">${shown.length} / ${rows.length} ${L('δημοσιευμένα σημεία · Αγγίξτε ένα σημείο ή χρησιμοποιήστε τα βέλη στο γράφημα για λεπτομέρειες.','published points · Tap a point, or use the arrow keys on the chart, for details.')}</p>`;
  }
  function athleteInsights(summary){
    const row=(label,value,cls='')=>`<div class="athlete-stat-row ${cls}"><span>${label}</span><span>${value}</span></div>`;
    const record=([w,l])=>`<b>${num(w)}–${num(l)}</b> <small>${percent(w+l?w/(w+l):null)}</small>`;
    const totals=summary.totals,opponents=summary.opponents.slice(0,6);
    const scoreMax=Math.max(1,...summary.scoreLines.map(line=>line.count));
    const scoreRows=summary.scoreLines.map(line=>`<div class="athlete-stat-row score-line">`+`<span class="${line.mine>line.theirs?'won':'lost'}">${line.mine>line.theirs?'✓':'✕'} ${line.mine}–${line.theirs}</span>`+`<span class="score-bar ${line.mine>line.theirs?'won':'lost'}" aria-hidden="true"><i style="width:${Math.round(line.count/scoreMax*100)}%"></i></span><span>`+`<b>${num(line.count)}</b>`+`</span></div>`).join('');
    const rankLabels={higher:L('Αντίπαλος σε υψηλότερη θέση','Higher-ranked opponent'),lower:L('Αντίπαλος σε χαμηλότερη θέση','Lower-ranked opponent'),level:L('Ίδια θέση','Same rank'),unknown:L('Χωρίς σύγκριση','Not comparable')};
    return `<section aria-labelledby="athlete-analysis"><div class="section-title"><h2 id="athlete-analysis" tabindex="-1">${L('Ανάλυση αγώνων','Match breakdown')}</h2></div><div class="athlete-insight-grid"><section class="panel panel-pad"><h3>${L('Σκορ αγώνων','Match scores')}</h3>${scoreRows}${row(L('Αγώνες στο τελευταίο σετ','Deciding-game matches'),record([totals.decidingWins,totals.deciding-totals.decidingWins]))}${row(L('Σετ υπέρ–κατά','Games won–lost'),`<b>${num(totals.gamesWon)}–${num(totals.gamesLost)}</b>`)}</section><section class="panel panel-pad"><h3>${L('Ανάλογα με τη θέση του αντιπάλου','By opponent ranking')}</h3>${Object.entries(summary.vsRanking).filter(([k,v])=>k!=='level'||v[0]+v[1]).map(([k,v])=>row(rankLabels[k],record(v))).join('')}<p class="chart-note">${L('Σύγκριση στον ίδιο γενικό πίνακα, από τον πιο πρόσφατο διαθέσιμο μήνα πριν από τον αγώνα. Οι πηγές δίνουν μήνα, όχι ακριβή ημέρα δημοσίευσης. Αν λείπει ένας αθλητής από τον ίδιο πίνακα, δεν γίνεται σύγκριση.','Both players are compared in the same general ranking, from the latest available month before the match month. Sources provide a month, not an exact publication day. If either player is absent from that list, the match is not compared.')}</p></section><section class="panel panel-pad"><h3>${L('Καλύτερες νίκες','Best wins')}</h3>${summary.bestWins.length?summary.bestWins.map(b=>{const snap=snapshotMap.get(b.snapshot),m=b.match;return row(`<strong>#${b.rank}</strong> · ${pLink(b.opponent)}<small class="stat-context">${E(regionName(snap?.region))} · ${snap?month(snap.period):''} · ${snap?sourceLink(snap.source):''}</small>`,`<b>${(m.p1===current.id?m.score:[...m.score].reverse()).join('–')}</b><small class="stat-context">${datefmt(m.date)}</small>`,'best-win');}).join(''):`<p class="chart-note">${L('Δεν υπάρχουν νίκες με συγκρίσιμη προηγούμενη κατάταξη.','No wins with a comparable earlier ranking.')}</p>`}<p class="chart-note">${L('Νίκες απέναντι στις υψηλότερες θέσεις των αντίστοιχων πινάκων πριν από τον μήνα του αγώνα.','Wins against the highest positions in the respective source lists before the match month.')}</p></section><section class="panel panel-pad"><h3>${L('Συχνότεροι αντίπαλοι','Most frequent opponents')}</h3>${opponents.map(o=>row(pLink(o.id),record([o.wins,o.losses]))).join('')}<p class="chart-note">${num(summary.opponents.length)} ${L('διαφορετικοί αντίπαλοι','distinct opponents')}</p></section></div></section>`;
  }
  function athleteSeasonTables(summary,id){
    const seasonRows=summary.bySeason.map(r=>`<tr><td>${link('player/'+id,r.season,{season:r.season,...(param('range')?{range:param('range')}:{})})}</td><td class="number">${num(r.events)}</td><td class="number">${num(r.played)}</td><td class="number won">${num(r.wins)}</td><td class="number lost">${num(r.losses)}</td><td class="number">${percent(r.winRate)}</td></tr>`).join('');
    return `<div class="athlete-seasons-grid"><section><div class="section-title"><h2>${L('Ανά αγωνιστική περίοδο','By season')}</h2></div><div class="panel">${table([L('Περίοδος','Season'),L('Διοργ.','Events'),L('Αγ.','Played'),L('Ν','W'),L('Η','L'),'%'],seasonRows)}</div></section><section aria-labelledby="athlete-events"><div class="section-title"><h2 id="athlete-events" tabindex="-1">${L('Διοργανώσεις','Competitions')} · ${num(summary.byEvent.length)}</h2></div>${paged(summary.byEvent,rs=>table([L('Τελευταίος αγώνας','Last match'),L('Διοργάνωση','Competition'),L('Αγ.','Played'),L('Ν–Η','W–L')],rs.map(r=>`<tr><td>${datefmt(r.last)}</td><td>${link('event/'+r.id,events.get(r.id).name)}<span class="meta">${E(events.get(r.id).season)}</span></td><td class="number">${num(r.played)}</td><td class="number">${num(r.wins)}–${num(r.losses)}</td></tr>`).join('')),'epage',8,L('διοργανώσεις','competitions'))}</section></div>`;
  }
  function playerDetail(id) {
    const p=players.get(id);if(!p)return notFound();
    const rows=[...(matchesByPlayer.get(id)||[])].sort((a,b)=>b.date.localeCompare(a.date)||a.id.localeCompare(b.id));
    const seasons=[...new Set(rows.map(m=>events.get(m.event).season))].sort().reverse();
    const filtered=rows.filter(m=>!param('season')||events.get(m.event).season===param('season'));
    const summary=PofepaAthleteStats.summarize(filtered,id,events,playerRankComparisons.get(id)||db.match_rankings||{}),s=summary.totals;
    const chartRows=combinedRankingHistory(id);
    const latest=chartRows.at(-1),latestPoints=[...new Set(chartRows.filter(h=>h.period===latest?.period&&h.row[2]!==null).map(h=>h.row[2]))];
    return breadcrumb(L('Αθλητές','Players'),'players')+`<div class="athlete-profile">`+
      `<div class="profile-head athlete-hero"><div class="profile-identity"><div class="avatar" aria-hidden="true">${E(p.name.split(' ').slice(0,2).map(n=>n[0]).join(''))}</div><div><div class="eyebrow">${p.registration?'ΔΑΙ '+E(p.registration):L('Προσωρινή ταυτότητα','Provisional identity')}</div><h1>${E(p.name)}</h1><div class="athlete-chips"><span>${cLink(p.club)} · ${month(p.period)}</span>${p.category?`<span>${E(p.category)}</span>`:''}${latestPoints.length?`<span>${latestPoints.map(v=>num(v,1)).join(' / ')} ${L('βαθμοί','points')} · ${month(latest.period)}</span>`:''}</div></div></div><a class="button secondary" href="${E(href('h2h',{p1:id}))}">${L('Σύγκριση αθλητών','Compare players')}</a></div>`+
      `<nav class="profile-jumps" aria-label="${L('Ενότητες αθλητή','Athlete sections')}"><button type="button" data-jump="athlete-rankings">${L('Κατάταξη','Ranking')}</button>${s.played?`<button type="button" data-jump="athlete-analysis">${L('Ανάλυση','Breakdown')}</button>`:''}<button type="button" data-jump="athlete-matches">${L('Αγώνες','Matches')}</button></nav>`+
      (p.provisional?`<div class="notice">${L('Αυτή η εγγραφή δεν συνδέθηκε με βεβαιότητα με αριθμό ΔΑΙ. Οι αγώνες της παραμένουν χωριστά από ομώνυμους αθλητές.','This source identity could not be resolved to a registration number. Its matches remain separate from players with the same name.')}</div>`:'')+
      (p.identity_conflict?`<div class="notice">${L('Ο ίδιος ΔΑΙ εμφανίζεται με διαφορετικά ονόματα στις πηγές. Οι διαφορετικές εγγραφές διατηρούνται χωριστές μέχρι να ελεγχθούν.','This registration number appears under different names in the sources. Those identities remain separate pending review.')}</div>`:'')+
      `<section class="panel panel-pad athlete-chart-panel" aria-labelledby="athlete-rankings">${historyChart(chartRows)}</section>`+
      `<div class="toolbar athlete-season">${select('season',L('Περίοδος αγώνων','Match season'),[['',L('Όλες οι περίοδοι','All seasons')],...seasons.map(v=>[v,v])],param('season'))}<p class="chart-note">${num(s.played)} ${L('αγώνες στο αρχείο. Η περίοδος αλλάζει τα στατιστικά και τους αγώνες. Το γράφημα έχει ξεχωριστό διάστημα.','archived matches. Season filters statistics and matches. The chart has its own date range.')}</p></div>`+
      `<div class="athlete-results">${metric(s.played?num(s.wins):'—',L('Νίκες','Wins'),'win')}${metric(s.played?num(s.losses):'—',L('Ήττες','Losses'),'loss')}${metric(percent(s.winRate),L('Ποσοστό νικών','Win rate'))}</div>`+
      (s.played?athleteInsights(summary)+athleteSeasonTables(summary,id):'')+
      `<section aria-labelledby="athlete-matches"><div class="section-title"><h2 id="athlete-matches" tabindex="-1">${L('Ιστορικό αγώνων','Match history')}</h2><button class="button secondary" data-export="player" data-id="${E(id)}">CSV</button></div>${paged(filtered,r=>matchTable(r,id),'page',10)}</section></div>`;
  }
  // The hosted Matches page reads a compact list (data/match-list.json.gz); full
  // records stay in data/matches.json.gz for CSV export. Offline uses db.matches.
  let matchIndex=null;
  async function loadMatchIndex(){if(!matchIndex){const list=await fetchData('data/match-list.json.gz');matchIndex||=Pofepa.expandMatchList(list);}return matchIndex;}
  const nameForms=new Map();
  // Shared by the Matches view and its CSV export. A season or competition that
  // does not belong to this view (or to each other) is ignored, not applied.
  function matchFilters(view){const singles=view==='singles',relevant=db.events.filter(e=>e.kind===(singles?'singles':'fixtures'));
    const seasons=[...new Set(relevant.map(e=>e.season))].sort().reverse(),season=seasons.includes(param('season'))?param('season'):'';
    const competitions=relevant.filter(e=>!season||e.season===season),event=competitions.some(e=>e.id===param('event'))?param('event'):'';
    const region=param('region'),status=param('status'),found=pairSearch(param('q'),nameForms);
    const keep=m=>(!event||m.event===event)&&(!season||events.get(m.event).season===season)&&(!region||(m.regions||[m.region]).includes(region))&&(!status||m.status===status)&&(singles?found(m.names[0],m.names[1]):found(m.home,m.away));
    return {seasons,season,competitions,event,keep};}
  function competitionLabel(e){const name=eventTitle(e),short=e.season.length===9?e.season.slice(0,5)+e.season.slice(7):e.season,place=eventPlace(e,regionName(e.region));
    return name+(name.includes(e.season)||name.includes(short)?'':' · '+e.season)+(place?' · '+place:'');}
  function competitionSelect(competitions,value){const seasons=[...new Set(competitions.map(e=>e.season))].sort().reverse();
    return `<div class="field competition-field"><label for="filter-event">${E(L('Διοργάνωση','Competition'))}</label><select id="filter-event" data-filter="event"><option value="">${E(L('Όλες οι διοργανώσεις','All competitions'))}</option>${seasons.map(season=>`<optgroup label="${E(season)}">${competitions.filter(e=>e.season===season).map(e=>[e.id,competitionLabel(e)]).sort((a,b)=>a[1].localeCompare(b[1],'el')).map(([id,label])=>`<option value="${E(id)}" ${id===value?'selected':''}>${E(label)}</option>`).join('')}</optgroup>`).join('')}</select></div>`;}
  function matchList(){const view=param('view','singles');const {seasons,season,competitions,event,keep}=matchFilters(view);
    const rows=(view==='singles'?db.matches:db.fixtures).filter(keep);
    return pageHead(L('Αγώνες & αποτελέσματα','Matches & results'),view==='singles'?L('Μόνο ολοκληρωμένα σκορ 3–0, 3–1 και 3–2.','Completed 3–0, 3–1 and 3–2 scores only.'):L('Οι ημερομηνίες ορισμού είναι προθεσμίες της πηγής, όχι επιβεβαιωμένες ημερομηνίες διεξαγωγής.','Source deadlines are not confirmed dates of play.'),view==='singles'?`<button class="button secondary" data-export="matches">${L('Εξαγωγή CSV','Export CSV')}</button>`:'')+
      `<div class="chips"><a class="${view==='singles'?'active':''}" href="#matches">${L('Ατομικοί αγώνες','Singles')}</a><a class="${view==='teams'?'active':''}" href="#matches?view=teams">${L('Ομαδικές συναντήσεις','Team fixtures')}</a></div><div class="toolbar">${field('q',L('Αναζήτηση','Search'),param('q'),view==='singles'?L('Όνομα αθλητή','Player name'):L('Όνομα ομάδας','Team name'))}${select('season',L('Περίοδος','Season'),[['',L('Όλες οι περίοδοι','All seasons')],...seasons.map(s=>[s,s])],season)}${competitionSelect(competitions,event)}${view==='singles'?select('region',L('Περιοχή πηγής','Source region'),[['',L('Όλες οι περιοχές','All regions')],...['national','south','north'].map(r=>[r,regionName(r)])],param('region')):select('status',L('Κατάσταση','Status'),[['',L('Όλες','All')],['reported',L('Με αποτέλεσμα','Reported results')],['scheduled',L('Χωρίς αποτέλεσμα','No result yet')]],param('status'))}</div>`+paged(rows,r=>view==='singles'?matchTable(r):fixtureTable(r));
  }
  function eventList(){
    const seasons=[...new Set(db.events.map(e=>e.season))].sort().reverse();
    const season=param('season',seasons[0]),kind=param('kind','fixtures'),region=param('region'),competition=param('competition');
    const rows=db.events.filter(e=>(kind==='all'||e.kind===kind)&&(season==='all'||e.season===season)&&(!region||e.competition_region===region)&&(!competition||e.competition_type===competition)&&search(eventTitle(e)+' '+competitionRegionName(e.competition_region),param('q')));
    const order=id=>{const n=competitionRegions.findIndex(r=>r.id===id);return n<0?competitionRegions.length:n;};
    rows.sort((a,b)=>order(a.competition_region)-order(b.competition_region)||b.season.localeCompare(a.season));
    const grouped=rs=>competitionRegions.map(region=>{
      const group=rs.filter(e=>(e.competition_region||'unspecified')===region.id);if(!group.length)return '';
      const sections=[['league',L('Πρωταθλήματα','Leagues')],['cup',L('Κύπελλα','Cups')],['singles',L('Ατομικά αποτελέσματα','Singles results')]].map(([type,label])=>{
        const competitions=group.filter(e=>(e.competition_type||e.kind)===type);if(!competitions.length)return '';
        return `<div class="competition-kind" data-competition-type="${type}"><h3>${label}</h3>`+table([L('Διοργάνωση','Competition'),L('Περίοδος','Season'),L('Προβολή','View'),L('Συναντήσεις','Matches')],competitions.map(e=>`<tr><td class="player-cell">${link('event/'+e.id,eventTitle(e))}</td><td>${e.season}</td><td>${e.kind==='singles'?L('Ατομικά αποτελέσματα','Singles results'):e.competition_type==='cup'?L('Αποτελέσματα κυπέλλου','Cup results'):L('Ανά αγωνιστική','By matchday')}</td><td class="number">${num(e.match_count??(e.kind==='singles'?db.matches:db.fixtures).filter(m=>m.event===e.id).length)}</td></tr>`).join(''))+'</div>';
      }).join('');
      return `<section class="competition-group" aria-labelledby="competition-${E(region.id)}"><h2 id="competition-${E(region.id)}">${E(competitionRegionName(region.id))}</h2>${sections}</section>`;
    }).join('');
    return pageHead(L('Διοργανώσεις','Competitions'),L('Οι διοργανώσεις ανά περιφέρεια, όπως οργανώνονται στις σελίδες αποτελεσμάτων του ΠΟΦΕΠΑ.','Competitions by region, following the organisation of POFΕPA’s results pages.'))+
      `<div class="toolbar">${field('q',L('Αναζήτηση','Search'),param('q'))}${select('season',L('Περίοδος','Season'),[['all',L('Όλες οι περίοδοι','All seasons')],...seasons.map(s=>[s,s])],season)}${select('region',L('Περιφέρεια','Region'),[['',L('Όλες οι περιφέρειες','All regions')],...competitionRegions.map(r=>[r.id,competitionRegionName(r.id)])],region)}${select('kind',L('Δεδομένα','Records'),[['fixtures',L('Ομαδικές διοργανώσεις','Team competitions')],['singles',L('Ατομικά αποτελέσματα','Singles results')],['all',L('Όλα','All')]],kind)}${kind!=='singles'?select('competition',L('Τύπος διοργάνωσης','Competition type'),[['',L('Πρωταθλήματα & κύπελλα','Leagues & cups')],['league',L('Πρωταθλήματα','Leagues')],['cup',L('Κύπελλα','Cups')]],competition):''}</div>`+
      (kind!=='fixtures'?`<p class="chart-note">${L('Όπου η πηγή δεν ορίζει συγκεκριμένη περιφέρεια διοργάνωσης, το αρχείο εμφανίζεται χωριστά.','Records without a specific competition region in the source are listed separately.')}</p>`:'')+paged(rows,grouped);
  }
  function eventDetail(id){const e=events.get(id);if(!e)return notFound();const rows=(e.kind==='singles'?db.matches:db.fixtures).filter(m=>m.event===id);
    return breadcrumb(L('Διοργανώσεις','Competitions'),'events')+pageHead(eventTitle(e),e.season+(e.competition_region&&e.competition_region!=='unspecified'?' · '+competitionRegionName(e.competition_region):''),sourceLink(e.sources[0]))+(e.competition_type==='cup'?cupDraw(e,rows):(e.kind==='fixtures'?`<div class="notice">${L('Οι ημερομηνίες ορισμού δεν είναι επιβεβαιωμένες ημερομηνίες αγώνα. Δεν συμπεραίνουμε ατομικά αποτελέσματα από το ομαδικό σκορ.','Listed deadlines are not confirmed match dates. Singles results are not inferred from team scores.')}</div>`:'')+(e.kind==='fixtures'?fixturesByRound(rows):paged(rows,matchTable)));
  }
  function teamDetail(id){const c=clubs.get(id);if(!c)return notFound();const roster=latestGeneral.rows.filter(r=>r[3]===id),fixtures=db.fixtures.filter(f=>f.clubs.includes(id));
    return breadcrumb(L('Διοργανώσεις','Competitions'),'events')+pageHead(c.name,L('Η σύνθεση βασίζεται στην τελευταία πανελλαδική κατάταξη.','Roster follows the latest national ranking.'))+`<div class="section-title"><h2>${L('Αθλητές','Players')} · ${month(latestPeriod)}</h2></div><div class="panel">${roster.length?rankingTable(roster,latestGeneral):empty()}</div><div class="section-title"><h2>${L('Ομαδικές συναντήσεις','Team fixtures')}</h2></div>`+paged(fixtures,fixtureTable);
  }
  const playerOption=p=>p.name+' · '+(p.registration?'ΔΑΙ '+p.registration:p.id);
  // Head-to-head player picker: an ARIA combobox over the same accent-insensitive
  // search as the player list, instead of a datalist of every profile.
  const pickerForms=new Map();
  const pickerText=p=>[p.name,p.aliases.join(' '),p.registration,clubs.get(p.club)?.name].join(' ');
  const suggestPlayers=(query,limit=8)=>Pofepa.playerSuggestions(db.players,query,{text:pickerText,played:p=>statsByPlayer.get(p.id)?.played||0,limit,cache:pickerForms});
  function playerPicker(key,name,label,player){const id='compare-'+key;
    return `<div class="field player-picker"><label for="${id}">${E(label)}</label><input id="${id}" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="${id}-list" value="${E(player?playerOption(player):'')}" placeholder="${E(L('Όνομα, ΔΑΙ ή ομάδα','Name, ID or team'))}" autocomplete="off" autocapitalize="off" spellcheck="false" required><input type="hidden" name="${name}" value="${E(player?.id||'')}"><ul id="${id}-list" class="picker-list" role="listbox" aria-label="${E(label)}" hidden></ul><span class="sr-only" role="status" id="${id}-status"></span></div>`;}
  const pickerParts=input=>{const picker=input.closest('.player-picker');return {picker,list:picker.querySelector('[role=listbox]'),status:picker.querySelector('[role=status]'),chosen:picker.querySelector('input[type=hidden]')};};
  function closePicker(input){const {list}=pickerParts(input);list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');}
  function showSuggestions(input){const {list,status}=pickerParts(input),{total,results}=suggestPlayers(input.value),typed=input.value.trim();
    list.innerHTML=results.length?results.map((p,i)=>`<li id="${input.id}-opt-${i}" role="option" aria-selected="false" data-player="${E(p.id)}"><strong>${E(p.name)}</strong><small>${E([p.registration?L('ΔΑΙ','ID')+' '+p.registration:L('Προσωρινή ταυτότητα','Provisional identity'),clubs.get(p.club)?.name,p.category,statsByPlayer.get(p.id)?.played?num(statsByPlayer.get(p.id).played)+' '+L('αγώνες','matches'):''].filter(Boolean).join(' · '))}</small></li>`).join('')+(total>results.length?`<li class="picker-more" role="presentation">${E(L(`Εμφανίζονται ${num(results.length)} από ${num(total)} · συνεχίστε να πληκτρολογείτε`,`Showing ${num(results.length)} of ${num(total)} · keep typing`))}</li>`:''):typed?`<li class="picker-more" role="presentation">${E(L('Δεν βρέθηκε αθλητής','No matching player'))}</li>`:'';
    list.hidden=!typed;input.setAttribute('aria-expanded',String(results.length>0));input.removeAttribute('aria-activedescendant');
    status.textContent=typed?(total?num(total)+' '+L(total===1?'αθλητής':'αθλητές','matching players'):L('Δεν βρέθηκε αθλητής','No matching player')):'';}
  function choosePlayer(input,option){const player=players.get(option?.dataset.player);if(!player)return;const {chosen,status}=pickerParts(input);
    input.value=playerOption(player);chosen.value=player.id;status.textContent='';closePicker(input);const error=document.getElementById('compare-error');if(error)error.textContent='';}
  function movePicker(input,step){const {list}=pickerParts(input);if(list.hidden)showSuggestions(input);const options=[...list.querySelectorAll('[role=option]')];if(!options.length)return;
    const current=options.findIndex(o=>o.id===input.getAttribute('aria-activedescendant')),next=current<0?(step>0?0:options.length-1):Math.min(options.length-1,Math.max(0,current+step));
    options.forEach((o,i)=>{o.setAttribute('aria-selected',String(i===next));o.classList.toggle('active',i===next);});input.setAttribute('aria-activedescendant',options[next].id);options[next].scrollIntoView({block:'nearest'});}
  // On submit: the chosen suggestion, else the exact label, else a unique match for the typed text.
  function pickedPlayer(form,name){const chosen=form.querySelector(`input[type=hidden][name="${name}"]`),text=chosen?.closest('.player-picker')?.querySelector('[role=combobox]')?.value.trim()||'';
    if(players.has(chosen?.value))return players.get(chosen.value);const exact=db.players.find(p=>playerOption(p)===text);if(exact)return exact;
    const registered=db.players.filter(p=>p.registration&&p.registration===text);if(registered.length===1)return registered[0];
    const {total,results}=suggestPlayers(text,1);return total===1?results[0]:null;}
  function compare(){const a=players.get(param('p1')),b=players.get(param('p2')),rows=h2h(db.matches,a?.id,b?.id),same=a&&b&&a.id===b.id;
    return pageHead(L('Σύγκριση αθλητών','Head to head'),L('Επίλεξε δύο αθλητές. Η διεύθυνση κρατά τη σύγκριση για να τη μοιραστείς.','Choose two players. The URL preserves your comparison for sharing.'))+`<form id="compare-form" class="panel panel-pad"><div class="compare">${playerPicker('a','p1',L('Πρώτος αθλητής','First player'),a)}<span class="versus">vs</span>${playerPicker('b','p2',L('Δεύτερος αθλητής','Second player'),b)}</div><button class="primary" style="margin-top:20px">${L('Σύγκριση','Compare')}</button><p id="compare-error" role="alert" style="margin-top:14px"></p></form>`+
      (same?empty(L('Επίλεξε δύο διαφορετικούς αθλητές.','Choose two different players.')):a&&b?`<div class="panel compare-score"><div><h2>${pLink(a.id)}</h2><small>${E(a.category)}</small></div><strong>${stats(rows,a.id).wins} : ${stats(rows,b.id).wins}</strong><div><h2>${pLink(b.id)}</h2><small>${E(b.category)}</small></div></div>${rows.length?paged(rows,matchTable):empty(L('Δεν υπάρχουν μεταξύ τους αγώνες στο εισαγμένο αρχείο. Αυτό δεν σημαίνει ότι δεν έχουν αγωνιστεί ποτέ.','No meetings in the imported archive. This does not mean they have never played.'))}`:'');
  }
  function aboutBase(){const c=db.coverage;
    return pageHead(L('Κάλυψη & πηγές','Coverage & sources'),L('Ανεξάρτητο έργο, με την ίδια στατική αρχιτεκτονική του Greek TT Archive. Δεν αποτελεί επίσημη υπηρεσία του ΠΟΦΕΠΑ.','An independent project using the static architecture of Greek TT Archive. Not an official POFΕPA service.'))+
      `<div class="metric-grid">${metric(num(c.matches),L('Ατομικοί αγώνες','Singles matches'))}${metric(num(c.ranking_rows),L('Εγγραφές κατάταξης','Ranking records'))}${metric(num(c.reported_fixtures),L('Ομαδικά αποτελέσματα','Reported fixtures'))}${metric(num(c.provisional_players),L('Μη συνδεδεμένες ταυτότητες','Unresolved identities'))}</div><div class="panel panel-pad prose"><h2>${L('Τι περιλαμβάνει το αρχείο','What the archive includes')}</h2><p>${L('Εισάγονται όλα τα συνδεδεμένα αρχεία Excel του επίσημου αρχείου, από τον Οκτώβριο 2011 έως τον Οκτώβριο 2026. Διατηρούνται οι ξεχωριστοί πίνακες Βόρειας, Νότιας Ελλάδας και οι πανελλαδικοί, ανά ηλικιακή κατηγορία. Από τον Σεπτέμβριο 2026 οι περιφερειακοί πίνακες ενοποιούνται.','Every linked Excel workbook in the official archive is imported, from October 2011 through October 2026. North Greece, Attica & South Greece and national lists retain their separate age-bracket positions. Regional rankings were unified from September 2026.')}</p><p>${L('Ατομικοί αγώνες στις εισαγμένες πηγές','Singles matches in imported sources')}: ${datefmt(c.match_date_min)} – ${datefmt(c.match_date_max)}. ${L('Έλεγχος πηγών','Sources checked')}: ${datefmt(c.as_of)}.</p><h2>${L('Ηλικία και περιοχή','Age and region')}</h2><p>${L('Χρησιμοποιούμε τους επίσημους πίνακες ANE και BET για κάθε ηλικιακό εύρος. Οι κατηγορίες και οι θέσεις λαμβάνονται από το αντίστοιχο φύλλο, δεν υπολογίζονται από έτη γέννησης ή από φιλτραρισμένη γενική κατάταξη. Τα έτη γέννησης δεν περιλαμβάνονται στο αρχείο. Η πηγή δίνει ενιαίο πίνακα γυναικών, όχι χωριστούς ανά ηλικία.','We use the official ANE and BET sheets for each age bracket. Categories and positions come from the relevant sheet, not from birth years or a filtered overall ranking. Birth years are not included. The source supplies one combined women’s list, not separate age lists.')}</p><h2>${L('Τι μετράει ως αγώνας','What counts as a match')}</h2><p>${L('Μετράνε μόνο γραμμές με δύο αθλητές, έγκυρη ημερομηνία και τελικό σκορ 3–0, 3–1 ή 3–2. Bonus, μη τυπικά σκορ (π.χ. 1–0), αποτελέσματα με σήμανση «α/α» (άνευ αγώνα), κενές ή ίδιες ταυτότητες αποκλείονται. Κάθε αποτέλεσμα διατηρεί την πηγή και τη γραμμή του στο αρχείο ή στο φύλλο αγώνα. Δεν εμφανίζονται επιμέρους πόντοι σετ.','Only rows with two players, a valid date and a final 3–0, 3–1 or 3–2 score count. Bonus rows, nonstandard scores (such as 1–0), results marked “α/α” (walkover, not played), missing or identical participants are excluded. Each result retains its source and row in the workbook or match sheet. Individual game points are not displayed.')}</p><p>${L('Εξαιρέσεις ανά λόγο','Excluded rows by reason')}: ${Object.entries(c.excluded_rows).map(([k,v])=>E(k)+': '+num(v)).join(' · ')}.</p><h2>${L('Σύνδεση αθλητών','Player identity')}</h2><p>${L('Οι κατατάξεις συνδέονται με τον επίσημο αριθμό ΔΑΙ. Τα μηνιαία φύλλα αποτελεσμάτων Excel δεν έχουν ΔΑΙ: χρησιμοποιούμε ακριβές όνομα και ομάδα στους πίνακες του ίδιου μήνα. Αν η ομάδα είναι κενή, συνδέουμε μόνο μοναδικό όνομα σε αυτούς τους πίνακες και σημειώνουμε την προσωρινή συσχέτιση. Αμφίσημα ονόματα παραμένουν χωριστά. Μοναδικό ακριβές όνομα μπορεί να συνδεθεί προσωρινά όταν διαφέρει η ομάδα. Παλαιότερες λίστες χωρίς ΔΑΙ συνδέονται με ακριβές όνομα και ομάδα ή μοναδικό ακριβές όνομα. Επαναλαμβανόμενα ιστορικά ονόματα παραμένουν χωριστά. Σύνδεση μοναδικού ονόματος με διαφορετική ομάδα σημειώνεται ως προσωρινή.','Rankings link by official DAI registration number where supplied. Monthly Excel results sheets omit DAI: we match exact name and team across the same month’s ranking lists. Unique exact names can be provisionally linked when the team is blank or differs. Ambiguous names remain separate. Before registration numbers appeared, historical rows are linked by an exact name and team, or a unique exact name across registered profiles. Repeated historical names remain separate. Exact-name matches with a different team are marked provisional. No fuzzy name matching is used.')}</p><h2>${L('Περιορισμοί κάλυψης','Coverage limitations')}</h2><p>${L('Τα ατομικά αποτελέσματα περιλαμβάνουν τις μηνιαίες λίστες και τα ελεγμένα φύλλα αγώνων. Τα ομαδικά προγράμματα ενημερώνονται ξεχωριστά και μπορεί να έχουν πιο πρόσφατα σκορ. Οι ημερομηνίες ορισμού δεν θεωρούνται ημερομηνίες διεξαγωγής. Οι αμφίσημες γραμμές, οι μη διαθέσιμες περίοδοι και τα μη αναγνώσιμα τμήματα καταγράφονται αναλυτικά παρακάτω. Δεν συμπληρώνουμε κενά με υποθετικούς αγώνες.','Singles coverage includes imported monthly workbooks and reviewed match sheets. Team schedules are collected separately and may have more recent scores. Scheduled deadlines are not treated as actual play dates. Ambiguous rows, missing periods and unparsed document sections are listed below. Gaps are not filled with inferred results.')}</p><p>${external('https://www.pofepa.gr/',L('Ιστότοπος ΠΟΦΕΠΑ','POFΕPA website'))} · ${external(db.ranking_index,L('Επίσημο αρχείο κατατάξεων','Official ranking archive'))}</p><button class="button secondary" data-export="data">${L('Λήψη δεδομένων (JSON, gzip)','Download dataset (JSON, gzip)')}</button> <button class="button secondary" data-export="matches">${L('Αγώνες CSV','Matches CSV')}</button></div>`;
  }
  // Long audit lists are paginated so the explanations stay at the top of the page.
  const ABOUT_PAGE_SIZE=25;
  const aboutJumps={sheetpage:'about-sheet-list',docpage:'about-documents',sourcepage:'about-sources'};
  const fileName=url=>decodeURIComponent(url.split('/').at(-1));
  function sourceInventory(){const c=db.coverage;
    return `<div class="section-title"><h2 id="about-sources" tabindex="-1">${L('Εισαγμένες πηγές','Imported sources')}</h2></div>`+
      paged(db.sources,rows=>table([L('Αρχείο / σελίδα','File / page'),L('Ανάκτηση UTC','Retrieved UTC'),L('SHA-256','SHA-256')],rows.map(s=>`<tr><td class="source-cell">${external(s.url,fileName(s.url))}</td><td>${E(s.retrieved_at)}</td><td><details><summary>${s.sha256.slice(0,12)}…</summary><code style="overflow-wrap:anywhere">${s.sha256}</code></details></td></tr>`).join('')),'sourcepage',ABOUT_PAGE_SIZE,L('πηγές','sources'))+
      `<details class="panel panel-pad"><summary>${L('Σελίδες που χρειάζονται ξεχωριστή εισαγωγή','Pages needing separate ingestion')} (${c.deferred.length})</summary>${table([L('Πηγή','Source'),L('Αιτία','Reason')],c.deferred.map(d=>`<tr><td>${external(d.url,d.label)}</td><td>${E(d.reason)}</td></tr>`).join(''))}</details>`;
  }
  function about(){return aboutBase()+matchSheetCoverage()+documentReviews()+`<section class="panel panel-pad"><h2>${L('ΔΑΙ με διαφορετικά ονόματα','Registration numbers with changed names')}</h2><p>${L('Οι παρακάτω παραλλαγές διατηρούνται σε χωριστά προφίλ μέχρι να ελεγχθούν, ακόμη και όταν φαίνονται σαν απλά ορθογραφικά λάθη.','These variants remain separate profiles pending review, even when they appear to be spelling corrections.')}</p>${table(['ΔΑΙ',L('Ονόματα στις πηγές','Names in source')],db.coverage.identity_conflicts.map(c=>`<tr><td>${E(c.registration)}</td><td>${c.names.map(E).join('<br>')}</td></tr>`).join(''))}</section>`+sourceInventory();}
  function notFound(){return pageHead(L('Η σελίδα δεν βρέθηκε','Page not found'))+`<a class="button" href="#home">${L('Επιστροφή στην αρχική','Back to overview')}</a>`;}
  function header(){const active={player:'players',team:'events',event:'events'}[current.name]||current.name;
    return `<header class="topbar"><div class="wrap top-inner"><a class="brand" href="#home"><span class="brandmark" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="m19 18 8 9" stroke="#f4ab61" stroke-width="5"/><ellipse cx="13" cy="12" rx="10" ry="9" fill="#8adfd2"/><circle cx="27" cy="5" r="3" fill="white"/></svg></span><span><b>POFEPA <span>STATS</span></b><small>${L('ΑΓΩΝΕΣ & ΑΘΛΗΤΕΣ','MATCHES & PLAYERS')}</small></span></a><nav class="nav" aria-label="${L('Κύρια πλοήγηση','Main navigation')}">${navItems.map(([r,el,en])=>`<a href="#${r}" class="${active===r?'active':''}" ${active===r?'aria-current="page"':''}>${L(el,en)}</a>`).join('')}</nav><button class="lang" id="lang" aria-label="${L('Switch to English','Αλλαγή σε Ελληνικά')}">${L('EN','ΕΛ')}</button></div></header>`;
  }
  // The language button sits outside the scrolling nav so it stays visible on
  // narrow screens. Keep the active section in view and fade clipped edges.
  function navEdges(nav){const hidden=nav.scrollWidth-nav.clientWidth;nav.classList.toggle('fade-start',nav.scrollLeft>1);nav.classList.toggle('fade-end',hidden-nav.scrollLeft>1);}
  function syncNav(){const nav=app.querySelector?.('.nav');if(!nav)return;const active=nav.querySelector('[aria-current]');
    if(active&&nav.scrollWidth>nav.clientWidth){const a=active.getBoundingClientRect(),n=nav.getBoundingClientRect();if(a.left<n.left||a.right>n.right)nav.scrollLeft+=a.left-n.left-(n.width-a.width)/2;}
    navEdges(nav);}
  const snapshotMap=map(db.snapshots);
  async function loadPlayer(id){const p=players.get(id);if(!p||!db.lazy)return;
    const records=await fetchData(p.archive),record=records[id];
    matchesByPlayer.set(id,record.matches);
    playerRankComparisons.set(id,record.rank_comparisons||{});
    playerHistories.set(id,record.history.map(([sid,row])=>({...snapshotMap.get(sid),row})));
  }
  async function prepareView(r){if(!db.lazy)return db.matches;
    if(r.name==='players'){const snapshot=rosterSnapshot(r.params.get('category'));if(snapshot&&!snapshot.rows)snapshot.rows=await fetchData(snapshot.archive);}
    if(r.name==='team'||(r.name==='matches'&&r.params.get('view')==='teams')||(r.name==='event'&&events.get(r.id)?.kind==='fixtures')){
      if(!db.fixtures&&db.archives?.fixtures)db.fixtures=await fetchData(db.archives.fixtures);
    }
    if(r.name==='event'&&events.get(r.id)?.draw_archive){
      db.cup_draws||={};
      if(!db.cup_draws[r.id])db.cup_draws[r.id]=await fetchData(events.get(r.id).draw_archive);
    }
    if(r.name==='about'&&db.archives?.about){
      const archive=await fetchData(db.archives.about);
      db.sources=archive.sources;db.coverage=archive.coverage;
      for(const source of db.sources)sources.set(source.id,source);
    }
    if(r.name==='player'){await loadPlayer(r.id);return db.recent_matches;}
    if(r.name==='h2h'){const id=r.params.get('p1');await loadPlayer(id);return matchesByPlayer.get(id)||[];}
    if(r.name==='matches'&&r.params.get('view')!=='teams')return loadMatchIndex();
    if(r.name==='event'&&events.get(r.id)?.kind==='singles')return fetchData(events.get(r.id).archive);
    if(r.name==='rankings'){
      const region=r.params.get('region')||'national',all=db.snapshots.filter(s=>s.region===region);
      const periods=[...new Set(all.map(s=>s.period))].sort().reverse(),period=periods.includes(r.params.get('period'))?r.params.get('period'):periods[0];
      const kind=r.params.get('class')||'BET',relevant=all.filter(s=>s.period===period),ages=relevant.filter(s=>s.list.startsWith(kind+' ')).map(s=>s.list.slice(4));
      const age=ages.includes(r.params.get('age'))?r.params.get('age'):ages.includes('40-49')?'40-49':ages[0];
      const list=kind==='WOMEN'?'ΓΥΝΑΙΚΩΝ':kind==='GENERAL'?'ΓΕΝΙΚΟΣ':kind+' '+age;
      const snap=relevant.find(s=>s.list===list);if(snap&&!snap.rows)snap.rows=await fetchData(snap.archive);
    }
    return db.recent_matches;
  }
  // Detail routes take the record's name; a missing record or unknown route is "not found".
  function pageTitle(view){const record={player:players,event:events,team:clubs}[current.name]?.get(current.id)?.name;
    if(view===notFound||(['player','event','team'].includes(current.name)&&!record))return L('Η σελίδα δεν βρέθηκε','Page not found');
    return record||navItems.find(n=>n[0]===current.name)?.[lang==='el'?1:2]||{about:L('Κάλυψη & πηγές','Coverage & sources')}[current.name]||'POFEPA Stats';}
  let renderSerial=0;
  function renderError(error,reload=false){
    app.innerHTML=header()+`<main id="main" class="wrap main"><h1>${L('Αδυναμία φόρτωσης','Unable to load data')}</h1><p>${reload?L('Ανανεώστε τη σελίδα για να φορτώσετε ξανά το αρχείο.','Reload the page to load the archive again.'):L('Δοκιμάστε ξανά.','Please retry.')}</p><button id="${reload?'reload':'retry'}">${reload?L('Ανανέωση σελίδας','Reload page'):L('Επανάληψη','Retry')}</button></main>`;syncNav();
    console.error(error);
  }
  async function render(){const serial=++renderSerial;current=route();document.documentElement.lang=lang;
    const pending=prepareView(current);
    if(db.lazy){app.innerHTML=header()+`<main id="main" class="wrap main"><p role="status">${L('Φόρτωση αρχείου…','Loading archive…')}</p></main>`;syncNav();}
    let loaded;try{loaded=await pending;}catch(error){if(serial===renderSerial)renderError(error);return;}
    if(serial!==renderSerial)return;db.matches=loaded;

    const view={home,rankings,players:playerList,player:()=>playerDetail(current.id),matches:matchList,events:eventList,event:()=>eventDetail(current.id),team:()=>teamDetail(current.id),h2h:compare,about}[current.name]||notFound;
    let body;try{body=view();}catch(error){renderError(error,true);return;}
    document.title=pageTitle(view)+' · POFEPA Stats';
    app.innerHTML=header()+(current.name==='home'?body:`<main id="main" class="wrap main">${body}</main>`)+`<footer class="footer"><div class="wrap footer-inner"><div><b>POFEPA STATS</b> · ${db.version==='prototype'?L('Πρωτότυπο','Prototype'):'v'+E(db.version)}<br>${L('Ανεξάρτητο αρχείο · όχι επίσημη υπηρεσία ΠΟΦΕΠΑ.','Independent archive · not an official POFΕPA service.')}</div><div>${link('about',L('Κάλυψη & πηγές','Coverage & sources'))}${external('https://www.pofepa.gr/','pofepa.gr')}${external('https://thanospolimeridis.github.io/greek-tt-stats/','Greek TT Archive')}</div></div></footer>`;syncNav();
  }
  async function updateFilter(name,value){const focus=document.activeElement?.id;let pos;try{pos=document.activeElement.selectionStart;}catch{}
    const params=new URLSearchParams(current.params);value?params.set(name,value):params.delete(name);if(!['page','epage','range'].includes(name)){params.delete('page');params.delete('epage');}params.delete('rpage');
    if(name==='region'&&current.name==='rankings'){params.delete('period');params.delete('list');}if(name==='class')params.delete('age');if(name==='season'&&current.name==='matches'&&value&&events.get(params.get('event'))?.season!==value)params.delete('event');if(name==='kind'&&value==='singles')params.delete('competition');
    history.replaceState(history.state,'',href(current.name+(current.id?'/'+current.id:''),Object.fromEntries(params)));await render();
    if(focus){const el=document.getElementById(focus);el?.focus();try{el?.setSelectionRange(pos,pos);}catch{}}
  }
  let searchTimer;
  app.addEventListener('input',event=>{if(event.target.matches('input[data-filter]')){clearTimeout(searchTimer);const {filter}=event.target.dataset,value=event.target.value;searchTimer=setTimeout(()=>updateFilter(filter,value),160);}
    else if(event.target.matches('.player-picker [role=combobox]')){pickerParts(event.target).chosen.value='';showSuggestions(event.target);}});
  // Suggestions are chosen on pointer-up (a touch scroll of the list cancels the
  // pointer, so it never chooses); mouse-down only keeps focus in the combobox.
  app.addEventListener('mousedown',event=>{if(event.target.closest?.('.picker-list'))event.preventDefault();});
  app.addEventListener('pointerup',event=>{const option=event.target.closest?.('.picker-list [role=option]');if(option)choosePlayer(option.closest('.player-picker').querySelector('[role=combobox]'),option);});
  app.addEventListener('focusout',event=>{const input=event.target;if(input.matches?.('.player-picker [role=combobox]'))setTimeout(()=>{if(document.activeElement!==input&&input.isConnected)closePicker(input);},150);});
  app.addEventListener('change',event=>{if(event.target.matches('select[data-draw-zoom]')){const image=document.getElementById('draw-canvas-'+event.target.dataset.drawZoom);image.style.width=event.target.value==='fit'?'100%':Math.round(Number(image.dataset.width)*Number(event.target.value))+'px';}if(event.target.matches('select[data-filter]'))updateFilter(event.target.dataset.filter,event.target.value);});
  function jumpToSection(id){const section=document.getElementById(id);if(section){section.focus({preventScroll:true});section.scrollIntoView({block:'start'});}}
  function showRankingPoint(event){const point=event.target.closest('[data-rank-point]');if(point){const readout=document.getElementById('ranking-readout');if(readout)readout.textContent=point.dataset.rankPoint;}}
  app.addEventListener('focusin',showRankingPoint);
  // The chart is one tab stop; arrow keys, Home and End step through its points.
  // Player picker keys: arrows move through suggestions, Enter chooses, Escape closes.
  function pickerKey(event){const input=event.target;
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();movePicker(input,event.key==='ArrowDown'?1:-1);return;}
    const {list}=pickerParts(input),open=!list.hidden,options=[...list.querySelectorAll('[role=option]')];
    if(event.key==='Enter'&&open&&options.length){const active=document.getElementById(input.getAttribute('aria-activedescendant')||'')||(options.length===1?options[0]:null);if(active){event.preventDefault();choosePlayer(input,active);}}
    else if(event.key==='Escape'&&open){event.preventDefault();closePicker(input);}}
  app.addEventListener('keydown',event=>{if(event.target.matches?.('.player-picker [role=combobox]'))return pickerKey(event);
    const chart=event.target.closest?.('.athlete-ranking-chart');if(!chart)return;
    const points=[...chart.querySelectorAll('[data-rank-point]')],steps={ArrowLeft:-1,ArrowDown:-1,ArrowRight:1,ArrowUp:1};if(!points.length)return;
    let index=Number(chart.dataset.active??points.length-1);
    if(event.key in steps)index=Math.min(points.length-1,Math.max(0,index+steps[event.key]));else if(event.key==='Home')index=0;else if(event.key==='End')index=points.length-1;else return;
    event.preventDefault();chart.dataset.active=index;points.forEach((point,i)=>point.classList.toggle('active',i===index));
    const readout=document.getElementById('ranking-readout');if(readout)readout.textContent=points[index].dataset.rankPoint;});
  app.addEventListener('scroll',event=>{if(event.target.classList?.contains('nav'))navEdges(event.target);},true);
  app.addEventListener('mouseover',showRankingPoint);
  app.addEventListener('click',event=>{showRankingPoint(event);const button=event.target.closest('button');if(!button)return;
    if(button.dataset.chartRange){updateFilter('range',button.dataset.chartRange);return;}
    if(button.dataset.drawEnd!==undefined){const viewport=document.getElementById('draw-viewport-'+button.dataset.drawEnd);viewport.scrollTo({left:viewport.scrollLeft+viewport.clientWidth*.8,behavior:'auto'});return;}
    if(button.dataset.jump){jumpToSection(button.dataset.jump);return;}
    if(button.id==='retry')render();
    if(button.id==='reload')location.reload();
    if(button.id==='lang'){lang=lang==='el'?'en':'el';try{localStorage.setItem('pofepa-lang',lang);}catch{}render();}
    if(button.dataset.page!==undefined){const key=button.dataset.pageKey||'page',athlete=current.name==='player',rounds=current.name==='event'&&events.get(current.id)?.kind==='fixtures';updateFilter(key,button.dataset.page).then(()=>{if(athlete)jumpToSection(key==='epage'?'athlete-events':'athlete-matches');else if(rounds)jumpToSection('fixture-round-0');else if(current.name==='about'&&aboutJumps[key])jumpToSection(aboutJumps[key]);});}
    if(button.dataset.export)exportData(button.dataset.export,button.dataset.id);
  });
  app.addEventListener('submit',event=>{event.preventDefault();const form=event.target;
    if(form.id==='home-search')location.hash=href('players',{q:new FormData(form).get('q')}).slice(1);
    if(form.id==='compare-form'){const a=pickedPlayer(form,'p1'),b=pickedPlayer(form,'p2');
      if(!a||!b||a.id===b.id){document.getElementById('compare-error').textContent=L('Επίλεξε δύο διαφορετικούς αθλητές από τις προτάσεις.','Select two different players from the suggestions.');return;}
      location.hash=href('h2h',{p1:a.id,p2:b.id}).slice(1);
    }
  });
  function download(href,filename){const a=document.createElement('a');a.href=href;a.download=filename;a.click();}
  // The dataset is offered as the published gzip file. Neither edition parses
  // and re-serialises the 140 MB catalog in the page just to save it.
  function exportDataset(){
    if(db.lazy){download(payload.revision?'data/catalog.json.gz?data='+payload.revision:'data/catalog.json.gz','pofepa-data.json.gz');return;}
    const blob=payload.compressed?new Blob([decodeBase64(payload.compressed)],{type:'application/gzip'}):new Blob([JSON.stringify(db)],{type:'application/json'});
    const url=URL.createObjectURL(blob);download(url,payload.compressed?'pofepa-data.json.gz':'pofepa-data.json');setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function exportData(kind,id){let content,mime,filename;
    if(kind==='data')return exportDataset();
    {let rows=kind==='player'?(matchesByPlayer.get(id)||[]).filter(m=>!param('season')||events.get(m.event).season===param('season')):db.lazy?await fetchData('data/matches.json.gz'):db.matches;
      if(kind==='matches'&&current.name==='matches')rows=rows.filter(matchFilters('singles').keep);
      const quote=v=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replace(/"/g,'""')+'"';
      const evidenceColumns=['document_sources','correction_flags','correction_original_state','correction_reasons'];
      content='\ufeff'+[['date','player_1','player_2','games_1','games_2','event','region','source','sheet_row','identity_1','identity_2',...evidenceColumns],...rows.map(m=>{const evidence=Evidence.csvFields(m,{sourceUrl:id=>sources.get(id)?.url||''});return [m.date,...m.names,...m.score,events.get(m.event).name,m.region,sources.get(m.source).url,m.row,...m.identity,...evidenceColumns.map(k=>evidence[k])];})].map(r=>r.map(quote).join(',')).join('\r\n');mime='text/csv;charset=utf-8';filename='pofepa-matches.csv';}
    const url=URL.createObjectURL(new Blob([content],{type:mime}));download(url,filename);setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  document.querySelector('.skip').addEventListener('click',event=>{event.preventDefault();const main=document.getElementById('main');main.setAttribute('tabindex','-1');main.focus();main.scrollIntoView();});
  // Back/forward returns to where the reader left each page; new pages start at
  // the top. Positions are kept per history entry, so revisiting a section from
  // the menu still opens it at the top.
  const pageHistory=window.history,scrollPositions=new Map();
  if(pageHistory&&'scrollRestoration' in pageHistory)pageHistory.scrollRestoration='manual';
  function historyEntry(){if(!pageHistory)return null;let id=pageHistory.state?.entry;
    if(!id){id=Date.now().toString(36)+Math.random().toString(36).slice(2,8);try{pageHistory.replaceState({...pageHistory.state,entry:id},'');}catch{}}return id;}
  let currentEntry=historyEntry();
  window.addEventListener('scroll',()=>{if(currentEntry)scrollPositions.set(currentEntry,window.scrollY);},{passive:true});
  // Announce the new page to screen readers and start keyboard focus there.
  function focusPage(){const target=app.querySelector?.('main h1')||app.querySelector?.('main');if(!target)return;
    if(!target.hasAttribute('tabindex'))target.setAttribute('tabindex','-1');target.focus({preventScroll:true});}
  window.addEventListener('hashchange',()=>{clearTimeout(searchTimer);currentEntry=historyEntry();const top=scrollPositions.get(currentEntry)||0;
    if(!top)window.scrollTo(0,0);render().then(()=>{window.scrollTo(0,top);focusPage();});});
  let chartResizeTimer,chartWidth=window.innerWidth;
  window.addEventListener('resize',()=>{
    if(window.innerWidth===chartWidth)return;chartWidth=window.innerWidth;clearTimeout(chartResizeTimer);
    chartResizeTimer=setTimeout(()=>{syncNav();if(current.name==='player'){const panel=document.querySelector('.athlete-chart-panel');if(panel)panel.innerHTML=historyChart(combinedRankingHistory(current.id));}},120);
  });
  await render();
})().catch(error=>{document.getElementById('app').innerHTML='<main class="wrap main"><h1>Unable to load archive / Αδυναμία φόρτωσης</h1><p>Please reload the page / Ανανεώστε τη σελίδα.</p></main>';console.error(error);});
