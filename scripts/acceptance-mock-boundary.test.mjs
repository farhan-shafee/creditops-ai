import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createAcceptanceDetector} from './acceptance-detector.mjs';

test('only exact existing initial-scenario fixture503 with successful fulfillment proof is expected',()=>{
 const row={status:503,method:'GET',url:'http://127.0.0.1:3000/api/scenarios',testId:'the console recovers when its initial scenario request is temporarily unavailable',mockedScenarioProof:{fulfilled:true,detail:'Temporary synthetic test outage'}};
 const detector=createAcceptanceDetector(); detector.observeResponse(row);assert.equal(detector.snapshot().failure,null);
 for(const changed of [{status:500},{method:'POST'},{url:'http://127.0.0.1:3000/api/incidents'},{testId:'other test'},{mockedScenarioProof:undefined},{mockedScenarioProof:{fulfilled:true,detail:'other'}}]){
  const bad=createAcceptanceDetector();bad.observeResponse({...row,...changed});assert.ok(bad.snapshot().failure);
 }
 const real=createAcceptanceDetector();real.feedLog('backend','INFO: "GET /api/scenarios HTTP/1.1" 503 Service Unavailable\n');assert.ok(real.snapshot().failure);
});

import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {instrumentAcceptanceBrowser} from './acceptance-browser.mjs';

test('actual string-body mock503 proof never excuses a later same-route real503', async()=>{
 const server=createServer((request,response)=>{response.writeHead(request.url==='/api/scenarios'?503:200,{'content-type':'text/html'});response.end('Offline fixture');});
 await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
 const url='http://127.0.0.1:'+server.address().port;
 const requireWeb=createRequire(resolve('apps/web/package.json'));const {chromium}=requireWeb('@playwright/test');const browser=await chromium.launch();
 const detector=createAcceptanceDetector();
 const instrument=instrumentAcceptanceBrowser(browser,{testId:'the console recovers when its initial scenario request is temporarily unavailable',onResponse:r=>detector.observeResponse(r),onPageError:r=>detector.observePageError(r),onConsoleError:r=>detector.observeConsoleError(r)});
 try{
  const page=await browser.newPage();await page.goto(url);
  await page.route('**/api/scenarios',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Temporary synthetic test outage'})}));
  await page.evaluate(()=>fetch('/api/scenarios').then(r=>r.text()));assert.equal(detector.snapshot().failure,null);assert.equal(detector.snapshot().expectedScenarioResponses,1);
  await page.unroute('**/api/scenarios');await page.evaluate(()=>fetch('/api/scenarios').then(r=>r.text()));assert.equal(detector.snapshot().failure.kind,'browser-http-5xx');
 }finally{instrument.detach();await browser.close();await new Promise(ok=>server.close(ok));}
});
