import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

async function supervisor() {
  const module = await import('./browser-acceptance.mjs').catch(() => null);
  assert.ok(module?.runAcceptance, 'The normal CI browser command needs a teardown-aware acceptance entrypoint');
  return module.runAcceptance;
}

for (const [label, error, afterExit] of [
  ['clean shutdown', '', false],
  ['shutdown SSE error after passing UI', '{"logger":"creditops.sse","event":"sse_shutdown_incomplete"}', false],
  ['partial final rollback error', 'Exception during reset or similar', false],
  ['failure after suite exit while pipes drain', 'Application shutdown failed. Exiting.', true],
]) {
  test(label, async () => {
    const runAcceptance = await supervisor();
    const directory = mkdtempSync(join(tmpdir(), 'creditops-gate-'));
    const suite = join(directory, 'suite.mjs');
    if (afterExit) {
      const server = join(directory, 'server.mjs');
      writeFileSync(server, `import {createServer} from 'node:http'; const listener=createServer((_,res)=>res.end('Passing UI'));process.on('disconnect',()=>listener.close(()=>process.stderr.write(${JSON.stringify(error ? "[WebServer] " + error : "")},()=>{process.exitCode=0;})));listener.listen(0,'127.0.0.1',()=>process.send({port:listener.address().port}));`);
      writeFileSync(suite, `import {fork} from 'node:child_process';import {get} from 'node:http';const server=fork(${JSON.stringify(server)},[],{stdio:['ignore','inherit','inherit','ipc']});server.once('message',({port})=>get('http://127.0.0.1:'+port,res=>{res.resume();res.on('end',()=>{console.log('1 passed');process.exit(0);});}));`);
    } else {
      writeFileSync(suite, `console.log('1 passed'); process.stderr.write(${JSON.stringify(error ? "[WebServer] " + error : "")}); process.exitCode=0;`);
    }
    const result = await runAcceptance({ command: process.execPath, args: [suite], directory: join(directory, 'result'), forwardOutput: false });
    assert.equal(result.suiteExitCode, 0);
    assert.equal(result.exitCode, error ? 1 : 0);
    assert.equal(Boolean(result.detector.failure), Boolean(error));
    assert.ok(result.closedAt && result.finalLogDrainAt);
    const saved = JSON.parse(readFileSync(join(directory, 'result/result.json'), 'utf8'));
    assert.equal(saved.exitCode, result.exitCode);
    if (error) assert.ok(saved.detector.failure.kind);
  });
}


test('a retained server pipe cannot make final drain unbounded', async () => {
 const runAcceptance=await supervisor();
 const directory=mkdtempSync(join(tmpdir(),'creditops-held-drain-'));
 const server=join(directory,'server.mjs'),suite=join(directory,'suite.mjs'),release=join(directory,'release');
 writeFileSync(server, `import {createServer} from 'node:http';import {watch,existsSync,writeFileSync} from 'node:fs';const server=createServer((_,res)=>res.end('ok'));const watcher=watch(${JSON.stringify(directory)},()=>{if(existsSync(${JSON.stringify(release)}))stop();});function stop(){watcher.close();server.close(()=>writeFileSync(${JSON.stringify(join(directory,'joined'))},'closed'));}process.on('SIGTERM',stop);server.listen(0,'127.0.0.1',()=>process.send({port:server.address().port}));`);
 writeFileSync(suite, `import {fork} from 'node:child_process';import {get} from 'node:http';const server=fork(${JSON.stringify(server)},[],{stdio:['ignore','inherit','inherit','ipc']});server.once('message',({port})=>get('http://127.0.0.1:'+port,res=>{res.resume();res.once('end',()=>{console.log('1 passed');process.exit(0);});}));`);
 const pending=runAcceptance({command:process.execPath,args:[suite],directory:join(directory,'result'),forwardOutput:false,drainTimeoutMs:30});
 let timer;
 const deadline=new Promise(resolve=>{timer=setTimeout(()=>resolve(null),1000);});
 const early=await Promise.race([pending,deadline]);
 clearTimeout(timer);
 // Test-owned controlled release guarantees joining even on the pre-fix red run.
 writeFileSync(release,'release');
 const result=await pending;
 assert.ok(early,'The supervisor must return its bounded failure before test containment releases the server');
 assert.equal(result.suiteExitCode,0);
 assert.equal(result.exitCode,1);
 assert.equal(result.detector.failure.kind,'owned-output-drain-deadline');
 assert.equal(result.finalLogDrainCompleted,false);
 assert.ok(result.containment);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  test(`external ${signal} joins the owned runner and remains a failure`, async () => {
    const { spawn } = await import('node:child_process');
    const { once } = await import('node:events');
    const directory = mkdtempSync(join(tmpdir(), 'creditops-gate-signal-'));
    const suite = join(directory, 'suite.mjs'), wrapper = join(directory, 'wrapper.mjs');
    const resultDirectory = join(directory, 'result');
    writeFileSync(suite, `import {createServer} from 'node:http';const server=createServer((_,res)=>res.end('ok'));process.on('message',message=>{if(message?.type==='acceptance-stop')server.close(()=>{console.log('OWNED_SERVER_CLOSED');process.disconnect();});});server.listen(0,'127.0.0.1',()=>{console.log('SUITE_READY '+process.pid);});`);
    writeFileSync(wrapper, `import {runAcceptance} from ${JSON.stringify(new URL('./browser-acceptance.mjs', import.meta.url).href)};const result=await runAcceptance({command:process.execPath,args:[${JSON.stringify(suite)}],directory:${JSON.stringify(resultDirectory)}});process.exitCode=result.exitCode;`);
    const child = spawn(process.execPath, [wrapper], { stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '', suitePid;
    const ready = new Promise(resolveReady => child.stdout.on('data', chunk => {
      output += chunk;
      const match = /SUITE_READY (\d+)/.exec(output);
      if (match) { suitePid = Number(match[1]); resolveReady(); }
    }));
    let timer;
    try {
      await Promise.race([ready, new Promise((_,reject)=> { timer=setTimeout(()=>reject(new Error('Controlled suite did not acknowledge startup')),3000); })]);
      clearTimeout(timer);
      const closed = once(child, 'close');
      child.kill(signal);
      const [code, exitSignal] = await closed;
      assert.equal(code, 1, 'Interruption must retain a nonzero qualification outcome');
      assert.equal(exitSignal, null, 'Supervisor must finish the owned stop and persist its result');
      const result = JSON.parse(readFileSync(join(resultDirectory, 'result.json'), 'utf8'));
      assert.equal(result.detector.failure.kind, 'external-interruption');
      assert.equal(result.detector.failure.signal, signal);
      assert.equal(result.suiteExitCode, 0);
      assert.equal(result.finalLogDrainCompleted, true);
      assert.match(output, /OWNED_SERVER_CLOSED/);
      assert.throws(()=>process.kill(suitePid,0), { code:'ESRCH' }, 'The exact owned suite must be joined');
    } finally {
      clearTimeout(timer);
      if (suitePid) { try { process.kill(suitePid,'SIGTERM'); } catch(error) { if(error.code!=='ESRCH')throw error; } }
      if(child.exitCode===null && child.signalCode===null)child.kill('SIGTERM');
    }
  });
}

for (const event of ['', 'sse_shutdown_incomplete']) {
  test(`actual CI entrypoint: ${event || 'successful shutdown'}`, async () => {
    const { spawn } = await import('node:child_process');
    const { once } = await import('node:events');
    const { createRequire } = await import('node:module');
    const { fileURLToPath } = await import('node:url');
    const root = fileURLToPath(new URL('../', import.meta.url));
    const requireWeb = createRequire(join(root, 'apps/web/package.json'));
    const sdk = requireWeb.resolve('@playwright/test');
    const requireTest = createRequire(sdk);
    const cli = join(requireTest.resolve('playwright/package.json'), '..', 'cli.js');
    const directory = mkdtempSync(join(tmpdir(), 'creditops-ci-entrypoint-'));
    const server = join(directory, 'server.mjs'), port = join(directory, 'port');
    const config = join(directory, 'playwright.config.cjs');
    writeFileSync(server, `import {createServer} from 'node:http';import {writeFileSync} from 'node:fs';const server=createServer((_,res)=>res.end('<h1>Controlled UI</h1>'));process.on('SIGTERM',()=>server.close(()=>{${event ? `console.error(JSON.stringify({logger:'creditops.sse',event:${JSON.stringify(event)}}));` : ''}console.log('CONTROLLED_SERVER_CLOSED');}));server.listen(0,'127.0.0.1',()=>{writeFileSync(${JSON.stringify(port)},String(server.address().port));console.log('CONTROLLED_SERVER_READY');});`);
    writeFileSync(join(directory, 'ui.spec.cjs'), `const {test,expect}=require(${JSON.stringify(sdk)});const {readFileSync}=require('node:fs');test('controlled UI assertion succeeds',async({page})=>{await page.goto('http://127.0.0.1:'+readFileSync(${JSON.stringify(port)},'utf8'));await expect(page.getByRole('heading',{name:'Controlled UI'})).toBeVisible();});`);
    writeFileSync(config, `module.exports={testDir:${JSON.stringify(directory)},testMatch:'ui.spec.cjs',retries:0,use:{headless:true},webServer:{command:${JSON.stringify(JSON.stringify(process.execPath)+' '+JSON.stringify(server))},wait:{stdout:/CONTROLLED_SERVER_READY/},stdout:'pipe',stderr:'pipe',gracefulShutdown:{signal:'SIGTERM',timeout:5000}}};`);
    async function command(args) {
      const child=spawn(process.execPath,args,{cwd:join(root,'apps/web'),env:{...process.env,CREDITOPS_ENV_FILE:'',OPENAI_API_KEY:'',ANTHROPIC_API_KEY:'',ADMIN_API_KEY:''},stdio:['ignore','pipe','pipe']});
      let output='';child.stdout.on('data',chunk=>output+=chunk);child.stderr.on('data',chunk=>output+=chunk);
      const [code,signal]=await once(child,'close');return {code,signal,output};
    }
    // The old direct runner accepted exit zero despite this shutdown log.
    const old=await command([cli,'test','--config='+config,'--reporter=line']);
    assert.equal(old.code,0);assert.match(old.output,/1 passed/);
    const resultDirectory=join(directory,'result');
    const current=await command([join(root,'scripts/browser-acceptance.mjs'),'legacy','--config='+config,'--result-dir',resultDirectory]);
    assert.equal(current.code,event?1:0);assert.equal(current.signal,null);
    const result=JSON.parse(readFileSync(join(resultDirectory,'result.json'),'utf8'));
    const report=JSON.parse(readFileSync(join(resultDirectory,'playwright.json'),'utf8'));
    assert.equal(report.stats.expected,1,'The UI assertion passed before server teardown');
    assert.equal(result.finalLogDrainCompleted,true);
    assert.match(current.output,/CONTROLLED_SERVER_CLOSED/);
    if(event){assert.equal(result.detector.failure.event,event);assert.equal(result.exitCode,1);}
    else{assert.equal(result.detector.failure,null);assert.equal(result.exitCode,0);}
  });
}
