import {chromium} from 'playwright';
import {writeFile,mkdir} from 'node:fs/promises';
const output=new URL('./output/playwright/',import.meta.url);await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.ARCHIPELAGO_CHROMIUM||'C:/Users/limou/AppData/Local/ms-playwright/chromium-1237/chrome-win64/chrome.exe',args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist','--use-angle=d3d11','--disable-background-timer-throttling','--disable-renderer-backgrounding']});
const context=await browser.newContext({viewport:{width:1448,height:1086},deviceScaleFactor:1});const page=await context.newPage();const errors=[],warnings=[],responses=[];
page.on('console',m=>{if(m.type()==='error'){errors.push(m.text());console.log('ERROR',m.text());}if(m.type()==='warning'){warnings.push(m.text());console.log('WARNING',m.text());}});page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});page.on('response',r=>{if(r.url().includes('/assets/'))responses.push({url:r.url(),status:r.status(),encoding:r.headers()['content-encoding']||'none'});});
const timer=setInterval(()=>page.evaluate(()=>({label:document.querySelector('#loading-label')?.textContent,ready:window.__archipelago?.diagnostic.ready,frames:window.__archipelago?.diagnostic.frames})).then(s=>console.log('PROGRESS',JSON.stringify(s))).catch(e=>console.log('PROGRESS ERROR',String(e))),5000);
try{
  await page.goto('http://127.0.0.1:4173/',{waitUntil:'networkidle',timeout:120000});
  await page.waitForFunction(()=>window.__archipelago?.diagnostic.ready||document.querySelector('#reload')?.hidden===false,null,{timeout:180000});
  const failure=await page.locator('#reload').isVisible();if(failure){const message=await page.locator('#loading-label').innerText();throw new Error(message);}
  await page.waitForTimeout(2500);
  const snapshot=await page.evaluate(()=>window.__archipelago.snapshot());await writeFile(new URL('initial-runtime.json',output),JSON.stringify({browser:browser.version(),snapshot,errors,warnings,responses},null,2));console.log(JSON.stringify({browser:browser.version(),backend:snapshot.diagnostic.backend,adapter:snapshot.diagnostic.adapter,triangles:snapshot.diagnostic.triangles,frames:snapshot.diagnostic.frames,errors,warnings},null,2));
  await page.screenshot({path:new URL('overview.png',output).pathname.replace(/^\/(.:)/,'$1'),timeout:30000});
}catch(e){console.error(e);await writeFile(new URL('initial-runtime-failure.json',output),JSON.stringify({error:String(e),errors,warnings,responses},null,2));try{await page.screenshot({path:new URL('failure.png',output).pathname.replace(/^\/(.:)/,'$1'),timeout:10000});}catch{}process.exitCode=1;}finally{clearInterval(timer);await browser.close();}
