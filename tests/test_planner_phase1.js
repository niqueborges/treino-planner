const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app.js'), 'utf8');
function assert(ok, message) { if (!ok) throw new Error(message); }
function extract(name) {
  const m = new RegExp(`^(?:async )?function ${name}\\(`, 'm').exec(source);
  if (!m) throw new Error(`Missing ${name}`);
  const start=m.index,open=source.indexOf('{',start);let depth=0;
  for(let i=open;i<source.length;i++){if(source[i]==='{')depth++;if(source[i]==='}'&&--depth===0)return source.slice(start,i+1)}
  throw new Error(`Unclosed ${name}`);
}
const names=['estimateWorkoutMinutes','workoutSummary','buildSetPatchPayload','localDateKey','completedWorkoutDaysForToday','completedWorkoutSessionsForToday','renderSessionExercisePicker','startPlannedWorkout','beginPlannedExecution','renderExecutionStep','advanceToNextExecutionStep','finishRestPeriod','pauseExecution','resumeExecution','advanceExecution'];
const functions=names.map(extract).join('\n');
function flow(extra={}) {
  let now=10000;
  const nodes=new Map(),calls={starts:[],stops:0,renders:0,requests:[],shown:0};
  const scope={
    executionSteps:[],executionIndex:0,executionStartedAt:0,executionDayId:null,executionWeekday:null,
    executionPaused:false,executionPausedAt:0,executionPausedDurationMs:0,restDeadlineAt:0,restRemainingSeconds:0,
    restAdvancesExecution:false,restSecondsForCurrentSet:0,
    activePlan:null,weekdayNames:['SEGUNDA','TERÇA'],selectedDashboardDay:1,nextWorkoutDay:null,
    completedWorkoutDayIdsToday:new Set(),completedWorkoutSessionsToday:[],pendingSessionExercises:[],pendingSessionDay:null,sessionDate:value=>new Date(`${String(value).replace(' ','T')}Z`),
    updatePlannerStartButtons(){},renderDashboardWeek(){},
    planDay:w=>extra.day||null,dayHasWorkout:d=>Boolean(d?.exercises?.length),workoutName:()=> 'Treino',
    document:{querySelector(sel){if(!nodes.has(sel))nodes.set(sel,{textContent:'',disabled:false,hidden:false,value:'',setAttribute(){}});return nodes.get(sel)}},
    Date:{now:()=>now},setNow:v=>{now=v},
    formatRestTime:s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`,showRestTime:s=>{scope.document.querySelector('#rest-timer-display').textContent=String(s)},
    restTimer:{start(s){calls.starts.push(s)},stop(){calls.stops++}},
    executionSnapshot(){return []},
    dialog:{showModal(){calls.shown++},close(){}},renderExecutionStep(){calls.renders++},
    async plannerRequest(...args){calls.requests.push(args);return{}},async loadDashboard(){},async loadHistory(){},
    escapeHtml:x=>String(x),executionDayId:7
  };
  const api=new Function('scope',`with(scope){${functions};return {estimateWorkoutMinutes,workoutSummary,buildSetPatchPayload,completedWorkoutDaysForToday,completedWorkoutSessionsForToday,renderSessionExercisePicker,startPlannedWorkout,beginPlannedExecution,advanceToNextExecutionStep,finishRestPeriod,pauseExecution,resumeExecution,advanceExecution}}`)(scope);
  return {scope,api,nodes,calls,setNow:v=>{now=v}};
}
let passed=0;
{
  const f=flow(),day={exercises:[{sets:[{rest_seconds:60},{rest_seconds:60},{rest_seconds:60}]},{sets:[{rest_seconds:30},{rest_seconds:30},{rest_seconds:30}]}]};
  assert(f.api.estimateWorkoutMinutes(day)===10,'duration estimate should round based on set time and configured rests');
  assert(f.api.workoutSummary(day)==='2 exercícios · 6 séries · ~10 min','weekly summary should include exercises, sets and approximate time');
  assert(f.api.estimateWorkoutMinutes({exercises:[]})===null,'empty days should not have invented duration');
  passed++;
}
{
  const f=flow(),payload=f.api.buildSetPatchPayload({repetitions:'8',load_value:'12.5',load_unit:'kg',rest_seconds:'60',notes:'Controlado'});
  assert(payload.repetitions===8&&payload.load_value===12.5&&payload.rest_seconds===60&&payload.load_unit==='kg'&&payload.notes==='Controlado','explicit save payload should normalize all series fields');
  passed++;
}
{
  const now=new Date('2026-10-18T15:00:00');
  const f=flow();
  const completed=f.api.completedWorkoutDaysForToday([
    {workout_day_id:7,completed_at:'2026-10-18 14:00:00'},
    {workout_day_id:8,completed_at:'2026-10-17 14:00:00'}
  ],now);
  assert(completed.has(7)&&!completed.has(8),'only workouts completed on the local current date should be blocked');
  passed++;
}
{
  const f=flow();f.scope.executionSteps=[{set:{rest_seconds:0}},{set:{rest_seconds:0}}];f.scope.executionIndex=1;f.scope.executionStartedAt=1000;f.scope.executionPausedDurationMs=0;f.setNow(9000);
  f.api.pauseExecution();assert(f.scope.executionPaused&&f.scope.executionIndex===1,'exercise pause should preserve the current step');
  assert(f.scope.document.querySelector('#complete-set').disabled,'complete action should be disabled while paused');
  f.setNow(69000);f.api.resumeExecution();assert(!f.scope.executionPaused&&f.scope.executionIndex===1,'resume should continue at the same step');
  assert(f.scope.executionPausedDurationMs===60000,'paused wall time should be tracked for exclusion');
  assert(!f.scope.document.querySelector('#complete-set').disabled,'complete action should return after resume');
  passed++;
}
{
  const f=flow();f.scope.executionSteps=[{set:{rest_seconds:30}},{set:{rest_seconds:0}}];f.scope.executionIndex=0;f.scope.restAdvancesExecution=true;f.scope.restDeadlineAt=40000;f.scope.executionStartedAt=1000;f.scope.executionPausedDurationMs=0;f.setNow(18000);
  f.api.pauseExecution();assert(f.scope.executionPaused&&f.scope.executionIndex===0,'rest pause should preserve current series');
  assert(f.scope.restRemainingSeconds===22,'rest pause should preserve the remaining countdown');
  f.setNow(78000);f.api.resumeExecution();assert(f.calls.starts.at(-1)===22,'rest resume should restart with only the remaining seconds');
  assert(f.scope.executionPausedDurationMs===60000,'rest pause duration should not count as active execution');
  assert(f.scope.executionIndex===0,'resuming rest should not advance early');
  passed++;
}
{
  const day={id:7,weekday:1,title:'Treino',exercises:[{sets:[{id:1,set_number:1,rest_seconds:30},{id:2,set_number:2,rest_seconds:30}]},{sets:[{id:3,set_number:1,rest_seconds:30}]}]};
  const f=flow({day});f.scope.planDay=()=>day;f.scope.executionStartedAt=0;
  f.api.startPlannedWorkout(1);
  assert(f.scope.executionSteps[2].exerciseIndex===2&&f.scope.executionSteps[2].exerciseCount===2,'execution step should identify exercise position');
  assert(f.scope.executionSteps[1].setIndex===2&&f.scope.executionSteps[1].total===2,'execution step should identify set position');
  passed++;
}
(async()=>{
  {
    const day={id:7,weekday:1,title:'Treino',exercises:[
      {id:101,display_name:'Agachamento',sets:[{set_number:1,rest_seconds:30}]},
      {id:202,display_name:'Exercício esquecido',sets:[{set_number:1,rest_seconds:30}]}
    ]};
    const f=flow({day});f.scope.planDay=()=>day;f.scope.completedWorkoutDayIdsToday=new Set([7]);
    f.scope.completedWorkoutSessionsToday=[{id:33,workout_day_id:7}];
    f.scope.plannerRequest=async url=>({snapshot_available:true,exercises:[{workout_exercise_id_snapshot:101,exercise_name_snapshot:'Agachamento'}]});
    await f.api.startPlannedWorkout(1);
    assert(f.calls.shown===1&&f.scope.executionSteps.length===0&&f.scope.pendingSessionExercises.length===2,'a follow-up session should open an empty exercise selection');
    assert(f.nodes.get('#execution-content').innerHTML.includes('Buscar exercício na biblioteca'),'a new session should let the user add exercises directly from the library');
    f.api.beginPlannedExecution(day,1,[day.exercises[1]]);
    assert(f.scope.executionSteps.length===1&&f.scope.executionSteps[0].exercise.id===202,'only exercises selected for the new session should enter execution');
    f.scope.executionPaused=true;f.scope.executionWeekday=1;
    f.api.startPlannedWorkout(1);
    assert(f.calls.shown===3&&!f.scope.executionPaused,'a paused workout can still be resumed');
    passed++;
  }
  const f=flow();f.scope.executionSteps=[{set:{rest_seconds:0}}];f.scope.executionIndex=0;f.scope.executionDayId=7;f.scope.executionStartedAt=10000;f.scope.executionPausedDurationMs=60000;f.setNow(80000);
  await f.api.advanceExecution();
  const body=JSON.parse(f.calls.requests[0][1].body);
  assert(body.duration_seconds===10,'recorded workout duration should exclude 60 seconds spent paused');
  passed++;
  console.log(`${passed} planner phase 1 tests passed`);
})().catch(error=>{throw error});

