let connectionsState={},timeline=[],playingArtifact=null,highlighted=null,syncing=false,playbackEpoch=0;
const providerLabels={gemini:'Gemini',elevenlabs:'ElevenLabs',hume:'Hume',deepgram:'Deepgram'};
async function loadStatus(){
 const r=await api('/connections');connectionsState=r.connected;
 status={voices:['am_adam','am_echo','am_eric','am_fenrir','am_liam','am_michael','am_onyx','am_puck','am_santa','af_heart','af_bella','af_nicole','af_sarah','af_sky','af_nova','af_river','af_jessica'],models:[]};
 $('engineStatus').textContent=Object.keys(connectionsState).filter(p=>connectionsState[p]).map(p=>providerLabels[p]).join(' · ')||'Add free API keys in Cloud connections';
 updateProviderNote();
}
function applyBookSettings(){
 const s=book.settings||{};
 $('mappingProvider').value=s.mapping_provider||'gemini';$('ttsProvider').value=s.tts_provider||'gemini';
 updateModels(s.model);$('cloudCharLimit').value=s.max_cloud_chars||10000;
 $('mode').value=s.mode||'full';$('thoughts').checked=!!s.thoughts;$('fallback').checked=!!s.allow_unresolved;
 renderCast();updateProviderNote();
}
function updateModels(model){
 const models=$('mappingProvider').value==='gemini'?['gemini-3.8-flash','gemini-3.5-flash','gemini-2.5-flash']:['qwen3:4b'];
 $('model').innerHTML=models.map(m=>'<option>'+m+'</option>').join('');if(models.includes(model))$('model').value=model;
}
function updateProviderNote(){
 const p=$('ttsProvider').value;
 $('providerNote').textContent=p==='local'?'Existing local speech mode requires installed Kokoro models.':
 (connectionsState.gemini?'Gemini mapping key added. ':'Gemini mapping key needed. ')+(connectionsState[p]?providerLabels[p]+' speech key added. ':providerLabels[p]+' speech key needed. ')+
 'Free quotas vary. A job stops on rate limits or its text allowance; it never switches to a paid provider. '+(p==='elevenlabs'?'Voice direction is recorded for casting; this prototype sends exact text without acting tags.':'');
}
function renderChapterList(){
 $('chapterList').innerHTML=book.chapters.length?book.chapters.map(c=>'<button data-chapter="'+c.id+'"><strong>'+c.ordinal+'. '+esc(c.title)+'</strong><small>'+c.passages+' passages · '+(c.mapped?'Mapped':'Not mapped')+' · '+c.review_count+' flagged</small></button>').join(''):'<p>No chapters yet. Add chapter 1 to begin.</p>';
 if(!book.chapters.length){$('source').textContent='Add a chapter to read and review it.';$('segments').innerHTML='';}
}
$('mappingProvider').onchange=()=>{updateModels();if($('mappingProvider').value==='ollama')$('ttsProvider').value='local';updateProviderNote();if(book)renderCast()};
$('ttsProvider').onchange=()=>{if($('ttsProvider').value!=='local'&&$('mappingProvider').value!=='gemini'){$('mappingProvider').value='gemini';updateModels()}updateProviderNote();if(book)renderCast()};
$('connections').onclick=async()=>{
 try{await loadStatus();$('connectionInputs').innerHTML=['gemini','elevenlabs','hume','deepgram'].map(p=>'<label>'+providerLabels[p]+' '+(connectionsState[p]?'· key added':'· not connected')+'<input id="key-'+p+'" type="password" autocomplete="new-password" placeholder="Paste key to add or replace"></label><label><input id="clear-'+p+'" type="checkbox"> Remove this connection</label>').join('');$('connectionDialog').showModal()}catch(e){toast(e.message)}
};
$('connectionForm').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{for(const p of ['gemini','elevenlabs','hume','deepgram']){const value=$('key-'+p).value.trim();if(value||$('clear-'+p).checked)await api('/connections/'+p,{key:$('clear-'+p).checked?'':value},'PUT');$('key-'+p).value=''}$('connectionDialog').close();await loadStatus();toast('Connections saved for this server session.')})};
$('addChapter').onclick=()=>{$('chapterForm').reset();$('chapterNumber').value=Math.max(0,...book.chapters.map(c=>c.ordinal))+1;$('chapterDialog').showModal()};
$('chapterFile').onchange=async()=>{const f=$('chapterFile').files[0];if(!f)return;if(f.size>1000000){toast('Use a TXT chapter smaller than 1 MB.');return}$('chapterText').value=await f.text()};
$('chapterForm').onsubmit=e=>{e.preventDefault();busy(e.submitter,async()=>{const r=await api('/books/'+book.id+'/chapters',{number:Number($('chapterNumber').value),title:$('chapterTitle').value,text:$('chapterText').value});$('chapterDialog').close();await refreshBook();await library();await loadChapter(r.id);switchTab('script');toast('Chapter saved. Choose your providers and start mapping.')})};
function currentVoice(){
 if($('ttsProvider').value==='local')return localVoice();
 return {provider:$('ttsProvider').value,voice_id:$('cloudVoiceId').value,direction:$('cloudDirection').value,...($('ttsProvider').value==='deepgram'?{speed:Number($('deepgramSpeed').value),pitch_semitones:Number($('deepgramPitch').value)}:{})};
}
async function openVoice(id){
 openLocalVoice(id);const provider=$('ttsProvider').value,isCloud=provider!=='local';
 $('localVoiceFields').hidden=isCloud;$('cloudVoiceFields').hidden=!isCloud;$('cloudVoiceId').required=isCloud;
 if(!isCloud)return;
 $('deepgramControls').hidden=provider!=='deepgram';
 const saved=editingChar?.cloud_voices?.[provider];$('deepgramSpeed').value=saved?.speed??1;$('deepgramPitch').value=saved?.pitch_semitones??0;$('cloudVoiceId').value=saved?.voice_id||'';$('cloudDirection').value=saved?.direction||'';
 $('castingReason').textContent=saved?.reason||'Step 1 assigns a voice from the provider catalog; you can choose one yourself.';
 $('cloudVoiceSelect').innerHTML='<option value="">Loading voices…</option>';
 try{const voices=await api('/cloud-voices/'+provider);$('cloudVoiceSelect').innerHTML='<option value="">Choose a voice</option>'+voices.map(v=>'<option value="'+esc(v.id)+'">'+esc(v.name+' · '+v.description)+'</option>').join('');$('cloudVoiceSelect').value=saved?.voice_id||''}
 catch(e){$('cloudVoiceSelect').innerHTML='<option>Catalog unavailable</option>';$('castingReason').textContent=e.message+' You may enter an existing voice ID.'}
}
$('cloudVoiceSelect').onchange=()=>{if($('cloudVoiceSelect').value)$('cloudVoiceId').value=$('cloudVoiceSelect').value};
async function previewCharacter(button,id){
 const c=book.cast.find(c=>c.id===id),p=$('ttsProvider').value,v=p==='local'?c.voice:c.cloud_voices?.[p];
 if(!v)throw Error('Run mapping to assign a voice, or use Edit voice first.');await preview(button,v);
}
function resetTimeline(){timeline=[];playingArtifact=null;highlighted=null;playbackEpoch++;document.querySelectorAll('.playing-passage').forEach(e=>e.classList.remove('playing-passage'))}
function setTimeline(a,data){timeline=data.segments;playingArtifact=a;$('playbackNote').textContent=data.stale?'Earlier audio: speaker edits require regeneration.':timeline.length?'Text follows each spoken passage.':'This earlier export has no text timings. Regenerate to enable tracking.'}
function invalidatePlayback(){if(!$('mainAudio').getAttribute('src'))return;$('mainAudio').pause();resetTimeline();$('playbackNote').textContent='Text or cast changed. Regenerate audio to hear corrections.'}
async function syncPlayback(){
 if(syncing||!timeline.length||!$('followAudio').checked||document.querySelector('dialog[open]'))return;
 const t=$('mainAudio').currentTime,s=timeline.find(s=>t>=s.start&&t<s.end);
 if(!s){document.querySelectorAll('.playing-passage').forEach(e=>e.classList.remove('playing-passage'));highlighted=null;return}
 if(s.id===highlighted&&chapter?.id===s.chapter_id&&document.querySelector('#source .playing-passage'))return;
 const epoch=playbackEpoch;syncing=true;
 try{
  if(chapter?.id!==s.chapter_id)await loadChapter(s.chapter_id);
  if(epoch!==playbackEpoch)return;
  document.querySelectorAll('.playing-passage').forEach(e=>e.classList.remove('playing-passage'));
  const el=document.querySelector('#source [data-segment="'+s.id+'"]');
  if(el){el.classList.add('playing-passage');if(highlighted!==s.id)el.scrollIntoView({block:'center',behavior:'smooth'})}highlighted=s.id;
 }catch(e){toast(e.message)}finally{syncing=false}
}
$('mainAudio').addEventListener('timeupdate',syncPlayback);$('mainAudio').addEventListener('seeked',syncPlayback);
$('seekSegment').onclick=()=>{const t=timeline.find(t=>t.id===editingSegment?.id);if(!t)return;$('mainAudio').currentTime=t.start;$('segmentDialog').close();$('mainAudio').play().catch(e=>toast(e.message))};
(async()=>{try{await loadStatus();await library();const all=await api('/books');const last=localStorage.getItem('ttsai-book');if(all.length)await selectBook(all.find(b=>b.id===last)?.id||all[0].id)}catch(e){toast(e.message)}})();
