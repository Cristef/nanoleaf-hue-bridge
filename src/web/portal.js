"use strict";
let accountSetup=false,authenticated=false,csrf=null,tuningDraft={smoothingMs:0,saturation:100,blackThreshold:0},tuningDirty=false,tuningRevision=null,profileKey="",areaKey="",setupAreaKey="",pendingImport=null,deleteName=null,pairingTimer=null;
function hasDrafts(){return dirty||brightnessDirty||tuningDirty;}
function showAccount(){authenticated=false;$("portal-main").hidden=true;$("login-panel").hidden=true;$("account-panel").hidden=false;$("sync-label").hidden=true;$("logout").hidden=true;}
function showLogin(){authenticated=false;$("account-panel").hidden=true;$("portal-main").hidden=true;$("login-panel").hidden=false;$("sync-label").hidden=true;$("logout").hidden=true;clearTimeout(pairingTimer);$("nanoleaf-pairing-status").textContent="";}
function showPortal(){$("account-panel").hidden=true;authenticated=true;$("portal-main").hidden=false;$("login-panel").hidden=true;$("sync-label").hidden=false;$("logout").hidden=false;}
function targetPreview(rgb){
 if(Math.max(...rgb)<tuningDraft.blackThreshold)return [0,0,0];
 const max=Math.max(...rgb),min=Math.min(...rgb),delta=max-min;
 if(!delta||tuningDraft.saturation===100)return rgb;
 const saturation=Math.min(1,delta/max*tuningDraft.saturation/100),newMin=max*(1-saturation);
 return rgb.map(c=>newMin+(c-min)/delta*(max-newMin));
}
function options(select,items,current,preferCurrent=false){
 const previous=select.value;select.replaceChildren();
 for(const item of items){const option=document.createElement("option");option.value=item.id;option.textContent=item.name;select.append(option);}
 select.value=preferCurrent&&items.some(i=>i.id===current)?current:items.some(i=>i.id===previous)?previous:current||items[0]?.id||"";
}
function renderPortal(){
 if(!state)return;
 if(!tuningDirty){tuningDraft=clone(state.activeSettings.tuning);tuningRevision=state.tuningRevision;}
 for(const [id,key,suffix] of [["smoothing","smoothingMs"," ms"],["saturation","saturation","%"],["black-threshold","blackThreshold"," / 255"]]){$(id).value=tuningDraft[key];$(id).disabled=busy;$(id+"-value").textContent=tuningDraft[key]+suffix;}
 $("save-tuning").disabled=busy||!tuningDirty;$("tuning-status").textContent=tuningDirty?"Preview only. Save color response to apply.":"Saved color response applies during streaming.";
 $("discard").hidden=!hasDrafts();$("discard").disabled=busy;
 const pk=JSON.stringify(state.profiles);if(pk!==profileKey){profileKey=pk;options($("profile-select"),state.profiles.map(p=>({id:p.name,name:p.name})));}
 const ak=JSON.stringify([state.bridge,state.activeSettings.area,state.areas]);if(ak!==areaKey){areaKey=ak;options($("area-select"),state.areas,state.activeSettings.area,true);}
 for(const id of ["apply-profile","delete-profile"])$(id).disabled=busy||hasDrafts()||!$("profile-select").value;
 $("save-profile").disabled=busy||hasDrafts()||!$("profile-name").value.trim();$("apply-area").disabled=busy||hasDrafts()||!$("area-select").value||$("area-select").value===state.activeSettings.area;
 $("refresh-areas").disabled=busy;$("connect-hue").disabled=busy||["connecting","pairing"].includes(state.setupJob.phase);$("start-nanoleaf").disabled=busy;
 if(!$("setup-bridge").value)$("setup-bridge").value=state.bridge;
 const job=state.setupJob;
 $("setup-status").textContent=job.phase==="pairing"?"Press the physical Hue Bridge button now. Pairing waits up to three minutes.":job.phase==="connecting"?"Connecting to the Hue Bridge...":job.phase==="ready"?`Connected to ${job.bridge}. Select an Entertainment area to use it.`:job.phase==="error"?job.message:"Existing pairing remains valid. Connect again to refresh this bridge.";
 $("setup-area-row").hidden=job.phase!=="ready";if(job.phase==="ready"){const key=JSON.stringify([job.bridge,job.areas]);if(key!==setupAreaKey){setupAreaKey=key;options($("setup-area-select"),job.areas,state.activeSettings.area);}}
 $("apply-setup-area").disabled=busy||hasDrafts()||!$("setup-area-select").value;$("apply-import").disabled=busy||hasDrafts()||!pendingImport;
}
function discardDrafts(){draft=clone(state.mapping);revision=state.revision;brightnessDraft=clone(state.brightness);brightnessRevision=state.brightnessRevision;tuningDraft=clone(state.activeSettings.tuning);tuningRevision=state.tuningRevision;dirty=false;brightnessDirty=false;tuningDirty=false;render();}
async function portalAction(path,payload,message){
 if(busy)return;busy=true;render();
 try{const result=await request(path,payload);if(["/api/profile","/api/area","/api/import"].includes(path)){const response=await fetch("/api/state",{cache:"no-store"});if(!response.ok)throw new Error("Unable to refresh settings. Reload the page.");state=await response.json();areaKey="";discardDrafts();}notice(message);return result;}catch(error){notice(error.message);return null;}finally{busy=false;render();}
}
async function boot(){
 $("account-form").addEventListener("submit",async event=>{event.preventDefault();const button=$("account-form").querySelector("button");button.disabled=true;try{await request("/api/account/setup",{username:$("account-username").value,password:$("account-password").value,confirmation:$("account-confirmation").value});accountSetup=false;showPortal();poll();}catch(error){$("account-error").textContent=error.message;}finally{$("account-password").value="";$("account-confirmation").value="";button.disabled=false;}});

 $("login-form").addEventListener("submit",async event=>{event.preventDefault();const button=$("login-form").querySelector("button");button.disabled=true;$("login-error").textContent="";try{await request("/api/login",{username:$("login-username").value,password:$("access-key").value});if(accountSetup)showAccount();else{showPortal();poll();}}catch(error){$("login-error").textContent=error.message;}finally{$("access-key").value="";button.disabled=false;}});
 $("logout").addEventListener("click",async()=>{try{await request("/api/logout",{});showLogin();}catch(error){notice(error.message);}});
 $("discard").addEventListener("click",()=>{discardDrafts();notice("Unsaved changes discarded.");});
 for(const [id,key] of [["smoothing","smoothingMs"],["saturation","saturation"],["black-threshold","blackThreshold"]])$(id).addEventListener("input",()=>{tuningDraft[key]=Number($(id).value);tuningDirty=true;render();});
 $("save-tuning").addEventListener("click",async()=>{const result=await portalAction("/api/tuning",{tuning:tuningDraft,tuningRevision},"Color response saved.");if(result){tuningDirty=false;tuningDraft=clone(result.activeSettings.tuning);}});
 $("profile-name").addEventListener("input",renderPortal);
 $("area-select").addEventListener("change",renderPortal);
 $("save-profile").addEventListener("click",()=>portalAction("/api/profile",{operation:"save",name:$("profile-name").value,overwrite:$("profile-overwrite").checked},"Profile saved."));
 $("apply-profile").addEventListener("click",()=>portalAction("/api/profile",{operation:"apply",name:$("profile-select").value},"Profile applied. The stream updates on incoming colors."));
 $("delete-profile").addEventListener("click",()=>{deleteName=$("profile-select").value;$("delete-name").textContent=deleteName;$("delete-dialog").showModal();});
 $("cancel-delete").addEventListener("click",()=>$("delete-dialog").close());
 $("confirm-delete").addEventListener("click",()=>{$("delete-dialog").close();portalAction("/api/profile",{operation:"delete",name:deleteName},"Profile deleted. Active settings are unchanged.");});
 $("apply-area").addEventListener("click",()=>portalAction("/api/area",{bridge:state.bridge,area:$("area-select").value},"Entertainment area selected. The stream updates on incoming colors."));
 $("refresh-areas").addEventListener("click",()=>portalAction("/api/refresh",{},"Hue lights and Entertainment areas refreshed."));
 $("connect-hue").addEventListener("click",()=>portalAction("/api/setup/hue",{bridge:$("setup-bridge").value},"Hue connection started. Follow the pairing status below."));
 $("apply-setup-area").addEventListener("click",()=>portalAction("/api/area",{bridge:state.setupJob.bridge,area:$("setup-area-select").value},"Hue Bridge and area selected."));
 $("start-nanoleaf").addEventListener("click",async()=>{const result=await portalAction("/api/setup/nanoleaf",{},"Nanoleaf pairing is open for two minutes. Complete power-button pairing in Desktop.");if(result){clearTimeout(pairingTimer);$("nanoleaf-pairing-status").textContent="Pairing open for 120 seconds. In Nanoleaf Desktop, add the virtual device using power-button pairing.";pairingTimer=setTimeout(()=>{$("nanoleaf-pairing-status").textContent="Pairing window expired. Click Start Nanoleaf pairing to open it again if needed.";},120000);}});
 $("import-file").addEventListener("change",async()=>{pendingImport=null;$("import-preview").textContent="";const file=$("import-file").files[0];if(!file){renderPortal();return;}try{if(file.size>65536)throw new Error("Settings file must be smaller than 64 KiB.");const settings=JSON.parse(await file.text());const result=await request("/api/import/preview",{settings});pendingImport=settings;$("import-preview").textContent=`Reviewed: Hue Bridge ${result.bridge}, area ${result.area}, ${result.profiles.length} profiles, global brightness ${result.globalBrightness}%. Apply to replace current settings and profiles.`;}catch(error){$("import-preview").textContent=error.message;}renderPortal();});
 $("apply-import").addEventListener("click",async()=>{const result=await portalAction("/api/import",{settings:pendingImport},"Settings imported. Pairing and login preserved.");if(result){pendingImport=null;$("import-file").value="";$("import-preview").textContent="Import completed.";renderPortal();}});
 try{const response=await fetch("/api/session",{cache:"no-store"});const session=await response.json();csrf=session.csrf;accountSetup=session.setupRequired;if(accountSetup)showAccount();else if(session.authenticated){showPortal();poll();}else showLogin();}catch(error){$("login-error").textContent="Portal unavailable. Reload to reconnect.";}
}
