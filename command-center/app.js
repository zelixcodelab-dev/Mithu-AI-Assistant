(() => {
  const API = '/api/v1/admin';
  const $ = (selector, root=document) => root.querySelector(selector);
  const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
  const state = {
    section:'overview', mode:'personal', permissionMode:'personal', selectedVoice:'OPggdAvz9vtogYnK5Ge4',
    voices:[], conversations:[], activeConversation:null, memories:[], permissions:{personal:[],business:[]},
    agent:{id:'agent_2801m8b0fg2zfdfbfvsgs2yg07sv',name:'Support Agent',branch:'agtbrch_8801m8b0fgzaekna55d5tptbtwaj',voice:'OPggdAvz9vtogYnK5Ge4'},
    eventSocket:null
  };
  const toast = (message, type='success') => {
    const node=document.createElement('div'); node.className='toast '+type; node.textContent=message;
    $('#toasts').append(node); setTimeout(()=>node.remove(),3600);
  };
  async function api(path, options={}) {
    const response=await fetch(API+path,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
    if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||body.message||('Request failed ('+response.status+')'));}
    return response.status===204?null:response.json();
  }
  function navigate(section) {
    if(!$('#section-'+section)) return;
    state.section=section;
    $$('.section-page').forEach(x=>x.classList.toggle('active',x.id==='section-'+section));
    $$('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.section===section));
    $('#breadcrumbCurrent').textContent=({overview:'Overview',agents:'Agent Studio',voice:'Voice Lab',conversations:'Conversations',memory:'Memory Centre',permissions:'Permissions',analytics:'Live Analytics',usage:'Usage & Credits'})[section];
    $('#sidebar').classList.remove('open');
    window.scrollTo({top:0,behavior:'smooth'});
    if(section==='conversations') loadConversations();
    if(section==='voice' && !state.voices.length) loadVoices();
    if(section==='memory') loadMemories();
    if(section==='permissions') loadPermissions();
  }
  $$('[data-section]').forEach(x=>x.addEventListener('click',()=>navigate(x.dataset.section)));
  $$('[data-goto]').forEach(x=>x.addEventListener('click',()=>navigate(x.dataset.goto)));
  $('#menuToggle').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
  $('#themeToggle').addEventListener('click',()=>{document.body.classList.toggle('light');localStorage.setItem('mithu-theme',document.body.classList.contains('light')?'light':'dark');});
  if(localStorage.getItem('mithu-theme')==='light')document.body.classList.add('light');
  $('#helpBtn').addEventListener('click',()=>toast('Help documentation will be connected in the next release.','success'));

  async function loadOverview() {
    try {
      const data=await api('/overview');
      if(data.agent){state.agent={...state.agent,...data.agent};$('#agentName').textContent=data.agent.name||state.agent.name;$('#agentNameInput').value=data.agent.name||'';$('#agentLang').textContent=data.agent.language||'—';}
      const stats=data.stats||{};
      if(stats.conversations!=null)$('#statConversations').textContent=stats.conversations;
      if(stats.success_rate!=null)$('#statSuccess').innerHTML=Number(stats.success_rate).toFixed(0)+'<span class="unit">%</span>';
      if(stats.average_duration_secs!=null)$('#statDuration').innerHTML=Number(stats.average_duration_secs).toFixed(0)+'<span class="unit">s</span>';
      if(stats.total_cost_usd!=null)$('#statSpend').textContent='$'+Number(stats.total_cost_usd).toFixed(4);
      if(data.services?.api)$('#apiStatus').textContent='Connected';
    } catch(e){console.info('Command Center running in preview mode:',e.message);}
  }
  $('#refreshBtn').addEventListener('click',()=>loadOverview().then(()=>toast('Workspace snapshot refreshed.')));
  $('#agentRefresh').addEventListener('click',()=>loadAgent());
  $('#versionRefresh').addEventListener('click',()=>loadAgent());
  async function loadAgent() {
    try {
      const d=await api('/agent');
      state.agent={...state.agent,...d};
      $('#agentName').textContent=d.name||state.agent.name;
      $('#agentNameInput').value=d.name||'';
      $('#agentIdLabel').textContent=d.agent_id||state.agent.id;
      $('#agentLanguage').value=d.language||'ml';
      $('#agentLang').textContent=d.language||'—';
      $('#firstMessage').value=d.first_message||'';
      $('#llmSelect').value=d.llm||'deepseek-v41-flash';
      $('#systemPrompt').value=d.prompt||'';
      $('#temperature').value=d.temperature??0;
      $('#monitoring').checked=!!d.monitoring_enabled;
      $('#maxDuration').value=d.max_duration_seconds||600;
      $('#recordVoice').checked=d.record_voice!==false;
      $('#requireAuth').checked=!!d.require_auth;
      $('#retention').value=String(d.retention_days??-1);
    } catch(e){toast('Agent configuration is not yet connected to the admin API.','error');}
  }
  $$('.settings-tab').forEach(x=>x.addEventListener('click',()=>{ $$('.settings-tab').forEach(t=>t.classList.toggle('active',t===x)); $$('.settings-pane').forEach(p=>p.classList.toggle('active',p.id==='tab-'+x.dataset.tab));}));
  async function saveConfig(payload){try{await api('/agent',{method:'PATCH',body:JSON.stringify(payload)});toast('Configuration saved as a draft.');}catch(e){toast(e.message,'error');}}
  $('#saveAgentGeneral').addEventListener('click',()=>saveConfig({name:$('#agentNameInput').value,first_message:$('#firstMessage').value,language:$('#agentLanguage').value}));
  $('#saveModel').addEventListener('click',()=>saveConfig({llm:$('#llmSelect').value,prompt:$('#systemPrompt').value,temperature:Number($('#temperature').value),max_tokens:Number($('#maxTokens').value)}));
  $('#saveBehaviour').addEventListener('click',()=>saveConfig({allow_interruptions:$('#interruptions').checked,hinglish_mode:$('#hinglish').checked,monitoring_enabled:$('#monitoring').checked,max_duration_seconds:Number($('#maxDuration').value)}));
  $('#saveSecurity').addEventListener('click',()=>saveConfig({record_voice:$('#recordVoice').checked,require_auth:$('#requireAuth').checked,retention_days:Number($('#retention').value)}));

  async function loadVoices() {
    $('#voiceGrid').innerHTML='<div class="panel loading-card">Loading voice catalogue…</div>';
    try {
      const d=await api('/voices'); state.voices=d.voices||[]; renderVoices();
    } catch(e){$('#voiceGrid').innerHTML='<div class="panel loading-card">Voice catalogue is available after the admin API is configured.</div>';}
  }
  function renderVoices() {
    const query=$('#voiceSearch').value.toLowerCase(), gender=$('#voiceGender').value;
    const filtered=state.voices.filter(v=>(!query||(v.name+' '+(v.description||'')).toLowerCase().includes(query))&&(!gender||String(v.gender||v.labels?.gender||'').toLowerCase()===gender));
    $('#voiceGrid').innerHTML=filtered.length?filtered.map(v=>'<article class="panel voice-card '+(state.selectedVoice===v.voice_id?'selected':'')+'"><div class="voice-card-orb">'+escapeHtml((v.name||'V')[0].toUpperCase())+'</div><div class="voice-card-copy"><strong>'+escapeHtml(v.name)+'</strong><small>'+escapeHtml(v.description||v.language||'ElevenLabs voice')+'</small></div><div class="voice-card-actions"><button class="mini-play" data-preview="'+escapeAttr(v.voice_id)+'" title="Preview">▶</button><button class="choose-voice" data-choose="'+escapeAttr(v.voice_id)+'" title="Select">✓</button></div></article>').join(''):'<div class="panel loading-card">No voices match this search.</div>';
    $$('[data-preview]').forEach(b=>b.addEventListener('click',()=>previewVoice(b.dataset.preview)));
    $$('[data-choose]').forEach(b=>b.addEventListener('click',()=>{state.selectedVoice=b.dataset.choose;renderVoices();toast('Voice selected. Save to apply it to the agent.');}));
  }
  function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  const escapeAttr=escapeHtml;
  async function previewVoice(id){try{const d=await api('/voices/'+encodeURIComponent(id)+'/preview');if(!d.audio_url)throw new Error('No preview URL returned');const audio=new Audio(d.audio_url);await audio.play();}catch(e){toast(e.message,'error');}}
  $('#voiceSearch').addEventListener('input',renderVoices);$('#voiceGender').addEventListener('change',renderVoices);
  $('#voiceRefresh').addEventListener('click',loadVoices);$('#playSample').addEventListener('click',()=>previewVoice(state.agent.voice));
  $('#voicePreviewCurrent').addEventListener('click',()=>previewVoice(state.agent.voice));
  $('#testVoiceBtn').addEventListener('click',()=>{navigate('voice');previewVoice(state.agent.voice);});
  ['stability','similarity','speed'].forEach(id=>$('#'+id).addEventListener('input',e=>$('#'+id+'Value').textContent=e.target.value+'%'));
  $('#saveVoiceSettings').addEventListener('click',async()=>{try{await api('/agent/voice',{method:'PATCH',body:JSON.stringify({voice_id:state.selectedVoice,stability:Number($('#stability').value)/100,similarity_boost:Number($('#similarity').value)/100,speed:Number($('#speed').value)/100})});state.agent.voice=state.selectedVoice;toast('Voice settings saved as a draft.');}catch(e){toast(e.message,'error');}});

  async function loadConversations() {
    $('#conversationTable').innerHTML='<tr><td colspan="6" class="table-empty">Loading conversations…</td></tr>';
    try{const d=await api('/conversations');state.conversations=d.conversations||[];renderConversations();}
    catch(e){$('#conversationTable').innerHTML='<tr><td colspan="6" class="table-empty">Conversation history is not available from the admin API.</td></tr>';$('#conversationCount').textContent='—';}
  }
  function renderConversations(){
    const q=$('#conversationSearch').value.toLowerCase(), status=$('#conversationStatus').value;
    const rows=state.conversations.filter(c=>(!q||(c.title||'').toLowerCase().includes(q))&&(!status||c.call_successful===status));
    $('#conversationCount').textContent=rows.length+' result'+(rows.length===1?'':'s');
    $('#conversationTable').innerHTML=rows.length?rows.map(c=>'<tr><td><div class="conversation-name"><strong>'+escapeHtml(c.title||'Untitled conversation')+'</strong><small>'+escapeHtml(c.conversation_id||'')+'</small></div></td><td>'+escapeHtml(c.language||'—')+'</td><td>'+Number(c.duration_secs||0)+' sec</td><td><span class="status-pill '+(c.call_successful==='success'?'good':'pending')+'">'+escapeHtml(c.call_successful||'unknown')+'</span></td><td>'+ (c.cost_usd!=null?'$'+Number(c.cost_usd).toFixed(5):'—')+'</td><td><button class="row-arrow" data-open="'+escapeAttr(c.conversation_id)+'">↗</button></td></tr>').join(''):'<tr><td colspan="6" class="table-empty">No matching conversations.</td></tr>';
    $$('[data-open]').forEach(b=>b.addEventListener('click',()=>openConversation(b.dataset.open)));
  }
  $('#conversationSearch').addEventListener('input',renderConversations);$('#conversationStatus').addEventListener('change',renderConversations);$('#conversationRefresh').addEventListener('click',loadConversations);
  async function openConversation(id){
    try{const d=await api('/conversations/'+encodeURIComponent(id));$('#transcriptTitle').textContent=d.title||'Conversation detail';$('#transcriptMeta').textContent=(d.language||'')+' · '+(d.duration_secs||0)+' seconds · '+(d.call_successful||'unknown');$('#transcriptMessages').innerHTML=(d.transcript||[]).map(t=>'<div class="transcript-bubble '+(t.role==='user'?'user':'agent')+'"><small>'+escapeHtml(t.role||'assistant')+'</small>'+escapeHtml(t.message||'')+'</div>').join('');$('#transcriptPanel').hidden=false;$('#transcriptPanel').scrollIntoView({behavior:'smooth',block:'start'});}
    catch(e){toast(e.message,'error');}
  }
  $('#closeTranscript').addEventListener('click',()=>$('#transcriptPanel').hidden=true);

  async function loadMemories(){try{const d=await api('/memories?context='+state.mode);state.memories=d.memories||[];renderMemories();}catch(e){renderMemories();}}
  function renderMemories(){
    const q=$('#memorySearch').value.toLowerCase(),cat=$('#memoryCategory').value;
    const list=state.memories.filter(m=>(!q||(m.title+' '+m.content).toLowerCase().includes(q))&&(!cat||m.category===cat));
    $('#personalCount').textContent=state.mode==='personal'?state.memories.length:'—';
    $('#businessCount').textContent=state.mode==='business'?state.memories.length:'—';
    $('#memoryList').innerHTML=list.length?list.map(m=>'<article class="panel memory-card"><div class="memory-symbol">✳</div><div class="memory-copy"><strong>'+escapeHtml(m.title)+'</strong><p>'+escapeHtml(m.content)+'</p><small>'+escapeHtml(m.category)+' · '+escapeHtml(m.context)+' · '+escapeHtml(m.updated_at||'Saved')+'</small></div><div class="memory-actions"><button class="mini-play" data-edit-memory="'+escapeAttr(m.id)+'">✎</button><button class="mini-play" data-delete-memory="'+escapeAttr(m.id)+'">×</button></div></article>').join(''):'<div class="panel empty-state"><div>✳</div><h3>No saved memories yet</h3><p>Add an item to this '+state.mode+' memory space.</p></div>';
    $$('[data-delete-memory]').forEach(b=>b.addEventListener('click',()=>deleteMemory(b.dataset.deleteMemory)));
    $$('[data-edit-memory]').forEach(b=>b.addEventListener('click',()=>editMemory(b.dataset.editMemory)));
  }
  $$('[data-mode]').forEach(b=>{if(b.classList.contains('mode-button'))b.addEventListener('click',()=>{state.mode=b.dataset.mode;$$('.mode-button').forEach(x=>x.classList.toggle('active',x===b));$('#memoryContext').value=state.mode;loadMemories();});});
  $('#memorySearch').addEventListener('input',renderMemories);$('#memoryCategory').addEventListener('change',renderMemories);
  function openModal(memory){$('#modalTitle').textContent=memory?'Edit memory':'Add memory';$('#memoryTitle').value=memory?.title||'';$('#memoryContent').value=memory?.content||'';$('#memoryType').value=memory?.category||'preference';$('#memoryContext').value=memory?.context||state.mode;$('#memoryForm').dataset.id=memory?.id||'';$('#modalBackdrop').classList.add('open');}
  $('#newMemory').addEventListener('click',()=>openModal());$('#modalClose').addEventListener('click',closeModal);$('#modalCancel').addEventListener('click',closeModal);function closeModal(){$('#modalBackdrop').classList.remove('open');}
  async function editMemory(id){const m=state.memories.find(x=>x.id===id);if(m)openModal(m);}
  $('#memoryForm').addEventListener('submit',async e=>{e.preventDefault();const id=e.currentTarget.dataset.id;const body={title:$('#memoryTitle').value,content:$('#memoryContent').value,category:$('#memoryType').value,context:$('#memoryContext').value};try{await api('/memories'+(id?'/'+encodeURIComponent(id):''),{method:id?'PATCH':'POST',body:JSON.stringify(body)});closeModal();toast(id?'Memory updated.':'Memory saved.');loadMemories();}catch(err){toast(err.message,'error');}});
  async function deleteMemory(id){if(!confirm('Delete this memory permanently?'))return;try{await api('/memories/'+encodeURIComponent(id),{method:'DELETE'});toast('Memory deleted.');loadMemories();}catch(e){toast(e.message,'error');}}

  const permissionDefinitions={
    personal:[['read_personal_memory','Read personal memory','Retrieve facts and preferences saved in personal context.','allow'],['write_personal_memory','Save personal memory','Store new facts after explicit consent.','approval'],['calendar_read','Read personal calendar','View events from a connected personal calendar.','approval'],['calendar_write','Create or change events','Create, move or cancel personal calendar events.','approval'],['financial_actions','Financial actions','Payments, transfers or financial commitments.','deny'],['external_messages','Send external messages','Email, SMS or messages to other people.','approval']],
    business:[['read_business_memory','Read business memory','Retrieve records from the selected business workspace.','allow'],['write_business_memory','Save business memory','Store business procedures and approved operational context.','approval'],['educonnect_read','EduConnect read-only tools','Query data exposed by the isolated, authenticated gateway.','approval'],['educonnect_write','EduConnect record changes','Any create, edit or delete action in EduConnect Pro.','deny'],['crm_update','Update CRM records','Change leads, student status or assignments.','deny'],['financial_actions','Financial actions','Payments, refunds or financial commitments.','deny'],['external_messages','Send external messages','Email, SMS or contact with students/partners.','approval']]
  };
  async function loadPermissions(){try{const d=await api('/permissions');state.permissions=d.permissions||state.permissions;}catch(e){}renderPermissions();}
  function renderPermissions(){
    const defs=permissionDefinitions[state.permissionMode];$('#permissionHeading').textContent=state.permissionMode==='personal'?'Personal assistant permissions':'Business assistant permissions';
    $('#permissionList').innerHTML=defs.map(([key,title,desc,defaultValue])=>{const saved=state.permissions[state.permissionMode].find(x=>x.permission===key);const value=saved?.decision||defaultValue;return '<div class="permission-row"><div class="permission-info"><strong>'+title+'</strong><small>'+desc+'</small></div><select class="permission-select" data-permission="'+key+'"><option value="allow" '+(value==='allow'?'selected':'')+'>Allowed</option><option value="approval" '+(value==='approval'?'selected':'')+'>Needs approval</option><option value="deny" '+(value==='deny'?'selected':'')+'>Denied</option></select></div>';}).join('');
  }
  $$('.mode-card').forEach(b=>b.addEventListener('click',()=>{state.permissionMode=b.dataset.mode;$$('.mode-card').forEach(x=>x.classList.toggle('active',x===b));renderPermissions();}));
  $('#savePermissions').addEventListener('click',async()=>{const entries=$$('[data-permission]').map(s=>({permission:s.dataset.permission,decision:s.value}));try{await api('/permissions',{method:'PUT',body:JSON.stringify({context:state.permissionMode,permissions:entries})});toast('Permission policy saved.');}catch(e){toast(e.message,'error');}});

  $('#usageRefresh').addEventListener('click',async()=>{try{const d=await api('/usage');toast(d.account_balance==null?'Usage refreshed. Account balance is not exposed by this connector.':'Usage refreshed.');}catch(e){toast('Account-level credits are not available from the current integration.','error');}});
  async function startEventSocket(){
    try{const d=await api('/monitoring/session',{method:'POST',body:JSON.stringify({agent_id:state.agent.id})});if(!d.websocket_url)return;
      const ws=new WebSocket(d.websocket_url);state.eventSocket=ws;
      ws.onopen=()=>{$('#socketStatus').textContent='Connected';$('#socketStatus').className='status-pill good';};
      ws.onmessage=e=>{const event=JSON.parse(e.data);const row=document.createElement('div');row.className='event-item';const safe=escapeHtml(event.event||event.type||'event');row.innerHTML='<i class="event-dot"></i><div class="event-content"><strong>'+safe+'</strong><p>'+escapeHtml(JSON.stringify(event).slice(0,240))+'</p><small>'+new Date().toLocaleTimeString()+'</small></div>';$('#eventStream').prepend(row);$('#eventStream').querySelector('.empty-state')?.remove();};
      ws.onclose=()=>{$('#socketStatus').textContent='Disconnected';$('#socketStatus').className='status-pill pending';};
      ws.onerror=()=>{$('#socketStatus').textContent='Connection error';};
    }catch(e){console.info('Live monitor unavailable:',e.message);}
  }

  loadOverview();loadAgent();loadConversations();loadVoices();loadPermissions();
  // Live monitoring is deliberately opt-in and is opened only from the analytics page.
  document.querySelector('[data-section="analytics"]').addEventListener('click',()=>startEventSocket(),{once:true});
})();