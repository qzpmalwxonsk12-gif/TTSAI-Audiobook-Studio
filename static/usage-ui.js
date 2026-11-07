let usageLoading=false;
const usageDashboards={gemini:'https://aistudio.google.com/usage',elevenlabs:'https://elevenlabs.io/app/subscription',hume:'https://app.hume.ai/billing',deepgram:'https://console.deepgram.com/'};
const usageNumber=n=>Number(n).toLocaleString();
function usageMeter(percent,label){return percent===null?'':`<progress max="100" value="${Math.min(100,Math.max(0,percent))}" aria-label="${esc(label)}"></progress>`}
async function loadUsage(){
 if(usageLoading)return;
 usageLoading=true;const bid=book?.id;
 try{
  const data=await api('/usage'+(bid?'?book_id='+encodeURIComponent(bid):''));
  if(book?.id!==bid)return;
  $('usagePeriod').textContent='App activity: '+data.month_utc+' (UTC) · Account balances use the provider’s billing cycle';
  $('usageCards').innerHTML=data.providers.map(p=>{
   const a=p.account,local=p.local;
   let account='<p class="hint">Account balance unavailable here. Check the provider dashboard; an accepted key does not confirm a free plan.</p>';
   if(a?.available){
    const pct=a.percent_used===null?'Percentage unavailable':a.percent_used+'% used';
    const reset=Number.isFinite(a.resets_at)?' · Resets '+new Date(a.resets_at*1000).toLocaleDateString():'';
    account='<p class="usage-total">'+usageNumber(a.used)+' / '+usageNumber(a.limit)+' credits</p><strong>'+pct+'</strong>'+usageMeter(a.percent_used,'ElevenLabs account usage')+'<p>'+usageNumber(a.remaining)+' remaining · '+esc(a.tier)+' plan'+esc(reset)+'</p><small>Provider balance checked '+esc(new Date(a.checked_at).toLocaleTimeString())+'</small>';
   }else if(a){account='<p class="hint">'+esc(a.message)+'</p>'}
   return '<article class="usage-card" data-usage-provider="'+p.provider+'"><h3>'+providerLabels[p.provider]+' <small>'+(p.connected?'Key added':'No key')+'</small></h3>'+account+'<p class="usage-local">This app this month: <b>'+usageNumber(local.requests)+'</b> requests · <b>'+usageNumber(local.speech_characters)+'</b> speech characters<br>'+usageNumber(local.requests_today)+' requests today</p><a href="'+usageDashboards[p.provider]+'" target="_blank" rel="noopener noreferrer">Provider dashboard ↗</a></article>';
  }).join('');
  const j=data.job;
  $('jobUsage').innerHTML=j?'<div class="usage-job"><strong>Latest job allowance · '+esc(j.state)+'</strong><div class="grid two"><div><p>'+usageNumber(j.requests)+' / '+usageNumber(j.request_limit)+' requests · '+j.request_percent+'% used</p>'+usageMeter(j.request_percent,'Job request allowance')+'</div><div><p>'+usageNumber(j.speech_characters)+' / '+usageNumber(j.character_limit)+' speech characters · '+j.character_percent+'% used</p>'+usageMeter(j.character_percent,'Job text allowance')+'</div></div><small>This is the app’s safety allowance, separate from your provider quota. Mapping input tokens are not included in speech characters.</small></div>':'';
 }catch(e){$('usagePeriod').textContent='Usage unavailable: '+e.message}
 finally{usageLoading=false;if(book?.id!==bid)setTimeout(loadUsage,0)}
}
$('refreshUsage').onclick=()=>busy($('refreshUsage'),loadUsage);
loadUsage();
setInterval(()=>{if(!document.hidden)loadUsage()},30000);
