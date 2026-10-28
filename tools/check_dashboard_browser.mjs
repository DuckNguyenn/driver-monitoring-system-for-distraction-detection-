import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';

const server=process.argv[2];
const token=process.env.DRIVER_MONITOR_TOKEN;
if(!server||!token)throw new Error('Server and private pairing environment required');
const browser=await chromium.launch({headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(server);
  await page.getByLabel('Địa chỉ máy chủ').fill(server);
  await page.getByLabel('Mã kết nối').fill(token);
  await page.getByRole('button',{name:'Kết nối máy chủ'}).click();
  await page.getByText('Phát lại video',{exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.preview img')?.naturalWidth>0);
  await page.evaluate(()=>{
    window.dashboardLatencies=[];
    window.dashboardImageLoads=[];
    document.querySelector('.preview').addEventListener('load',event=>{
      if(event.target.tagName==='IMG')window.dashboardImageLoads.push(performance.now());
    },true);
    const root=document.querySelector('.state-strip');
    let sequence='';
    new MutationObserver(()=>{
      if(root.dataset.sequence===sequence||root.dataset.fresh!=='true')return;
      sequence=root.dataset.sequence;
      const age=Date.now()-Date.parse(root.dataset.sourceUtc);
      if(Number.isFinite(age)&&age>=0)window.dashboardLatencies.push(age);
    }).observe(root,{attributes:true,attributeFilter:['data-sequence','data-source-utc','data-fresh']});
  });
  await page.waitForTimeout(4000);
  const renderLatencies=await page.evaluate(()=>window.dashboardLatencies);
  const imageLoads=await page.evaluate(()=>window.dashboardImageLoads);
  const previewFps=imageLoads.length>1?(imageLoads.length-1)*1000/(imageLoads.at(-1)-imageLoads[0]):null;
  const image=await page.locator('.preview img').evaluate(el=>({width:el.naturalWidth,height:el.naturalHeight}));
  const chartRows=await page.locator('.signal-charts .probability-panel').count();
  if(chartRows!==3)throw new Error('Expected three aligned probability charts');
  await page.screenshot({path:'.cache/dashboard_implementation/web-live-private.png',fullPage:true});
  await page.getByRole('button',{name:'Lịch sử phiên',exact:true}).click();
  await page.getByRole('button',{name:'Xem phiên'}).first().click();
  await page.getByText('60 giây cuối phiên').waitFor();
  const downloadPending=page.waitForEvent('download');
  await page.getByRole('button',{name:'Xuất CSV'}).click();
  const download=await downloadPending;
  const csv=await fs.readFile(await download.path(),'utf8');
  if(!csv.includes('source_timestamp')||!csv.includes('UNKNOWN'))throw new Error('Export lacks replay records');
  if(errors.length)throw new Error(`Browser error: ${errors[0]}`);
  renderLatencies.sort((a,b)=>a-b);
  console.log(JSON.stringify({passed:true,preview:image,render_samples:renderLatencies.length,
    preview_image_loads:imageLoads.length,preview_render_fps:previewFps,probability_chart_rows:chartRows,
    render_p95_ms:renderLatencies[Math.max(0,Math.ceil(renderLatencies.length*.95)-1)]??null,
    history_opened:true,csv_downloaded:true,page_errors:errors,physical_iphone_tested:false,scope:'one real Chromium client with real replay API on same PC'}));
}finally{await browser.close();}
