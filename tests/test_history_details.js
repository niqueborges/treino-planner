const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');

function assert(condition, message) { if (!condition) throw new Error(message); }
function extractFunction(name) {
  const match = new RegExp(`^(?:async )?function ${name}\\(`, 'm').exec(source);
  if (!match) throw new Error(`Function ${name} not found in app.js`);
  const open = source.indexOf('{', match.index);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    if (source[i] === '}' && --depth === 0) return source.slice(match.index, i + 1);
  }
  throw new Error(`Unclosed function ${name}`);
}

(async () => {
  let passed = 0;
  {
    const requests = [];
    const elements = new Map();
    const scope = {
      executionSteps: [
        { exerciseIndex: 1, exercise: { id: 5, display_name: 'Agachamento' }, set: { set_number: 1, repetitions: 8, load_value: 20, load_unit: 'kg', rest_seconds: 60, notes: '' } },
        { exerciseIndex: 1, exercise: { id: 5, display_name: 'Agachamento' }, set: { set_number: 2, repetitions: 8, load_value: 20, load_unit: 'kg', rest_seconds: 60, notes: 'Controlado' } },
        { exerciseIndex: 2, exercise: { id: 6, display_name: 'Remada' }, set: { set_number: 1, repetitions: 10, load_value: null, load_unit: 'none', rest_seconds: 45, notes: '' } }
      ],
      document: { querySelector(selector) { if (!elements.has(selector)) elements.set(selector, { innerHTML: '', showModal() { this.open = true; } }); return elements.get(selector); } },
      plannerRequest: async url => { requests.push(url); return { completed_at: '2026-10-18T12:00:00', plan_name_snapshot: 'Plano', day_title_snapshot: 'Treino A', duration_seconds: 900, snapshot_available: true, exercises: [{ exercise_name_snapshot: 'Agachamento', sets: [{ set_number: 1, repetitions: 8, load_value: 20, load_unit: 'kg', rest_seconds: 60, notes: '' }] }] }; },
      sessionDate: value => new Date(value),
      fmtDuration: () => '15 min',
      escapeHtml: value => String(value)
    };
    const funcs = [extractFunction('executionSnapshot'), extractFunction('openHistorySession')].join('\n');
    const result = new Function('scope', `with(scope){${funcs};return {executionSnapshot,openHistorySession}}`)(scope);
    const snapshot = result.executionSnapshot();
    assert(snapshot.length === 2 && snapshot[0].sets.length === 2, 'snapshot should preserve exercise order and all configured sets');
    assert(snapshot[1].display_name === 'Remada' && snapshot[1].workout_exercise_id === 6 && snapshot[1].sets[0].load_unit === 'none', 'snapshot should retain the exercise identity, name and set data');
    passed += 1;
    await result.openHistorySession(42);
    assert(requests.length === 1 && requests[0] === '/api/history/42', 'opening history should request only the read-only detail endpoint');
    assert(elements.get('#history-detail-dialog').open, 'history details should open in its dialog');
    assert(elements.get('#history-detail-content').innerHTML.includes('Agachamento'), 'historical exercise details should be rendered');
    assert(!requests.some(url => url === '/api/workout-sessions'), 'opening history must not start or record a workout');
    passed += 1;
  }
  console.log(`History detail tests: ${passed} passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
