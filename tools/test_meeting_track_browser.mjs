import assert from 'node:assert/strict';
import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {transform} from 'esbuild';
import {chromium} from 'playwright';
const input=await readFile(new URL('../packages/ui/src/meetingTrackPlayback.ts',import.meta.url),'utf8');
const code=(await transform(input,{loader:'ts',format:'esm',target:'es2022'})).code;
function wav(samples,frequency){const b=Buffer.alloc(44+samples*2);b.write('RIFF',0);b.writeUInt32LE(36+samples*2,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(16000,24);b.writeUInt32LE(32000,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(samples*2,40);for(let i=0;i<samples;i++)b.writeInt16LE(Math.round(1000*Math.sin(2*Math.PI*frequency*i/16000)),44+i*2);return b;}
const files={'/mic-1.wav':wav(16000,220),'/mic-2.wav':wav(16000,230),'/sys-1.wav':wav(8000,330),'/sys-2.wav':wav(24000,340)};
const server=http.createServer((req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname;if(name==='/controller.js'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end(code);return;}
 if(name==='/'){res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><html><body></body></html>');return;}
 const b=files[name];if(!b){res.writeHead(404);res.end();return;}
 const range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);const start=range?Number(range[1]):0,end=range&&range[2]?Math.min(Number(range[2]),b.length-1):b.length-1;
 if(start>end||start>=b.length){res.writeHead(416,{'Content-Range':`bytes */${b.length}`});res.end();return;}
 res.writeHead(range?206:200,{'Content-Type':'audio/wav','Content-Length':end-start+1,'Accept-Ranges':'bytes',...(range?{'Content-Range':`bytes ${start}-${end}/${b.length}`}:{})});res.end(b.subarray(start,end+1));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const port=server.address().port;
let browser;
try {
 browser=await chromium.launch({headless:true,executablePath:process.env.COMPANION_TEST_BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--mute-audio','--autoplay-policy=no-user-gesture-required']});
 const page=await browser.newPage();await page.goto(`http://127.0.0.1:${port}/`);
 await page.evaluate(async()=>{const {MeetingTrackPlayback}=await import('/controller.js');const mic=document.createElement('audio'),sys=document.createElement('audio');document.body.append(mic,sys);window.tracks=[mic,sys];window.states=[];window.player=new MeetingTrackPlayback({microphone:[{url:'/mic-1.wav',firstSample:0,samples:16000},{url:'/mic-2.wav',firstSample:16000,samples:16000}],system:[{url:'/sys-1.wav',firstSample:0,samples:8000},{url:'/sys-2.wav',firstSample:8000,samples:24000}]},mic,sys,s=>window.states.push(s));await window.player.play();});
 await page.waitForFunction(()=>window.states.some(s=>s.position>1.15&&s.playing),null,{timeout:10000});
 const during=await page.evaluate(()=>({src:window.tracks.map(x=>new URL(x.src).pathname),position:window.player.getPosition(),playing:window.states.at(-1).playing}));
 assert.deepEqual(during.src,['/mic-2.wav','/sys-2.wav']);assert.equal(during.playing,true);
 await page.evaluate(async()=>{window.player.pause();await window.player.seek(1.5);});
 const seek=await page.evaluate(()=>({mic:window.tracks[0].currentTime,system:window.tracks[1].currentTime,position:window.player.getPosition()}));
 assert.ok(Math.abs(seek.mic-.5)<.03);assert.ok(Math.abs(seek.system-1)<.03);assert.ok(Math.abs(seek.position-1.5)<.03);
 await page.evaluate(()=>window.player.dispose());
 console.log(JSON.stringify({state:'PASS_HEADLESS_EDGE_SYNTHETIC_WAV',scope:'real browser audio decoding, independently split local synthetic tracks, cross-boundary playback and paused seek; muted, no device or real meeting',during,seek}));
} finally {if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
