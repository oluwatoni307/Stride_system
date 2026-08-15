// Full SPA logic for the throwaway Stride UI

function el(id){return document.getElementById(id)}
function pretty(obj){return JSON.stringify(obj, null, 2)}

const transient = {
  confirmedGoals: [],
  taskHistory: [],
  lastPulled: null,
}

async function doFetch(path, opts={}){
  try{
    const res = await fetch(path, opts)
    const data = await res.json().catch(()=>null)
    return { ok: res.ok, status: res.status, data }
  }catch(e){
    return { ok: false, error: String(e) }
  }
}

// --- Navigation ---
const navButtons = document.querySelectorAll('.nav-btn')
navButtons.forEach(b=> b.addEventListener('click', ()=> showView(b.dataset.view)))
function showView(name){
  document.querySelectorAll('.view').forEach(v=> v.classList.add('hidden'))
  const view = document.getElementById('view-'+name)
  if(view) view.classList.remove('hidden')
}
// default
showView('dashboard')

// --- Common helpers ---
function timeNow(){ return new Date().toISOString().slice(11,19) }
function logClient(msg, obj){
  const box = el('client-log')
  const entry = `${timeNow()} — ${msg}` + (obj? '\n'+pretty(obj): '') + '\n\n'
  if(box.textContent.trim() === '(no actions yet)') box.textContent = ''
  box.textContent = entry + box.textContent
}

// --- Health / Dashboard quick actions ---
el('btn-health').addEventListener('click', async ()=>{
  el('health-result').textContent = 'checking...'
  const r = await doFetch('/health')
  el('health-result').textContent = r.error ? r.error : pretty(r.data)
  logClient('/health ' + (r.ok? 'OK': 'ERROR'), r.data || r.error)
})
el('quick-draft').addEventListener('click', ()=>{ showView('goals'); el('raw-goal').value = 'Increase trial-to-paid conversion by 15% through onboarding improvements.'; el('btn-draft-goal').click() })
el('quick-weekly').addEventListener('click', ()=>{ showView('weekly'); el('btn-weekly').click() })
el('quick-pull').addEventListener('click', ()=>{ showView('tasks'); el('btn-pull').click() })

// --- Goals ---
el('btn-draft-goal').addEventListener('click', async ()=>{
  const user_id = el('goal-user-id').value
  const raw_goal = el('raw-goal').value
  el('draft-output').textContent = 'drafting...'
  const r = await doFetch('/goals/draft', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ user_id, raw_goal, user_context: '' }) })
  if(r.ok){
    el('draft-output').textContent = pretty(r.data)
    el('btn-confirm-goal').disabled = false
    window._lastDraft = r.data
    logClient('Draft produced', r.data)
  } else {
    el('draft-output').textContent = r.error || (r.data? pretty(r.data): 'Request failed')
    logClient('Draft failed', r.error || r.data)
  }
})

el('btn-confirm-goal').addEventListener('click', async ()=>{
  const user_id = el('goal-user-id').value
  const draft = window._lastDraft || null
  if(!draft){ alert('No draft to confirm'); return }
  el('draft-output').textContent = 'confirming...'
  const payload = { user_id, confirmed_draft: draft, smart_assessment: {}, week_start: new Date().toISOString().slice(0,10) }
  const r = await doFetch('/goals/confirm', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
  if(r.ok){
    el('draft-output').textContent = pretty(r.data)
    transient.confirmedGoals.unshift({ ts: new Date().toISOString(), data: r.data })
    renderConfirmedGoals()
    el('btn-confirm-goal').disabled = true
    logClient('Goal confirmed', r.data)
  } else {
    el('draft-output').textContent = r.error || pretty(r.data)
    logClient('Confirm failed', r.error || r.data)
  }
})

function renderConfirmedGoals(){
  const ul = el('confirmed-goals')
  ul.innerHTML = ''
  transient.confirmedGoals.slice(0,20).forEach(g=>{
    const li = document.createElement('li')
    li.textContent = g.ts + ' — ' + (g.data && g.data.goal? (g.data.goal.name || g.data.goal.goal_id) : JSON.stringify(g.data))
    ul.appendChild(li)
  })
}

// --- Tasks ---
el('btn-pull').addEventListener('click', async ()=>{
  const user_id = el('task-user-id').value
  const level = el('energy').value
  el('pulled-task').textContent = 'waiting...'
  const r = await doFetch('/tasks/pull', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ user_id, current_energy_level: level }) })
  if(r.ok){
    el('pulled-task').textContent = pretty(r.data)
    transient.lastPulled = r.data && r.data.pulled_task ? r.data.pulled_task : null
    el('btn-complete').disabled = !transient.lastPulled
    if(transient.lastPulled) transient.taskHistory.unshift({ ts: new Date().toISOString(), action: 'pulled', task: transient.lastPulled })
    renderTaskHistory()
    logClient('/tasks/pull', r.data)
  } else {
    el('pulled-task').textContent = r.error || (r.data? pretty(r.data): 'Request failed')
    logClient('pull failed', r.error || r.data)
  }
})

el('btn-complete').addEventListener('click', async ()=>{
  if(!transient.lastPulled){ alert('No pulled task available'); return }
  const user_id = el('task-user-id').value
  const payload = { user_id, task_id: transient.lastPulled.task_id, goal_id: transient.lastPulled.goal_id, milestone_id: transient.lastPulled.milestone_id, completion_timestamp: new Date().toISOString() }
  el('pulled-task').textContent = 'completing...'
  const r = await doFetch('/tasks/complete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) })
  el('pulled-task').textContent = r.error ? r.error : pretty(r.data)
  if(r.ok){
    transient.taskHistory.unshift({ ts: new Date().toISOString(), action: 'completed', task: transient.lastPulled, result: r.data })
    transient.lastPulled = null
    el('btn-complete').disabled = true
    renderTaskHistory()
    logClient('/tasks/complete', r.data)
  } else {
    logClient('complete failed', r.error || r.data)
  }
})

function renderTaskHistory(){
  const ul = el('task-history')
  ul.innerHTML = ''
  transient.taskHistory.slice(0,50).forEach(item=>{
    const li = document.createElement('li')
    li.textContent = `${item.ts} — ${item.action} — ${item.task? (item.task.description || item.task.task_id): ''}`
    ul.appendChild(li)
  })
}

// --- Scheduling ---
el('btn-allocate').addEventListener('click', async ()=>{
  const user_id = el('schedule-user-id').value
  const week_start = el('schedule-week').value || new Date().toISOString().slice(0,10)
  let slot_grid = {}
  try{ slot_grid = JSON.parse(el('slot-grid').value) }catch(e){ el('allocate-result').textContent = 'Invalid JSON'; return }
  el('allocate-result').textContent = 'allocating...'
  const r = await doFetch('/schedule/allocate', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ user_id, week_start, slot_grid }) })
  el('allocate-result').textContent = r.error ? r.error : pretty(r.data)
  logClient('/schedule/allocate', r.data || r.error)
})

// --- Weekly analytics (chart) ---
let milestoneChart = null
function renderMilestoneChart(summary){
  try{
    const canvas = el('milestone-chart')
    const util = summary.milestone_utilization || summary.milestone_utilization || []
    const labels = util.map(u => u.description || u.milestone_id)
    const consumed = util.map(u => u.consumed_units || 0)
    const maxUnits = util.map(u => u.max_weekly_units || 1)

    if(milestoneChart) milestoneChart.destroy()
    milestoneChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Consumed units', data: consumed, backgroundColor: 'rgba(75, 192, 192, 0.7)' },
          { label: 'Max units', data: maxUnits, backgroundColor: 'rgba(53, 162, 235, 0.5)' }
        ]
      },
      options: { responsive:true, maintainAspectRatio:false }
    })
  }catch(e){ console.warn('chart render failed', e) }
}

el('btn-weekly').addEventListener('click', async ()=>{
  const user_id = el('weekly-user-id').value
  const week_start = el('week-start').value || new Date().toISOString().slice(0,10)
  el('weekly-result').textContent = 'running...'
  const r = await doFetch('/weekly/cycle', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ user_id, week_start }) })
  if(r.ok){
    el('weekly-result').textContent = pretty(r.data)
    renderMilestoneChart(r.data)
    logClient('/weekly/cycle', r.data)
  } else {
    el('weekly-result').textContent = r.error || pretty(r.data)
    logClient('weekly failed', r.error || r.data)
  }
})

// --- Onboarding ---
el('btn-create-profile').addEventListener('click', async ()=>{
  const user_id = el('onboard-user-id').value
  const timezone = el('onboard-timezone').value
  const hours = Number(el('onboard-hours').value)
  const payload = { user_id, timezone, max_workable_hours: hours, availability: [] }
  el('onboarding-result').textContent = 'creating...'
  const r = await doFetch('/onboarding/profile', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
  el('onboarding-result').textContent = r.error? r.error : pretty(r.data)
  logClient('/onboarding/profile (create)', r.data || r.error)
})

el('btn-get-profile').addEventListener('click', async ()=>{
  const user_id = el('onboard-user-id').value
  el('onboarding-result').textContent = 'loading...'
  const r = await doFetch(`/onboarding/profile/${encodeURIComponent(user_id)}`)
  el('onboarding-result').textContent = r.error? r.error : pretty(r.data)
  logClient('/onboarding/profile (get)', r.data || r.error)
})

// --- Presentation mode ---
let presenting = false
let presentTimer = null
el('btn-start-presentation').addEventListener('click', ()=> startPresentation())
el('btn-stop-presentation').addEventListener('click', ()=> stopPresentation())

async function startPresentation(){
  if(presenting) return
  presenting = true
  el('btn-start-presentation').disabled = true
  el('btn-stop-presentation').disabled = false
  el('present-narration').textContent = 'Starting demo sequence...'
  el('present-log').textContent = ''

  const user = el('present-user-id').value || 'demo-user'

  const steps = [
    { text: 'Create onboarding profile', fn: async ()=>{
      el('present-narration').textContent = 'Creating onboarding profile...'
      const payload = { user_id: user, timezone: 'UTC', max_workable_hours: 15, availability: [] }
      const r = await doFetch('/onboarding/profile', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
      el('present-log').textContent += timeNow() + ' — created profile\n' + (r.data? pretty(r.data): r.error) + '\n\n'
    }},
    { text: 'Run weekly cycle and show analytics', fn: async ()=>{
      el('present-narration').textContent = 'Running weekly cycle...'
      const week_start = new Date().toISOString().slice(0,10)
      const r = await doFetch('/weekly/cycle', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ user_id: user, week_start }) })
      el('present-log').textContent += timeNow() + ' — weekly\n' + (r.data? pretty(r.data): r.error) + '\n\n'
      if(r.ok) renderMilestoneChart(r.data)
    }},
    { text: 'Pull a task', fn: async ()=>{
      el('present-narration').textContent = 'Pulling a task for user...'
      const r = await doFetch('/tasks/pull', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ user_id: user, current_energy_level: 'MEDIUM' }) })
      el('present-log').textContent += timeNow() + ' — pull\n' + (r.data? pretty(r.data): r.error) + '\n\n'
    }},
    { text: 'Complete pulled task', fn: async ()=>{
      el('present-narration').textContent = 'Completing pulled task...'
      // Try to read last pulled from transient state or from UI
      let pulled = transient.lastPulled
      if(!pulled){
        try{
          const pulledText = el('pulled-task').textContent
          const obj = JSON.parse(pulledText)
          pulled = obj && obj.pulled_task ? obj.pulled_task : null
        }catch(e){ pulled = null }
      }
      if(pulled){
        const payload = { user_id: user, task_id: pulled.task_id, goal_id: pulled.goal_id, milestone_id: pulled.milestone_id, completion_timestamp: new Date().toISOString() }
        const r = await doFetch('/tasks/complete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
        el('present-log').textContent += timeNow() + ' — complete\n' + (r.data? pretty(r.data): r.error) + '\n\n'
      } else {
        el('present-log').textContent += timeNow() + ' — no pulled task to complete\n\n'
      }
    }},
    { text: 'Finish', fn: async ()=>{ el('present-narration').textContent = 'Presentation finished.' } }
  ]

  for(const s of steps){
    if(!presenting) break
    el('present-narration').textContent = s.text
    try{ await s.fn() } catch(e){ el('present-log').textContent += 'Step error: '+String(e)+'\n\n' }
    // pause between steps
    await new Promise(r=> setTimeout(r, 900))
  }

  stopPresentation()
}

function stopPresentation(){
  presenting = false
  el('btn-start-presentation').disabled = false
  el('btn-stop-presentation').disabled = true
  el('present-narration').textContent = 'Presentation stopped.'
}

// --- Raw request and remaining quick features ---
el('btn-send-raw').addEventListener('click', async ()=>{
  const endpoint = el('raw-endpoint').value
  let body = {}
  try{ body = JSON.parse(el('raw-body').value) }catch(e){ el('raw-result').textContent = 'Invalid JSON'; return }
  el('raw-result').textContent = 'sending...'
  const r = await doFetch(endpoint, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) })
  el('raw-result').textContent = r.error ? r.error : pretty(r.data)
})

// keep UI responsive if server is mock or returns reduced payloads
console.log('UI loaded')
