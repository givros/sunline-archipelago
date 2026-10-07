import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({headless:true,executablePath:process.env.ARCHIPELAGO_CHROMIUM||'C:/Users/limou/AppData/Local/ms-playwright/chromium-1237/chrome-win64/chrome.exe',args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist','--use-angle=d3d11']});
const results=[];
try{
  for(const scenario of['missing_webgpu','adapter_unavailable','scene_unavailable']){
    const context=await browser.newContext({viewport:{width:1448,height:1086}});
    if(scenario==='missing_webgpu')await context.addInitScript(()=>Object.defineProperty(Navigator.prototype,'gpu',{get:()=>undefined}));
    if(scenario==='adapter_unavailable')await context.addInitScript(()=>Object.defineProperty(Navigator.prototype,'gpu',{get:()=>({requestAdapter:async()=>null})}));
    const page=await context.newPage();let navigations=0;page.on('framenavigated',frame=>{if(frame===page.mainFrame())navigations++;});if(scenario==='scene_unavailable')await page.route('**/assets/scene.json',route=>route.fulfill({status:503,body:'Controlled local test fixture'}));
    await page.goto('http://127.0.0.1:4173/',{waitUntil:'networkidle'});await page.locator('#reload').waitFor({state:'visible',timeout:30000});
    const message=await page.locator('#loading-label').innerText();const busyLoop=await page.evaluate(()=>Boolean(window.__archipelago?.diagnostic.ready));
    await page.locator('#reload').click();await page.waitForLoadState('networkidle');await page.locator('#reload').waitFor({state:'visible',timeout:30000});
    results.push({scenario,status:message.length>20&&!busyLoop&&navigations>=2?'passed':'failed',message,reloadAvailable:true,reloadActionVerified:navigations>=2,sceneReady:busyLoop});await context.close();
  }
}finally{await browser.close();await writeFile(new URL('./output/playwright/failure-paths.json',import.meta.url),JSON.stringify({timestamp:new Date().toISOString(),method:'Isolated headless development fixtures; no user browser state changed',results},null,2));console.log(JSON.stringify(results,null,2));}
