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
const C = {ink:'#163C36', teal:'#256456', cream:'#F6F4ED', muted:'#52645E', gold:'#D8B779', white:'#FFFFFF'};
function text(slide, content, x,y,w,h,size=30,color=C.ink,bold=false){
 const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 s.text=content;s.text.style={typeface:'Arial',fontSize:size,color,bold,verticalAlignment:'middle'};return s;
}
function rect(s,x,y,w,h,fill){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});}
function base(title, note, dark=false){const s=ppt.slides.add();s.background.fill=dark?C.ink:C.cream;text(s,title,72,55,1136,110,48,dark?C.white:C.ink,true);s.speakerNotes.text=note;return s;}
let s=base('Practice the interview.\nShow your evidence.', '0:00–0:30. Hong Kong graduates often practise generic questions that do not match the job. VoxPrep HK takes a job description and supports English or Cantonese practice with explicit evidence. The original plan targets a genuinely fine-tuned model. The delivered software also has a base-model path and a labelled demo provider. Never describe the base model or demo templates as a trained adapter. Source: COMP4431_GroupProject2027.pdf, supplied implementation plan.',true);
text(s,'VoxPrep HK',72,260,1050,100,82,C.gold,true);
text(s,'Bilingual AI interview practice for technology graduates',76,380,1040,90,31,C.white);
text(s,'COMP4431  ·  Implementation and rehearsal deck',76,606,1050,38,22,'#C9D6CF');

s=base('One local application, four contributions', '0:30–1:00. The React interface collects a job description and answers. FastAPI coordinates local retrieval and model inference. Native llama.cpp and whisper.cpp keep Apple Metal acceleration. Azure voice is optional and consented. Explain which provider is running before demonstrating. Sources: docs/ARCHITECTURE.md; https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md');
const parts=[['Interface','React + editable captions'],['Voice + avatar','Azure / Whisper + Three.js'],['Grounded coaching','Retrieved passages + schemas'],['Model workflow','Reviewed data + QLoRA']];
parts.forEach(([h,b],i)=>{let y=190+i*102;rect(s,72,y,8,72,C.teal);text(s,h,104,y,380,42,31,C.ink,true);text(s,b,500,y,690,72,29,C.muted);});

s=base('Live demo: start with the role', '1:00–1:30 setup, then 1:30–3:40 live interview. Switch to the app. Import data/demo-job.txt, choose English and three questions for the timed demonstration. Describe the role and consent. Answer: “I worked on a team project and helped improve our API.” Show the follow-up asking for a specific personal action or result. Edit the transcript if voice recognition is wrong. Demonstrate pause/repeat only if the main path is on time. Switch one answer to Cantonese if available. Source: presentation/DEMO_SCRIPT.md.');
text(s,'1',75,205,110,100,72,C.teal,true);text(s,'Import a technology role',210,207,950,65,37,C.ink,true);text(s,'Python APIs, testing and teamwork',210,277,950,52,29,C.muted);
text(s,'2',75,365,110,100,72,C.teal,true);text(s,'Give an incomplete answer',210,367,950,65,37,C.ink,true);text(s,'“I helped improve our API.”',210,437,950,52,29,C.muted);
text(s,'3',75,525,110,100,72,C.teal,true);text(s,'Respond to the follow-up',210,527,950,65,37,C.ink,true);text(s,'Add your action and an observable result',210,597,950,52,29,C.muted);

s=base('Make the next answer more specific', '3:40–4:40. Show the debrief in the application. Read one exact transcript excerpt, identify a missing STAR element and open the source passage. Show one prioritized improvement and retry exercise. Speech counts describe observable delivery only and are not accent or personality scores. The current fallback report uses transparent heuristics and should not be described as a validated psychological assessment. Sources: backend report implementation; docs/MODEL_CARD.md.');
['Situation','Task','Action','Result'].forEach((v,i)=>{let x=72+i*290;rect(s,x,210,260,90,i===2?C.teal:'#E3E9DF');text(s,v,x+20,228,220,50,30,i===2?C.white:C.ink,true);});
text(s,'“I measured query time, added an index,\nand reduced latency by 30 percent.”',90,360,1100,130,40,C.ink,true);
text(s,'Your words support the feedback. Retrieved sources explain the role.',90,555,1100,80,29,C.muted);

s=base('Fine-tuning has a verifiable evidence trail', '4:40–5:35. Explain 4-bit NF4 base weights and a rank-32 adapter. The training script uses assistant-only loss, grouped splits, effective batch 32 and validation checkpoint selection. The draft curriculum must be rewritten and reviewed before it passes the training gate. GPU execution, adapter artifacts and loss curves remain pending until actually produced. Never claim genuine fine-tuning has already happened. Sources: ml/config.json; ml/train.py; docs/DATASET.md; https://qwen.readthedocs.io/en/latest/training/unsloth.html.');
const steps=[['Review','1,500 examples\nHuman approvals'],['Train','CUDA QLoRA\nBest validation loss'],['Retain','Hashes, logs\nAdapter + manifest'],['Compare','Held-out prompts\nBlinded ratings']];
steps.forEach(([h,b],i)=>{let x=72+i*290;rect(s,x,225,260,210,i%2?C.teal:'#E3E9DF');text(s,h,x+20,249,220,55,34,i%2?C.white:C.ink,true);text(s,b,x+20,325,225,88,25,i%2?C.white:C.muted);});
text(s,'Current status: tooling and draft curriculum ready; human review and GPU training pending.',72,516,1130,110,29,C.ink,true);

s=base('Report measured results, then test the targets', '5:35–6:25. The two displayed timings are one synthetic local integration run, not a latency distribution or first-token measurement. Update this slide from evaluation/results before the assessed presentation. Software and smoke checks are not model-quality results. The held-out targets shown are proposed gates from the supplied plan, not achieved metrics. Discuss missing evidence openly. Sources: docs/EVALUATION.md; evaluation/results/latest.json; docs/RELEASE_CHECKLIST.md.');
text(s,'Available development evidence',72,190,560,60,32,C.teal,true);
text(s,'Both typed language journeys pass\nLocal Qwen + retrieval connected\nEnglish first turn: 18.3 s\nGenerated debrief: 74.1 s',72,275,555,210,29,C.ink);
text(s,'Assessed evaluation still required',685,190,530,60,32,C.teal,true);
text(s,'120 held-out model prompts\n40 retrieval questions\n24 speech recordings\n5–8 usability participants',685,275,510,250,29,C.ink);
rect(s,72,590,1136,55,C.teal);text(s,'One synthetic timing run. Latency targets remain unmet.',90,598,1090,40,26,C.white,true);

s=base('A coach for practice, with clear limits', '6:25–7:00. Transcript storage is consented and local. Azure voice sends audio or speech text to Azure after consent. Users can type, disable the avatar, inspect citations and delete sessions. The tool provides practice feedback and does not rank candidates or score protected traits, emotion, appearance or accent quality. Close by returning to the value: a more specific answer grounded in the actual role. Sources: README.md and docs/ARCHITECTURE.md.',true);
text(s,'Local transcripts\nVisible sources\nEditable captions\nRecoverable fallbacks',72,210,690,340,48,C.white,true);
text(s,'User control is part\nof the product.',810,270,370,200,40,C.gold,true);
text(s,'No hiring decisions or personality, appearance, or accent-quality scores.',72,610,1130,52,25,'#C9D6CF');

s=base('Q&A: know the tradeoffs', 'Appendix, outside the seven-minute talk. Suggested specialties: student 1 UI/avatar; student 2 speech; student 3 model/data; student 4 backend/retrieval. Replace assignments with actual contributions. Discuss base versus adapter, citation support, storage privacy, fallback quality and honest limitations. Source: presentation/DEMO_SCRIPT.md.');
const qa=[['Why QLoRA?','Lower training memory while retaining a reusable adapter.'],['Why retrieval?','Connect role-specific feedback to inspectable source text.'],['What can fail?','Speech, model JSON, WebGL and latency each have recovery paths.'],['What is still pending?','Human review, genuine training and the assessed evaluation gates.']];
qa.forEach(([q,a],i)=>{let y=197+i*110;text(s,q,72,y,385,70,29,C.teal,true);text(s,a,475,y,720,85,28,C.ink);});

for (const [i,slide] of ppt.slides.items.entries()) {
 const png=await ppt.export({slide,format:'png',scale:1});
 await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await(await PresentationFile.exportPptx(ppt)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const final=path.join(root,process.env.DECK_OUTPUT || 'presentation/VoxPrep-HK.pptx');
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:final,pythonExecutable:path.join(runtime,'python/bin/python3'),integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],explicitTotalSlideCount:8,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,receiptPath:path.join(build,path.basename(final)+'.validation.json')});
console.log(final);
