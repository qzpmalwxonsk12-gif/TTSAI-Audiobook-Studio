/* Read-only browser check; never starts generation or changes the real library. */
const {chromium}=require(process.env.TTSAI_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8767/');
  await page.locator('[data-usage-provider=elevenlabs] progress').waitFor();
  assert.equal(await page.locator('.usage-card').count(),4);
  assert.match(await page.locator('[data-usage-provider=elevenlabs]').textContent(),/credits/);
  for(const p of ['gemini','hume']){
   assert.match(await page.locator('[data-usage-provider='+p+']').textContent(),/Account balance unavailable/);
   assert.equal(await page.locator('[data-usage-provider='+p+'] progress').count(),0);
  }
  await page.locator('#refreshUsage').click();
  await page.waitForFunction(()=>!document.getElementById('refreshUsage').disabled);
  assert.deepEqual(errors,[]);
  if(process.env.TTSAI_SCREENSHOT)await page.screenshot({path:process.env.TTSAI_SCREENSHOT,fullPage:true});
  console.log(JSON.stringify({passed:true,checks:['three provider cards','actual ElevenLabs balance','unknown balances not rendered as zero','manual refresh'],javascriptErrors:errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
