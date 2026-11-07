/* Source offsets from Python are Unicode code points, not JavaScript code units. */
(function(root){
 const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const index=(text,n)=>Array.from(text).slice(0,n).join('').length;
 function marked(text,segments,from=0,to=text.length){
  let pos=from,out='';const offsets=[0];for(const ch of text)offsets.push(offsets[offsets.length-1]+ch.length);
  for(const s of segments){
   const a=offsets[s.start],b=offsets[s.end];
   if(a<from||b>to||a<pos)continue;
   out+=escape(text.slice(pos,a))+'<button type="button" class="source-passage '+(s.review?'review-mark':'')+'" data-segment="'+escape(s.id)+'" title="View or change this passage’s speaker">'+escape(text.slice(a,b))+'</button>';pos=b;
  }
  return out+escape(text.slice(pos,to));
 }
 function context(text,s){
  const a=index(text,s.start),b=index(text,s.end);
  const separator=/\r?\n[ \t]*\r?\n/.test(text)?/\r?\n[ \t]*\r?\n+/g:/\r?\n/g;
  const paras=[];let start=0;
  for(const m of text.matchAll(separator)){if(text.slice(start,m.index).trim())paras.push([start,m.index]);start=m.index+m[0].length}
  if(text.slice(start).trim())paras.push([start,text.length]);
  const first=Math.max(0,paras.findIndex(p=>p[1]>a));
  let last=paras.findIndex(p=>p[1]>=b);if(last<0)last=paras.length-1;
  return marked(text,[{...s,review:1}],paras[Math.max(0,first-1)]?.[0]??0,paras[Math.min(paras.length-1,last+1)]?.[1]??text.length);
 }
 const api={marked,context};
 if(typeof module!=='undefined')module.exports=api;else root.ReviewText=api;
})(typeof window!=='undefined'?window:this);
