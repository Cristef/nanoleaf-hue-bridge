"use strict";
let advancedChannelKey="",advancedLightKey="";
const lightFields={saturation:"light-saturation",smoothingMs:"light-smoothing",blackThreshold:"light-threshold",redGain:"light-red",greenGain:"light-green",blueGain:"light-blue"};
function loadLightResponse(){if(!state)return;const id=$("response-light").value,settings={...state.activeSettings.tuning,redGain:100,greenGain:100,blueGain:100,...(state.activeSettings.channelSettings?.[id]||{})};for(const [key,node] of Object.entries(lightFields))$(node).value=settings[key];}
function renderAdvanced(){
 if(!state)return;
 $("diagnostic-report").textContent=state.diagnosticReport?.message||"Checking connection...";
 const checks=state.setupChecks||[];$("setup-checks").replaceChildren(...checks.map(c=>{const item=document.createElement("p");item.textContent=`${c.ok?"OK":"Pending"}: ${c.label}`;return item;}));
 if(!$("source-ip").value)$("source-ip").value=state.source?.ip||"";
 const channels=state.area.channels,key=JSON.stringify(channels);if(key!==advancedChannelKey){advancedChannelKey=key;options($("response-light"),channels.map(c=>({id:String(c.id),name:c.name})));options($("test-light"),[{id:"",name:"All lights"},...channels.map(c=>({id:String(c.id),name:c.name}))]);loadLightResponse();}
 const lightKey=JSON.stringify(state.activeSettings.channelSettings||{});if(lightKey!==advancedLightKey){advancedLightKey=lightKey;loadLightResponse();}
 $("suggest-mapping").disabled=busy||brightnessDirty||tuningDirty||!channels.length;
 for(const id of ["save-light-response","reset-light-response"])$(id).disabled=busy||hasDrafts()||!channels.length;
 const test=state.testMode||{};$("test-status").textContent=test.active?`${test.mode} test: ${test.secondsRemaining} seconds remaining.`:"No test running. Previous synchronization mode is preserved.";$("stop-test").disabled=busy||!test.active;$("start-test").disabled=busy||!channels.length;
 const release=state.updates||{};$("update-status").textContent=release.phase==="ready"?`Public release ${release.version}. ${release.message}`:release.phase==="checking"?"Checking GitHub...":release.message||"No release check yet.";$("update-notes").textContent=release.notes||"";
 $("install-update").disabled=busy||!state.stagedUpdate;$("install-update").textContent=state.stagedUpdate?`Install staged ${state.stagedUpdate.version}`:"Install staged update";
 $("rollback-update").disabled=busy||state.rollbackAvailable===false;
 $("maintenance-status").textContent=state.maintenance?.message||`Maintenance: ${state.maintenance?.phase||"idle"}`;
}
$("response-light").addEventListener("change",loadLightResponse);
$("save-light-response").addEventListener("click",()=>{const settings=clone(state.activeSettings.channelSettings||{});settings[$("response-light").value]=Object.fromEntries(Object.entries(lightFields).map(([k,id])=>[k,Number($(id).value)]));portalAction("/api/advanced/channels",{channelSettings:settings},"Per-light response saved.");});
$("reset-light-response").addEventListener("click",()=>{const settings=clone(state.activeSettings.channelSettings||{});delete settings[$("response-light").value];portalAction("/api/advanced/channels",{channelSettings:settings},"This light now uses global response.");});
$("suggest-mapping").addEventListener("click",async()=>{const suggestion=await portalAction("/api/advanced/mapping",{vertical:$("mapping-axis").value,flip:$("mapping-flip").checked,spread:$("mapping-spread").checked},"Mapping suggestion ready. Review and save to apply.");if(suggestion){draft=clone(suggestion.mapping);dirty=true;location.hash="/mapping";render();notice(suggestion.message);}});
$("start-test").addEventListener("click",()=>{const hex=$("test-color").value,rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)),light=$("test-light").value;portalAction("/api/advanced/test",{mode:$("test-pattern").value,seconds:Number($("test-seconds").value),rgb,channel:light===""?null:Number(light)},"Temporary color test started.");});
$("stop-test").addEventListener("click",()=>portalAction("/api/advanced/test",{operation:"stop"},"Test stopped; returning to normal operation."));
$("test-pattern").addEventListener("change",()=>{if($("test-pattern").value==="identify"&&$("test-light").value==="")$("test-light").value=String(state.area.channels[0]?.id??"");});
$("discover-4d").addEventListener("click",async()=>{const result=await portalAction("/api/setup/discover",{},"4D discovery completed.");if(result){options($("source-select"),result.devices.map(d=>({id:d.ip,name:`${d.name} (${d.ip})`})));if(result.devices.length)$("source-ip").value=$("source-select").value;}});
$("source-select").addEventListener("change",()=>$("source-ip").value=$("source-select").value);
$("save-source").addEventListener("click",()=>portalAction("/api/setup/source",{ip:$("source-ip").value},"4D source saved. Receiver restart queued."));
$("pair-desktop").addEventListener("click",async()=>{const result=await portalAction("/api/setup/desktop",{},"Desktop API pairing is open for 120 seconds.");if(result)$("desktop-pair-status").textContent="In Nanoleaf Desktop, add the virtual device using power-button pairing within two minutes.";});
$("check-update").addEventListener("click",()=>portalAction("/api/updates/check",{},"Checking public release notes."));
$("install-update").addEventListener("click",()=>{if(confirm("Install the staged compatible update? Services briefly restart; a private backup is created."))portalAction("/api/updates/action",{action:"update"},"Update queued. Reload after services restart.");});
$("rollback-update").addEventListener("click",()=>{if(confirm("Restore the most recent update backup? Current code and settings are replaced by the saved version."))portalAction("/api/updates/action",{action:"rollback"},"Recovery queued. Reload after services restart.");});
