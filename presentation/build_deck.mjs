import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';
const root = path.resolve(import.meta.dirname, '..');
const runtime = path.join(process.env.HOME, '.cache/codex-runtimes/codex-primary-runtime/dependencies');
process.env.RUNTIME_NODE_MODULES = path.join(runtime, 'node/node_modules');
const skill = path.join(process.env.HOME, '.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations');
const build = path.join(root, 'artifacts/presentation-build');
await fs.mkdir(build, {recursive:true});
const ppt = Presentation.create({slideSize:{width:1280,height:720}});
const C = {ink:'#163C36', teal:'#256456', cream:'#F6F4ED', muted:'#52645E', gold:'#D8B779', white:'#FFFFFF', sage:'#E3E9DF', soft:'#C9D6CF', warn:'#9A4A2E', good:'#256456'};

// Four presenters, one part each, mapped to the project description's structure.
const PARTS = [
 {n:1, who:'YUEN Yiu Yeung', time:'0:00–1:15', title:'The chatbot and its knowledge base', spec:'Basic features · knowledge base'},
 {n:2, who:'SO Ngai Chun', time:'1:15–2:30', title:'Interface and 3D interviewer', spec:'User-friendly interface · 3D avatar'},
 {n:3, who:'SHIH Richard', time:'2:30–5:00', title:'Voice and live demonstration', spec:'Voice recognition and synthesis · live demo'},
 {n:4, who:'WONG Kin Chung', time:'5:00–7:00', title:'Fine-tuned LLM and evaluation', spec:'Fine-tuned LLM · evaluation results · limitations'},
];

function text(slide, content, x,y,w,h,size=30,color=C.ink,bold=false){
 const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 s.text=content;s.text.style={typeface:'Arial',fontSize:size,color,bold,verticalAlignment:'middle'};return s;
}
function rect(s,x,y,w,h,fill){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});}
function base(title, note, dark=false){const s=ppt.slides.add();s.background.fill=dark?C.ink:C.cream;text(s,title,72,55,1136,110,48,dark?C.white:C.ink,true);s.speakerNotes.text=note;return s;}
// Content slide with a small "Part N · presenter" tag in the top-right corner.
function partSlide(part, title, note){const s=base(title, note);text(s,`Part ${part.n}  ·  ${part.who}`,860,22,348,30,15,C.muted,true);return s;}
function divider(part, note){
 const s=ppt.slides.add();s.background.fill=C.ink;s.speakerNotes.text=note;
 text(s,`Part ${part.n}`,72,180,600,70,40,C.gold,true);
 text(s,part.title,72,262,1136,100,52,C.white,true);
 text(s,part.spec,76,380,1100,44,25,C.soft);
 rect(s,72,470,90,4,C.gold);
 text(s,`${part.who}  ·  ${part.time}`,72,500,1100,44,26,C.white);
 return s;
}
function card(s,x,y,w,h,head,body,filled=false){
 rect(s,x,y,w,h,filled?C.teal:C.sage);
 text(s,head,x+20,y+12,w-40,56,20,filled?C.white:C.ink,true);
 text(s,body,x+20,y+74,w-40,h-88,17,filled?C.white:C.muted);
}
function columns(s,left,right,y=185){
 [left,right].forEach(([head,lines],i)=>{const x=72+i*580;text(s,head,x,y,540,46,26,C.teal,true);text(s,lines,x,y+52,540,140,21,C.ink);});
}
function challenges(s,rows,y0=500){
 text(s,'Challenge → fix',72,y0-44,600,36,19,C.warn,true);
 rows.forEach(([p,f],i)=>{const y=y0+i*58;rect(s,72,y,1136,50,i%2?C.cream:C.sage);text(s,p,92,y+6,540,38,19,C.ink,true);text(s,f,650,y+6,540,38,19,C.teal);});
}
const [P1,P2,P3,P4]=PARTS;

// Title
let s=base('Practice the interview.\nShow your evidence.', `${P1.who} opens. 0:00–0:15. Hong Kong technology graduates usually practise generic questions that have nothing to do with the job they apply for. VoxPrep HK turns a real job description into a spoken mock interview, in English or Cantonese, with feedback tied to the evidence in your own answers. Everything runs locally on this laptop, including a language model we fine-tuned ourselves.`,true);
text(s,'VoxPrep HK',72,250,1050,100,82,C.gold,true);
text(s,'A bilingual AI interview coach for Hong Kong technology graduates',76,365,1100,60,29,C.white);
text(s,'SO Ngai Chun  ·  SHIH Richard  ·  WONG Kin Chung  ·  YUEN Yiu Yeung',76,560,1130,40,22,C.soft);
text(s,'COMP4431 Artificial Intelligence  ·  Group Project',76,606,1130,38,22,C.soft);

// Agenda
s=base('Four parts, four presenters', `${P1.who}. 0:15–0:25. We follow the project description: first the basic features and the knowledge base, then the additional features one by one, a live demo with a spoken conversation, and finally our fine-tuned model and its evaluation.`);
PARTS.forEach((p,i)=>{const y=185+i*118;rect(s,72,y,1136,100,i%2?C.cream:C.sage);text(s,`Part ${p.n}`,96,y+12,160,76,30,C.teal,true);text(s,p.title,270,y+10,620,44,27,C.ink,true);text(s,p.spec,270,y+54,620,34,19,C.muted);text(s,p.who,900,y+10,290,44,22,C.ink,true);text(s,p.time,900,y+54,290,34,19,C.muted);});

// Part 1
divider(P1, `${P1.who}. Part 1 covers the basic features required by the project description and the knowledge base behind every answer.`);
s=partSlide(P1,'Basic features: a coach that stays in its domain', `${P1.who}. 0:25–0:50. The project requires a chatbot that communicates within its domain and gives relevant responses in a chosen language. Our domain is job-interview practice for technology roles. The coach only acts as an interviewer for the uploaded role and refuses injected or off-topic instructions. It asks role-specific questions, follows up when an answer is weak, and explains its feedback with evidence. Each session runs in English or Cantonese, and the answer language can switch mid-interview.`);
text(s,'Project requirement',72,180,420,36,19,C.muted,true);text(s,'How VoxPrep HK meets it',540,180,660,36,19,C.muted,true);
[
 ['Communicate within the domain','Acts only as an interview coach for the uploaded role; injected or off-topic instructions are refused'],
 ['Handle typical user queries','Role-specific questions, follow-ups on weak answers, feedback explained with evidence'],
 ['Relevant responses in a chosen language','English or Cantonese per session; the answer language can switch mid-interview'],
].forEach(([r,o],i)=>{const y=224+i*128;rect(s,72,y,1136,112,i%2?C.cream:C.sage);text(s,r,92,y+14,420,84,24,C.ink,true);text(s,o,540,y+14,650,84,22,C.teal);});

s=partSlide(P1,'Grounded in a knowledge base', `${P1.who}. 0:50–1:15. The uploaded job description, plus our STAR and competency guides, becomes the knowledge base. Passages are stored with embeddings in a vector database: pgvector, or SQLite locally. Retrieval fuses keyword, full-text and vector results with reciprocal rank fusion, and a Qwen3 reranker keeps the top four passages. Every model reply must match a strict JSON schema whose competency and citation fields are locked to those passages, so each question and piece of feedback can show its source. If a reply is invalid or in the wrong language, we retry once and otherwise fall back safely. Now ${P2.who} will show the interface and the avatar.`);
const arch=[['Browser','React + Three.js\nmicrophone, captions\nand 3D avatar'],['FastAPI','HTTP + WebSocket\nsession state\nreport builder'],['Knowledge base','job description +\nSTAR guides, embedded\nin a vector store'],['Retrieval + LLM','RRF fusion, reranker\nkeeps top 4; Qwen3-4B\n+ LoRA in llama.cpp']];
arch.forEach(([h,b],i)=>{const x=72+i*290;rect(s,x,190,260,240,i===3?C.teal:C.sage);text(s,h,x+20,210,225,52,24,i===3?C.white:C.ink,true);text(s,b,x+20,276,225,130,20,i===3?C.white:C.muted);});
text(s,'Strict JSON schema: competencies and citation IDs are locked to retrieved passages.',72,470,1136,50,25,C.ink,true);
text(s,'Invalid output or wrong language  →  retry once  →  safe fallback, never a silent error.',72,524,1136,50,24,C.muted);

// Part 2
divider(P2, `${P2.who}. Part 2: our additional features, starting with the interface and the 3D interviewer.`);
s=partSlide(P2,'Additional features', `${P2.who}. 1:15–1:45. The project description suggests four additional features: voice recognition and synthesis, a 2D or 3D avatar, a fine-tuned LLM, and a user-friendly interface. We implemented all four, shown in the top row with the part that explains each. Beyond that list we added hybrid retrieval with a reranker and citations, follow-up questions that target the missing STAR element, a debrief report with PDF export, and safety and privacy guardrails.`);
text(s,'From the project description',72,172,700,36,20,C.muted,true);
[
 ['Voice recognition + synthesis','Whisper speech-to-text in English and Cantonese; spoken questions  ·  Part 3'],
 ['3D avatar','Original Three.js interviewer with lip-sync and listening, thinking states  ·  Part 2'],
 ['Fine-tuned LLM','Qwen3-4B with our own QLoRA adapter, served locally  ·  Part 4'],
 ['User-friendly interface','Three-step flow, editable captions, type or speak  ·  Part 2'],
].forEach(([h,b],i)=>card(s,72+i*290,214,266,200,h,b,true));
text(s,'Beyond the list',72,436,700,36,20,C.muted,true);
[
 ['Hybrid RAG','Keyword, full-text and vector search, reranked; cited sources'],
 ['STAR follow-ups','Next question targets the element your answer missed'],
 ['Debrief + PDF','STAR evidence, competencies, pace and filler words'],
 ['Safety + privacy','Refuses injected instructions; transcripts stay local'],
].forEach(([h,b],i)=>card(s,72+i*290,478,266,170,h,b));

s=partSlide(P2,'Interface and 3D interviewer', `${P2.who}. 1:45–2:30. The interface is a three-step flow: set up the role, practise the interview, read the debrief. Captions are always editable, so you can type or speak. The interviewer is an original procedural 3D model built in Three.js with no external assets. It nods while listening, glances away while thinking and moves its mouth while speaking, driven by Azure visemes or the playback level. The main challenge: WebGL can fail on lab machines, so an error boundary swaps in a 2D portrait and the interview carries on; reduced-motion users get the portrait too. Now ${P3.who} will cover voice and run the live demo.`);
columns(s,['Interface','Three steps: set up → interview → debrief\nCaptions always editable; type or speak\nReport saved as a PDF\nKeyboard navigation and reduced-motion support'],['3D avatar','Original procedural model, built in Three.js\nListening nods, thinking glance, blinking\nLip-sync from Azure visemes or audio level\nNo external models or assets'],180);
challenges(s,[['WebGL can fail on lab machines','Error boundary swaps in a 2D portrait'],['Motion can distract some users','Reduced-motion setting shows the static portrait']],512);

// Part 3
divider(P3, `${P3.who}. Part 3: voice recognition and synthesis, then the live demo with a spoken conversation.`);
s=partSlide(P3,'Voice in, voice out', `${P3.who}. 2:30–3:00. Speech-to-text runs locally with whisper.cpp large-v3-turbo, in English or Cantonese. Azure streaming recognition is optional and used only with explicit consent. For speech output we use the browser's neural voices and pick Google Cantonese (Hong Kong) for Cantonese sessions. Three problems we fixed: Whisper returned Cantonese in Simplified characters, so we convert to Hong Kong Traditional with OpenCC; the voice sounded robotic because Chrome names its voices with a non-breaking space, so our picker never matched the good voice until we normalised the names; and the microphone test only checked permission, so now it records three seconds and plays them back.`);
columns(s,['Speech-to-text','whisper.cpp large-v3-turbo, fully local\nEnglish or Cantonese (yue)\nOptional Azure streaming, only with consent\nTranscript stays editable'],['Text-to-speech','Browser neural voices\nGoogle Cantonese (Hong Kong) for zh-HK\nAvatar mouth follows the speech\nMic test records 3 s and plays it back'],180);
challenges(s,[['Cantonese transcripts came back in Simplified','OpenCC s2hk converts to HK Traditional'],['Robotic voice: voice names hid a no-break space','Normalised names; picks the neural voice'],['Mic test only checked permission','Now records 3 s and plays it back']],488);

s=partSlide(P3,'Live demo', `${P3.who}. 3:00–5:00. Switch to the app. One: import the demo job description and choose English with three questions. Two: give a deliberately incomplete answer: I worked on a team project and helped improve our API. Three: the follow-up asks for the missing action or result; answer it by voice, switching the answer language to Cantonese, and show that the transcript is editable. Four: finish and open the debrief, show one STAR evidence line and its cited source, then save the PDF. If speech fails, type the prepared answer. If the app fails, play the backup recording. Then hand over to ${P4.who}.`);
const demo=[['Import a technology role','Paste or upload a job description · English or Cantonese'],['Give an incomplete answer','“I worked on a team project and helped improve our API.”'],['Answer the follow-up by voice, in Cantonese','The coach asks for the missing Action or Result'],['Open the debrief','STAR evidence, cited sources, retry exercise, PDF export']];
demo.forEach(([h,b],i)=>{const y=180+i*120;text(s,String(i+1),75,y,100,96,64,C.teal,true);text(s,h,200,y+4,1000,52,33,C.ink,true);text(s,b,200,y+56,1000,40,24,C.muted);});

// Part 4
divider(P4, `${P4.who}. Part 4: the fine-tuned model, how we evaluated it, and the limits of what we can claim.`);
s=partSlide(P4,'Fine-tuning our own adapter', `${P4.who}. 5:00–5:35. We generated 1,000 training examples using exactly the prompts the app sends at runtime. Every row was reviewed by hand over two days, and a second reviewer independently checked at least 15 percent of each language and task group; 971 were approved and 29 rejected. We split 790 for training, 62 for validation and 119 for testing, grouped by role, source and template so nothing leaks between splits. We trained a rank-32 QLoRA adapter on a 4-bit base on a free Kaggle T4, one epoch in 87 minutes. Validation loss fell from 0.43 to 0.056. The 132 megabyte adapter is applied by llama.cpp at run time, and it is what the demo just used.`);
const steps=[['Generate','1,000 drafts from\nthe exact runtime\nprompts'],['Review','971 approved\n2-day human review\n15% double-checked'],['Train','QLoRA r = 32, NF4\n1 epoch on a T4\n87 minutes'],['Serve','132 MB LoRA GGUF\nllama.cpp --lora\nused in the demo']];
steps.forEach(([h,b],i)=>{const x=72+i*290;rect(s,x,200,260,230,i%2?C.teal:C.sage);text(s,h,x+20,222,220,52,32,i%2?C.white:C.ink,true);text(s,b,x+20,290,225,120,21,i%2?C.white:C.muted);});
text(s,'Split 790 / 62 / 119, grouped by role, source and template: no leakage.',72,474,1136,50,25,C.ink,true);
text(s,'Validation loss 0.43 → 0.056 (best checkpoint kept).',72,528,1136,50,25,C.muted);

s=partSlide(P4,'Evaluation: what fine-tuning changed', `${P4.who}. 5:35–6:15. We ran all 119 held-out prompts through three configurations with identical prompts and retrieved context. Schema validity was already 100 percent for the base model, so fine-tuning did not change it. The real gain is language adherence: from 92.4 to 100 percent. Comparing the same prompt before and after, 9 were fixed and none got worse, which is significant with an exact McNemar test, p about 0.004. The typical failure was an English session whose coaching drifted into Chinese. Latency rises by about 0.3 seconds at p95. The limit: 109 of the 119 test prompts are English reports and only 4 are safety cases, so we make no claim about question quality.`);
text(s,'119 held-out prompts, same prompts and context',72,180,780,46,26,C.teal,true);
const cols=[72,330,500,680];
[['configuration',0],['schema',1],['language',2],['p95 first token',3]].forEach(([h,i])=>text(s,h,cols[i],238,240,36,20,C.muted,true));
const measured=[['base + RAG','100%','92.4%','1.77 s'],['adapter + RAG','100%','100%','2.04 s'],['adapter, no RAG','100%','100%','2.32 s']];
measured.forEach(([a,b,c,e],i)=>{const y=284+i*54;text(s,a,cols[0],y,250,42,23,C.ink,true);text(s,b,cols[1],y,150,42,23,C.ink);text(s,c,cols[2],y,160,42,23,i===0?C.warn:C.good,true);text(s,e,cols[3],y,200,42,23,C.ink);});
rect(s,72,454,800,50,C.sage);text(s,'Paired: 9 fixed  ·  0 regressed  ·  110 unchanged',92,461,770,36,22,C.ink,true);
text(s,'What it shows',920,180,300,46,26,C.teal,true);
text(s,'Language 92.4% → 100%\nExact McNemar p ≈ 0.004\nSchema already 100%\np95 latency +0.27 s',920,232,300,130,21,C.ink);
text(s,'What it does not show',72,528,900,40,22,C.warn,true);
text(s,'109 of 119 test prompts are English reports and only 4 are safety cases, so there is no claim about question quality.',72,568,1136,56,19,C.muted);
rect(s,72,640,1136,44,C.teal);text(s,'All numbers come from automated checks on held-out data. No human rating is claimed.',92,645,1100,34,21,C.white,true);

s=partSlide(P4,'Model challenges we solved', `${P4.who}. 6:15–6:40. Our first dataset did not match the prompts the app really sends, so we rebuilt the generator and the 1,000 examples. On the T4, PyTorch reports bf16 support through slow emulation: 310 seconds per step until we forced fp16, which made training 3.7 times faster. The default Kaggle image ships a transformers version that breaks bitsandbytes, so we pinned our training requirements. The llama.cpp converter pins protobuf below version 5, which broke importing transformers during export; we restored protobuf and kept transformers off TensorFlow. The base model drifted into Chinese in English sessions; we added a per-field language validator with a retry, and the adapter fixes it at the source.`);
const issues=[
 ['First dataset did not match the app','Rebuilt from the exact runtime prompts'],
 ['T4 emulates bf16: 310 s per step','Forced fp16: 84–105 s per step, 3.7× faster'],
 ['Kaggle transformers broke bitsandbytes','Pinned the training requirements'],
 ['Converter pinned protobuf<5: export broke','Restored protobuf; export runs with USE_TF=0'],
 ['Base model drifted into Chinese','Language validator + retry; adapter fixes it'],
];
text(s,'Problem',72,172,520,34,19,C.muted,true);text(s,'Fix',640,172,560,34,19,C.muted,true);
issues.forEach(([p,f],i)=>{const y=214+i*82;rect(s,72,y,1136,68,i%2?C.cream:C.sage);text(s,p,92,y+12,530,44,22,C.ink,true);text(s,f,640,y+12,550,44,22,C.teal);});

s=base('Limits we are honest about', `${P4.who}. 6:40–7:00. Our test set is dominated by English reports, we did not run a user study or blind rating, we have not measured Cantonese speech recognition accuracy, and the adapter adds about 0.3 seconds of latency. By design, transcripts stay on the laptop, every claim shows its source, captions are editable, and the coach never scores hiring chances, accent or appearance. Thank you; we are happy to take questions.`,true);
text(s,`Part 4  ·  ${P4.who}`,860,22,348,30,15,C.soft,true);
text(s,'Limitations',72,200,680,50,30,C.gold,true);
text(s,'Test set skews to English reports\nNo user study or blind rating\nCantonese ASR accuracy not measured\nAdapter adds ~0.3 s latency (p95)',72,262,680,200,30,C.white,true);
text(s,'By design',800,200,400,50,30,C.gold,true);
text(s,'Local transcripts\nVisible sources\nEditable captions\nNo hiring, accent or\nappearance scores',800,262,400,200,26,C.soft);
text(s,'Thank you  ·  Questions welcome',72,600,1136,56,30,C.gold,true);

// Q&A appendix
s=base('Q&A: who answers what', 'Appendix, outside the seven-minute talk. Each presenter takes questions on their own part.');
[
 [P1,'Why retrieval?','Feedback quotes the actual job description, and every source can be inspected.'],
 [P2,'What if WebGL fails?','The 2D portrait takes over and the interview continues.'],
 [P3,'How accurate is Cantonese speech?','Not measured yet; the transcript is always editable before sending.'],
 [P4,'Why fine-tune if schema was 100%?','Prompting alone drifted language 7.6% of the time; the adapter fixed all 9 cases.'],
].forEach(([p,q,a],i)=>{const y=180+i*118;rect(s,72,y,1136,104,i%2?C.cream:C.sage);text(s,`Part ${p.n}\n${p.who}`,92,y+10,250,84,19,C.teal,true);text(s,q,360,y+10,330,84,22,C.ink,true);text(s,a,710,y+10,480,84,20,C.muted);});

for (const [i,slide] of ppt.slides.items.entries()) {
 const png=await ppt.export({slide,format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await(await PresentationFile.exportPptx(ppt)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const final=path.join(root,process.env.DECK_OUTPUT || 'presentation/VoxPrep-HK.pptx');
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:final,pythonExecutable:path.join(runtime,'python/bin/python3'),integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],explicitTotalSlideCount:ppt.slides.items.length,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,receiptPath:path.join(build,path.basename(final)+'.validation.json')});
console.log(final);
