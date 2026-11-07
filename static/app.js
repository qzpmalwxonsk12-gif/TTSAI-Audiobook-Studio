const $=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let book=null,chapter=null,status=null,editingChar=null,editingSegment=null,tab='cast',autoListen=false,played=new Set(),polling=false;
async function api(path,body,method='POST'){
 const r=await fetch('/api'+path,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;
}
let toastTimer;
const shownFailures=new Set();
function toast(m){$('toast').textContent=m;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,8500)}
async function busy(b,fn){const t=b.textContent;b.disabled=true;try{await fn()}catch(e){toast(e.message)}finally{b.disabled=false;b.textContent=t}}
function duration(s){return Math.floor(s/60)+'m '+Math.round(s%60)+'s'}
function voiceName(v){return v.replace(/^[ab][fm]_/,'').replace(/^./,c=>c.toUpperCase())+' · '+(v[1]==='m'?'M':'F')}
async function loadLocalStatus(){status=await api('/status');$('engineStatus').textContent=(status.speech_ready?'Speech ready':'Speech setup needed')+' · '+(status.models.length?'Analysis ready':'Analysis model unavailable');if(status.models.length)$('model').innerHTML=status.models.map(m=>'<option>'+esc(m)+'</option>').join('')}
async function library(){const books=await api('/books');$('library').innerHTML=books.map(b=>'<button data-book="'+b.id+'" class="'+(book?.id===b.id?'active':'')+'">'+esc(b.title)+'<small>'+b.chapters+' chapters</small></button>').join('')}
async function selectBook(id){book=await api('/books/'+id);chapter=null;autoListen=false;played.clear();$('mainAudio').pause();$('mainAudio').removeAttribute('src');$('playerBar').hidden=true;if(typeof resetTimeline==='function')resetTimeline();$('welcome').hidden=true;$('studio').hidden=false;renderBook();applyBookSettings();localStorage.setItem('ttsai-book',id);await library();if(book.chapters.length)await loadChapter(book.chapters[0].id);if(typeof loadUsage==='function')loadUsage()}
function renderBook(){
 $('bookTitle').textContent=book.title;$('subtitle').textContent='Your cast, your reading pace. Cloud AI, saved voices and reviewable chapters.';
 const reviews=book.chapters.reduce((n,c)=>n+c.review_count,0);
 $('stats').innerHTML=[[book.chapters.length,'Chapters'],[Math.max(0,book.cast.length-1),'Character voices'],[reviews,'Passages to review'],[book.chapters.filter(c=>c.mapped).length,'Chapters mapped']].map(([n,t])=>'<div class="stat"><strong>'+n+'</strong><span>'+t+'</span></div>').join('');
 $('reviewBadge').textContent=reviews?'('+reviews+')':'';
 const scope=$('scope').value,sel=$('chapterSelect').value,opts=book.chapters.map(c=>'<option value="'+c.id+'">'+esc(c.title)+'</option>').join('');
 $('scope').innerHTML='<option value="">Entire book</option>'+opts;$('scope').value=scope;
 $('chapterSelect').innerHTML=opts;if(sel)$('chapterSelect').value=sel;
 $('projectDownload').href='/api/books/'+book.id+'/project';renderCast();renderJobs();renderExports();renderChapterList();
}
function renderCast(){
 const provider=$('ttsProvider').value;
 $('cast').innerHTML=book.cast.map(c=>{const v=c.cloud_voices?.[provider];const summary=provider==='local'?voiceName(c.voice.a)+' + '+voiceName(c.voice.b):v?v.voice_id+' · '+(v.direction||'Saved voice'):'Run Step 1 to assign a voice';return '<article class="cast-card"><div class="avatar">'+esc(c.name[0])+'</div><h3>'+esc(c.name)+'</h3><p class="aliases">'+esc(c.aliases.join(' · ')||'Persistent character identity')+'</p><p class="description">'+esc(c.description||'Review this character’s voice before production.')+'</p><div class="voice-recipe">'+esc(summary)+'</div><div class="actions"><button data-char-preview="'+c.id+'">▶ Preview</button><button data-char-edit="'+c.id+'">Edit voice</button></div></article>'}).join('');
}
function renderJobs(){
 const failure=book.jobs[0];if(failure?.state==='failed'&&!shownFailures.has(failure.id)){shownFailures.add(failure.id);toast('Attempt stopped: '+failure.message+' Start again when ready; saved progress is kept.')}
 $('jobs').innerHTML=book.jobs.filter(j=>j.state!=='failed').slice(0,3).map(j=>'<div class="job"><div class="job-head"><strong class="state-'+j.state+'">'+esc({map:'Story mapping',render:'Audiobook production',listen:'Chapter-buffered listening'}[j.type])+' · '+esc(j.state.replace('_',' '))+'</strong>'+(['running','queued'].includes(j.state)?'<button data-job="'+j.id+'" data-action="pause">'+(j.pause?'Pausing…':'Pause')+'</button>':['paused','needs_review'].includes(j.state)?'<button data-job="'+j.id+'" data-action="resume">Resume</button>':'')+'</div><p>'+esc(j.message||'Waiting to start')+'</p><progress max="'+Math.max(1,j.total)+'" value="'+j.completed+'"></progress><p>'+j.completed+' / '+j.total+' chapters</p></div>').join('');
 const active=book.jobs.some(j=>['running','queued'].includes(j.state));['map','render','listen','addCharacter','mapChapter','renderChapter','addChapter'].forEach(id=>$(id).disabled=active);
}
function renderExports(){
 const visible=book.artifacts.filter(a=>$('olderExports').checked||!a.stale);
 const partial=a=>a.id.startsWith('incomplete-');
 const card=a=>'<article class="export"><div><strong>'+esc((partial(a)?'Incomplete · ':'')+(a.chapter_title||'Complete audiobook')+' · '+(a.mode==='dialogue'?'Dialogue only':'Full narration'))+'</strong><p>'+duration(a.seconds)+' · '+(a.format||'WAV')+' · '+esc(a.created)+' UTC</p>'+(partial(a)?'<p class="hint">Recovered completed passages. This recording ends before the chapter does.</p>':'')+(a.stale?'<span class="stale">Earlier revision — regenerate for your latest changes.</span>':'')+'</div><div class="actions"><button data-play="'+a.id+'">▶ Listen</button><a class="button primary" href="/api/artifacts/'+a.id+'?download=true">Download ↓</a></div></article>';
 const complete=visible.filter(a=>!partial(a)),incomplete=visible.filter(partial);
 $('exports').innerHTML=visible.length?(complete.map(card).join('')+(incomplete.length?'<h3>Incomplete audio</h3>'+incomplete.map(card).join(''):'')):'<div class="empty">Your audio will appear here as chapters finish.</div>';
}
async function loadChapter(id){chapter=await api('/chapters/'+id);$('chapterSelect').value=id;$('source').innerHTML=ReviewText.marked(chapter.source,chapter.segments);renderSegments()}
function renderSegments(){
 if(!chapter)return;const people=Object.fromEntries(book.cast.map(c=>[c.id,c.name]));const list=chapter.segments.filter(s=>!$('reviewOnly').checked||s.review);
 $('segments').innerHTML=list.length?list.map(s=>'<article class="passage '+(s.review?'flagged':'')+'"><div><span class="speaker">'+esc(s.kind==='narration'?'Narrator':people[s.speaker]||'Unknown speaker')+'</span><span class="kind">'+s.kind+'</span>'+(s.review?'<span class="flag">'+(s.mapped?'Needs review':'Not analyzed')+'</span>':s.locked?'<span class="kind">Reviewed ✓</span>':'')+'</div><div class="text">'+(s.review?ReviewText.context(chapter.source,s):esc(s.text))+'</div><button data-segment="'+s.id+'">Review</button></article>').join(''):'<div class="empty">No passages need review in this chapter.</div>';
}
function switchTab(t){tab=t;['cast','script','exports'].forEach(n=>$(n+'Tab').hidden=n!==t);document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===t))}
function localVoice(){return {engine:'kokoro-v1.0',a:$('voiceA').value,b:$('voiceB').value,mix:Number($('voiceMix').value),speed:Number($('voiceSpeed').value),lang:'en-us'}}
function updateSliders(){$('mixValue').textContent=Math.round($('voiceMix').value*100)+'%';$('speedValue').textContent=Number($('voiceSpeed').value).toFixed(2)+'×'}
function openLocalVoice(id){
 editingChar=book.cast.find(c=>c.id===id)||null;const c=editingChar||{name:'',aliases:[],description:'',voice:{a:'am_michael',b:'am_puck',mix:.35,speed:1}};
 $('voiceHeading').textContent=editingChar?'Direct '+c.name:'Add a character';
 $('charName').value=c.name;$('charAliases').value=c.aliases.join(', ');$('charDescription').value=c.description;
 ['voiceA','voiceB'].forEach(id=>$(id).innerHTML=(status?.voices||[]).map(v=>'<option value="'+v+'">'+esc(voiceName(v))+'</option>').join(''));
 $('voiceA').value=c.voice.a;$('voiceB').value=c.voice.b;$('voiceMix').value=c.voice.mix;$('voiceSpeed').value=c.voice.speed;updateSliders();
 $('voiceAudio').hidden=true;$('voiceAudio').pause();$('previewTiming').textContent='';
 $('mergeBox').hidden=!editingChar||editingChar.name==='Narrator';
 $('mergeTarget').innerHTML=book.cast.filter(x=>x.id!==id&&x.name!=='Narrator').map(x=>'<option value="'+x.id+'">'+esc(x.name)+'</option>').join('');
 $('voiceDialog').showModal();
}
async function refreshBook(){if(!book)return;book=await api('/books/'+book.id);renderBook();if(chapter&&tab==='script')await loadChapter(chapter.id)}
async function preview(button,voice,text,inDialog=false){
 if(!inDialog&&typeof resetTimeline==='function')resetTimeline();
 await busy(button,async()=>{button.textContent='Generating…';const r=await api('/preview',{voice,...(text?{text}:{})});const a=inDialog?$('voiceAudio'):$('mainAudio');a.src=r.url;a.hidden=false;if(inDialog)$('previewTiming').textContent=duration(r.seconds)+' audio · '+(r.generation_seconds===0?'reused saved audio':r.generation_seconds.toFixed(1)+'s to generate');else{$('playerBar').hidden=false;$('playingTitle').textContent='Voice preview'}await a.play().catch(()=>{});});
}
async function playArtifact(a){
 resetTimeline();$('mainAudio').pause();$('playerBar').hidden=false;$('playingTitle').textContent=a.chapter_title||'Complete audiobook';
 const data=await api('/artifacts/'+a.id+'/timeline');setTimeline(a,data);switchTab('script');$('source').hidden=false;$('segments').hidden=true;$('showSource').textContent='Review list';
 if(data.segments.length)await loadChapter(data.segments[0].chapter_id);else if(a.chapter_id)await loadChapter(a.chapter_id);
 $('mainAudio').src='/api/artifacts/'+a.id;$('mainAudio').play().catch(()=>toast('Press play to listen.'));played.add(a.id);
}
function playNext(){if(!autoListen||!book)return;const a=book.artifacts.filter(a=>a.chapter_id&&!played.has(a.id)&&a.job_id===autoListen).sort((a,b)=>book.chapters.findIndex(c=>c.id===a.chapter_id)-book.chapters.findIndex(c=>c.id===b.chapter_id))[0];if(a)playArtifact(a)}
async function runJob(type,overrides={}){
 const r=await api('/books/'+book.id+'/jobs',{type,mode:$('mode').value,thoughts:$('thoughts').checked,allow_unresolved:$('fallback').checked,chapter_id:$('scope').value||null,model:$('model').value,mapping_provider:$('mappingProvider').value,tts_provider:$('ttsProvider').value,max_cloud_chars:Number($('cloudCharLimit').value),...overrides});
 if(type==='listen'){autoListen=r.id;played.clear();$('mainAudio').pause();$('mainAudio').removeAttribute('src');$('mainAudio').load();switchTab('exports')}
 toast(type==='map'?'Mapping started. You can review the cast as it appears.':'Production started. Progress is saved after each passage.');await refreshBook();
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b)return;try{
 if(b.dataset.close)$(b.dataset.close).close();
 if(b.dataset.book)await selectBook(b.dataset.book);
 if(b.dataset.tab)switchTab(b.dataset.tab);
 if(b.dataset.charEdit)await openVoice(b.dataset.charEdit);
 if(b.dataset.charPreview)await previewCharacter(b,b.dataset.charPreview);
 if(b.dataset.job){await api('/jobs/'+b.dataset.job+'/'+b.dataset.action,{});await refreshBook()}
 if(b.dataset.play){autoListen=false;await playArtifact(book.artifacts.find(a=>a.id===b.dataset.play))}
 if(b.dataset.chapter)await loadChapter(b.dataset.chapter),switchTab('script');
 if(b.dataset.segment){$('mainAudio').pause();editingSegment=chapter.segments.find(s=>s.id===b.dataset.segment);$('segmentQuote').innerHTML=ReviewText.context(chapter.source,editingSegment);$('segmentReason').textContent=editingSegment.reason||'This passage has not been analyzed yet.';$('segmentKind').value=editingSegment.kind;$('segmentSpeaker').innerHTML='<option value="">Choose speaker</option>'+book.cast.map(c=>'<option value="'+c.id+'">'+esc(c.name)+'</option>').join('');$('segmentSpeaker').value=editingSegment.speaker||'';$('segmentFlag').checked=false;$('seekSegment').disabled=!timeline.some(t=>t.id===editingSegment.id);if(!$('segmentDialog').open)$('segmentDialog').showModal();}
 }catch(e){toast(e.message)}
});
$('newBook').onclick=()=>$('importDialog').showModal();
$('sample').onclick=()=>busy($('sample'),async()=>{const s=await api('/sample');const b=await api('/books',s);await selectBook(b.id)});
$('importFile').onchange=async()=>{const f=$('importFile').files[0];if(f){if(f.size>10000000){toast('The prototype accepts up to 10 MB per book.');return}$('importText').value=await f.text();if(!$('importTitle').value)$('importTitle').value=f.name.replace(/\.txt$/i,'')}};
$('importForm').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{const b=await api('/books',{title:$('importTitle').value,text:$('importText').value});$('importDialog').close();$('importForm').reset();await selectBook(b.id)})};
['map','render','listen'].forEach(id=>$(id).onclick=()=>busy($(id),()=>runJob(id)));
$('addCharacter').onclick=()=>openVoice(null).catch(e=>toast(e.message));$('voiceMix').oninput=updateSliders;$('voiceSpeed').oninput=updateSliders;
$('previewVoice').onclick=()=>preview($('previewVoice'),currentVoice(),$('previewText').value,true);
$('voiceForm').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{const body={name:$('charName').value,aliases:$('charAliases').value.split(',').map(x=>x.trim()).filter(Boolean),description:$('charDescription').value,voice:localVoice(),cloud_voice:$('ttsProvider').value==='local'?null:currentVoice()};const saved=await api(editingChar?'/characters/'+editingChar.id:'/books/'+book.id+'/characters',body,editingChar?'PUT':'POST');$('voiceDialog').close();invalidatePlayback();await refreshBook();toast('Character and voice saved. Regenerate audio to hear changes.')})};
$('mergeCharacter').onclick=()=>busy($('mergeCharacter'),async()=>{if(!$('mergeTarget').value)throw Error('Choose a different character first.');await api('/characters/'+editingChar.id+'/merge',{target_id:$('mergeTarget').value});$('voiceDialog').close();invalidatePlayback();await refreshBook();toast('Identities merged. The target voice was retained.')});
$('chapterSelect').onchange=()=>loadChapter($('chapterSelect').value).catch(e=>toast(e.message));$('reviewOnly').onchange=()=>{$('source').hidden=true;$('segments').hidden=false;$('showSource').textContent='Whole chapter';renderSegments()};
$('showSource').onclick=()=>{$('source').hidden=!$('source').hidden;$('segments').hidden=!$('source').hidden;$('showSource').textContent=$('source').hidden?'Whole chapter':'Review list'};
$('segmentForm').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{await api('/segments/'+editingSegment.id,{kind:$('segmentKind').value,speaker:$('segmentSpeaker').value||null,needs_review:$('segmentFlag').checked},'PUT');$('segmentDialog').close();invalidatePlayback();await refreshBook();toast('Speaker saved. Regenerate audio to apply the correction.')})};
$('mainAudio').onended=playNext;$('closePlayer').onclick=()=>{$('mainAudio').pause();$('playerBar').hidden=true;autoListen=false};
setInterval(async()=>{if(polling||!book||document.querySelector('dialog[open]'))return;polling=true;try{const fresh=await api('/books/'+book.id);const changed=fresh.revision!==book.revision;book=fresh;renderJobs();renderExports();if(changed){renderBook();if(chapter&&tab==='script')await loadChapter(chapter.id)}if(autoListen&&$('mainAudio').ended)playNext();else if(autoListen&&!$('mainAudio').getAttribute('src'))playNext()}catch(e){}finally{polling=false}},3000);

$('olderExports').onchange=renderExports;
for(const [id,type] of [['mapChapter','map'],['renderChapter','render']]){
 $(id).onclick=()=>busy($(id),async()=>{
  if(!chapter)throw Error('Select a chapter first.');
  await runJob(type,{chapter_id:chapter.id,mode:$('chapterMode').value,thoughts:$('chapterThoughts').checked,allow_unresolved:$('chapterFallback').value==='narrator'});
 });
}
