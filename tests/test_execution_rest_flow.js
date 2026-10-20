globalThis.__executionRestFlowTestPromise = (async function () {
  const fs = typeof require === 'function' ? require('node:fs') : null;
  const path = typeof require === 'function' ? require('node:path') : null;
  const source = globalThis.__APP_SOURCE__ || fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
  const timerApi = globalThis.RestTimerController
    ? { createRestTimerController: globalThis.RestTimerController }
    : require('../rest-timer.js');

  function assert(condition, message) { if (!condition) throw new Error(message); }
  function extractFunction(name) {
    const marker = new RegExp(`^(?:async )?function ${name}\\(`, 'm');
    const match = marker.exec(source);
    if (!match) throw new Error(`Function ${name} not found in app.js`);
    const start = match.index;
    const open = source.indexOf('{', start);
    let depth = 0;
    for (let i = open; i < source.length; i += 1) {
      if (source[i] === '{') depth += 1;
      if (source[i] === '}') {
        depth -= 1;
        if (depth === 0) return source.slice(start, i + 1);
      }
    }
    throw new Error(`Unclosed function ${name}`);
  }
  const functions = ['updateActivePlanSet', 'startPlannedWorkout', 'beginPlannedExecution', 'advanceToNextExecutionStep', 'finishRestPeriod', 'skipRestPeriod', 'advanceExecution']
    .map(extractFunction).join('\n');

  function makeFlow(seconds = [42, 30, 0]) {
    const nodes = new Map();
    const document = { querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, { disabled: false, hidden: false, textContent: '' });
      return nodes.get(selector);
    } };
    const calls = { starts: [], stops: 0, renders: 0, requests: [], closed: false, dashboardLoads: 0 };
    const scope = {
      executionSteps: seconds.map(rest_seconds => ({ set: { rest_seconds } })),
      executionIndex: 0,
      executionPaused: false, executionPausedDurationMs: 0, executionWeekday: null, restDeadlineAt: 0, restRemainingSeconds: 0,
      restAdvancesExecution: false,
      executionSnapshot() { return []; },
      completedWorkoutDayIdsToday: new Set(), completedWorkoutSessionsToday: [], updatePlannerStartButtons() {}, renderDashboardWeek() {},
      executionDayId: 7,
      executionStartedAt: 1000,
      document,
      dialog: { close() { calls.closed = true; } },
      restTimer: {
        start(value) { calls.starts.push(value); },
        stop() { calls.stops += 1; }
      },
      renderExecutionStep() { calls.renders += 1; document.querySelector('#complete-set').disabled = false; },
      async plannerRequest(url) { calls.requests.push(url); return {}; },
      async loadDashboard() { calls.dashboardLoads += 1; }
    };
    scope.Date = { now: () => 31000 };
    const flow = new Function('scope', `with(scope){${functions}; return {advanceExecution,finishRestPeriod,skipRestPeriod};}`)(scope);
    return { scope, flow, nodes: document, calls };
  }

  let passed = 0;
  {
    const state = makeFlow([42, 30, 0]);
    await state.flow.advanceExecution();
    assert(state.calls.starts.length === 1 && state.calls.starts[0] === 42, 'intermediate series should start its own configured rest');
    assert(state.scope.executionIndex === 0 && state.calls.renders === 0, 'next series must not render before rest finishes');
    assert(state.nodes.querySelector('#complete-set').disabled, 'series advance must be disabled during rest');
    assert(!state.nodes.querySelector('#skip-rest').hidden, 'skip action should be available only during rest');
    assert(state.nodes.querySelector('#rest-next-step').textContent === 'Próxima série: 2 de 3', 'next series should be shown as information');
    passed += 1;
  }
  {
    const state = makeFlow([17, 30]);
    await state.flow.advanceExecution();
    state.flow.finishRestPeriod();
    assert(state.scope.executionIndex === 1 && state.calls.renders === 1, 'timer completion should advance and render the next series');
    assert(state.calls.starts[0] === 17, 'rest duration must come from the completed series');
    passed += 1;
  }
  {
    const state = makeFlow([45, 30]);
    await state.flow.advanceExecution();
    state.flow.skipRestPeriod();
    assert(state.calls.stops === 1, 'skipping should stop the single active timer');
    assert(state.scope.executionIndex === 1 && state.calls.renders === 1, 'skip should advance exactly one series');
    passed += 1;
  }
  {
    const state = makeFlow([0, 30]);
    state.scope.executionIndex = 1;
    await state.flow.advanceExecution();
    assert(state.calls.starts.length === 0, 'last series must not start a rest timer');
    assert(state.calls.requests.length === 1 && state.calls.requests[0] === '/api/workout-sessions', 'last series should preserve workout finalization');
    assert(state.calls.closed && state.calls.dashboardLoads === 1, 'successful finalization should close and refresh dashboard');
    passed += 1;
  }
  {
    const state = makeFlow([5, 30]);
    let now = 1000;
    let timerCallback;
    const controller = timerApi.createRestTimerController({
      AudioContextCtor: function () { throw new Error('audio unavailable'); },
      now: () => now,
      setIntervalFn(fn) { timerCallback = fn; return 1; },
      clearIntervalFn() {},
      onFinish: state.flow.finishRestPeriod
    });
    state.scope.restTimer = controller;
    await state.flow.advanceExecution();
    now += 5000;
    timerCallback();
    assert(state.scope.executionIndex === 1 && state.calls.renders === 1, 'audio failure must not prevent advancing after timer end');
    passed += 1;
  }
  {
    const planFlow = new Function('scope', `with(scope){${functions}; return {updateActivePlanSet,startPlannedWorkout,beginPlannedExecution,advanceExecution};}`);
    for (const configuredSeconds of [30, 60, 90]) {
      const starts = [];
      const day = { id: 11, weekday: 1, title: 'Treino', exercises: [{ sets: [
        { id: 101, set_number: 1, rest_seconds: 90 },
        { id: 102, set_number: 2, rest_seconds: 90 }
      ] }] };
      const nodes = new Map();
      const scope = {
        activePlan: { days: [day] },
        executionSteps: [], executionIndex: 0, executionPaused: false, executionPausedAt: 0, executionPausedDurationMs: 0, executionWeekday: null, restDeadlineAt: 0, restRemainingSeconds: 0, restAdvancesExecution: false,
        completedWorkoutDayIdsToday: new Set(), completedWorkoutSessionsToday: [], updatePlannerStartButtons() {}, renderDashboardWeek() {},
        executionStartedAt: 1000, executionDayId: null,
        planDay: () => day, dayHasWorkout: value => Boolean(value?.exercises?.length),
        weekdayNames: ['SEGUNDA'], workoutName: () => 'Treino',
        restTimer: { stop() {}, start(value) { starts.push(value); } },
        document: { querySelector(selector) { if (!nodes.has(selector)) nodes.set(selector, { textContent: '', disabled: false, hidden: false }); return nodes.get(selector); } },
        renderExecutionStep() {}, dialog: { showModal() {} },
        Date: { now: () => 1000 }
      };
      const flow = planFlow(scope);
      flow.updateActivePlanSet({ id: 101, rest_seconds: configuredSeconds });
      flow.startPlannedWorkout(1);
      await flow.advanceExecution();
      assert(starts.length === 1 && starts[0] === configuredSeconds, `configured rest ${configuredSeconds}s must reach restTimer.start unchanged`);
    }
    passed += 1;
  }
  assert(source.includes("onFinish:()=>{document.querySelector('#skip-rest').hidden=true;document.querySelector('#rest-status').textContent='Descanso concluído.';finishRestPeriod()}"), 'timer completion must be connected to execution advancement');
  assert(!source.includes("querySelector('#start-rest-timer')"), 'manual start timer control must not remain');
  if (typeof console !== 'undefined') console.log(`${passed} execution/rest integration tests passed`);
  globalThis.__executionRestFlowTestCount = passed;
})().catch(error => { throw error; });
